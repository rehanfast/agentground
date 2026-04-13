"""
backend/app/agent_executor.py
Wires a registered Agent record to a LangChain AgentExecutor and runs it.
Handles single-agent and multi-agent sequential runs.
"""

from __future__ import annotations
from typing import Generator

from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_tools_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema.messages import SystemMessage, HumanMessage

from backend.app.database import get_session
from backend.app.models import Agent, Tool, AgentTool
from backend.app.tools.terminal_tool import get_langchain_terminal_tool
from backend.app.resource_callback import ResourceCallbackHandler
from backend.app import audit_logger, run_manager


# ── Tool factory ──────────────────────────────────────────────────────────────
def _build_tool(tool_name: str):
    """Return the LangChain tool object for a given tool name."""
    if tool_name == "Terminal":
        return get_langchain_terminal_tool()
    elif tool_name == "Web Search":
        from langchain_community.tools import DuckDuckGoSearchRun
        return DuckDuckGoSearchRun()
    elif tool_name == "File Read/Write":
        from langchain_community.tools.file_management import (
            ReadFileTool, WriteFileTool
        )
        return [ReadFileTool(), WriteFileTool()]
    return None


def _get_tools_for_agent(agent_id: int, environment_id: int) -> list:
    """
    Retrieve tools for an agent respecting private/shared scope:
    - Private: only tools directly assigned to this agent
    - Shared: tools assigned (as shared) to any agent in the environment
    """
    session = get_session()
    try:
        # Private tools for this agent
        private = (
            session.query(AgentTool)
            .filter_by(agent_id=agent_id, scope="shared")
            .all()
        )
        # Actually get private for this agent too
        private_own = (
            session.query(AgentTool)
            .filter_by(agent_id=agent_id, scope="private")
            .all()
        )
        # Shared tools for the environment (any agent in this env with scope=shared)
        from backend.app.models import Agent as AgentModel
        env_agent_ids = [
            a.id for a in session.query(AgentModel)
            .filter_by(environment_id=environment_id).all()
        ]
        shared = (
            session.query(AgentTool)
            .filter(
                AgentTool.agent_id.in_(env_agent_ids),
                AgentTool.scope == "shared"
            ).all()
        )
        seen_tool_ids = set()
        result = []
        for at in list(private_own) + list(shared):
            if at.tool_id not in seen_tool_ids:
                seen_tool_ids.add(at.tool_id)
                built = _build_tool(at.tool.name)
                if built:
                    if isinstance(built, list):
                        result.extend(built)
                    else:
                        result.append(built)
        return result
    finally:
        session.close()


# ── Single agent run ──────────────────────────────────────────────────────────
def run_single_agent(
    agent_id:       int,
    environment_id: int,
    run_id:         int,
    user_message:   str,
    callback:       ResourceCallbackHandler,
    step_offset:    int = 0,
) -> str:
    """
    Execute one agent and return its final answer.
    All steps are logged to audit_logs.
    """
    session = get_session()
    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found.")
        system_prompt = agent.system_prompt
        api_url       = agent.api_url
        model_name    = agent.model_name
    finally:
        session.close()

    tools     = _get_tools_for_agent(agent_id, environment_id)
    step_num  = step_offset
    final_ans = ""

    # Log the initial LLM request
    step_num += 1
    audit_logger.log_step(run_id, agent_id, step_num, "llm_request", {
        "model":         model_name,
        "api_url":       api_url,
        "system_prompt": system_prompt[:500],
        "user_message":  user_message[:500],
        "tool_count":    len(tools),
        "tool_names":    [t.name for t in tools],
    })

    try:
        # Build LLM (via LangChain OpenAI wrapper — adapts to any OpenAI-compatible endpoint)
        llm = ChatOpenAI(
            model=model_name,
            openai_api_base=api_url,
            streaming=False,
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        if tools:
            lc_agent = create_openai_tools_agent(llm, tools, prompt)
            executor = AgentExecutor(
                agent=lc_agent,
                tools=tools,
                verbose=False,
                handle_parsing_errors=True,
            )
        else:
            # No tools — just direct LLM call
            executor = None

        if executor:
            result = executor.invoke(
                {"input": user_message},
                config={"callbacks": [callback]},
            )
            final_ans = result.get("output", "")
        else:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ]
            response  = llm.invoke(messages, config={"callbacks": [callback]})
            final_ans = response.content

    except StopIteration as e:
        # Resource limit or stop request
        step_num += 1
        audit_logger.log_step(run_id, agent_id, step_num, "run_stopped", {
            "reason": str(e)
        })
        return f"[STOPPED] {e}"

    except Exception as e:
        step_num += 1
        audit_logger.log_step(run_id, agent_id, step_num, "run_error", {
            "error": str(e)
        })
        raise

    # Log final answer
    step_num += 1
    audit_logger.log_step(run_id, agent_id, step_num, "llm_response", {
        "final_answer": final_ans[:1000],
        "total_llm_calls": callback.call_count,
    })

    return final_ans


# ── Multi-agent sequential run ────────────────────────────────────────────────
def run_sequential(
    agent_ids:      list[int],
    environment_id: int,
    run_id:         int,
    initial_message: str,
    max_calls:      int = 10,
    timeout_secs:   int = 60,
) -> dict:
    """
    Run a list of agents sequentially.
    Each agent receives the previous agent's output as its user message.
    Returns a dict with results and final status.
    """
    callback = ResourceCallbackHandler(max_calls=max_calls, timeout_secs=timeout_secs)
    callback.start_timeout()

    results     = []
    current_msg = initial_message
    step_offset = 0
    status      = "completed"

    try:
        for idx, agent_id in enumerate(agent_ids):
            output = run_single_agent(
                agent_id=agent_id,
                environment_id=environment_id,
                run_id=run_id,
                user_message=current_msg,
                callback=callback,
                step_offset=step_offset,
            )
            results.append({"agent_id": agent_id, "output": output})
            current_msg  = f"Previous agent output:\n{output}\n\nContinue with the task."
            step_offset += 10  # leave gaps in step numbering between agents

            if output.startswith("[STOPPED]"):
                status = "stopped"
                break

    except Exception as e:
        status = "failed"
        audit_logger.log_step(run_id, agent_ids[0], step_offset + 1, "run_error", {
            "error": str(e)
        })
    finally:
        callback.cancel_timeout()
        run_manager.update_run_status(run_id, status)

    return {
        "run_id":   run_id,
        "status":   status,
        "results":  results,
        "final_output": results[-1]["output"] if results else "",
    }
