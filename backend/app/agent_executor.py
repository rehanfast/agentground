"""
backend/app/agent_executor.py
Wires Agent records to LangChain executors.
Streams live progress via log_queue → ResourceCallbackHandler.
"""

from __future__ import annotations

import os
import queue
import threading
from typing import Callable, Optional

from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import SystemMessage, HumanMessage

from backend.app.database import get_session
from backend.app.models import Agent, AgentTool, ModelConfig
from backend.app.tools.terminal_tool import get_langchain_terminal_tool
from backend.app.resource_callback import ResourceCallbackHandler, AgentStopException
from backend.app import audit_logger, run_manager
from backend.app.auth_manager import get_agent_workspace, get_run_workspace
from backend.app.provider_adapters import (
    make_llm, invoke_llm, detect_provider,
    load_env_keys, resolve_keys_list,
)
from backend.app.key_manager import run_with_rotation


_CREDIT_ERR_MSG = (
    "API failure: Insufficient credits, exhausted keys, or strict rate limits. "
    "Master agent should step down to a fallback model."
)


def _is_credit_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    if "too many tool" in msg or "tool execution" in msg:
        return False
    return any(t in msg for t in (
        "402", "insufficient", "payment", "quota", "billing", 
        "exhausted", "429", "rate limit", "too many requests"
    ))


# ── Tool factory ───────────────────────────────────────────────────────────────

def _build_tool(tool_name: str, workspace_path: str = ""):
    if tool_name == "Terminal":
        return get_langchain_terminal_tool(workspace_path=workspace_path)
    if tool_name == "Web Search":
        # Using new langchain-tavily package if available, else fallback
        try:
            from langchain_tavily import TavilySearchResults
        except ImportError:
            from langchain_community.tools.tavily_search import TavilySearchResults
        return TavilySearchResults(max_results=3)
    if tool_name == "File Read/Write":
        from langchain_community.tools.file_management import ReadFileTool, WriteFileTool
        kwargs = {"root_dir": workspace_path} if workspace_path else {}
        return [ReadFileTool(**kwargs), WriteFileTool(**kwargs)]
    return None


def _get_tools_for_agent(
    agent_id: int, environment_id: int, run_id: int = 0,
    db_name: str = "", username: str = "",
) -> list:
    session = get_session(db_name)
    try:
        private_own = session.query(AgentTool).filter_by(agent_id=agent_id, scope="private").all()
        env_agent_ids = [
            a.id for a in session.query(Agent).filter_by(environment_id=environment_id).all()
        ]
        shared = session.query(AgentTool).filter(
            AgentTool.agent_id.in_(env_agent_ids), AgentTool.scope == "shared",
        ).all()

        workspace = ""
        if username:
            try:
                workspace = (get_run_workspace(username, environment_id, run_id, agent_id)
                             if run_id else
                             get_agent_workspace(username, environment_id, agent_id))
            except Exception:
                workspace = ""

        seen, result = set(), []
        for at in list(private_own) + list(shared):
            if at.tool_id not in seen:
                seen.add(at.tool_id)
                built = _build_tool(at.tool.name, workspace_path=workspace)
                if built:
                    result.extend(built) if isinstance(built, list) else result.append(built)
        return result
    finally:
        session.close()


# ── Key resolution ─────────────────────────────────────────────────────────────

def _resolve_keys_and_provider(
    api_url: str, model_id: str, db_name: str = ""
) -> tuple[str, list[str], int | None]:
    """Returns (provider, resolved_keys, model_config_id_or_None)."""
    provider = detect_provider(api_url, model_id)

    if provider == "ollama":
        return "ollama", ["ollama"], None

    # Check model registry first
    if db_name:
        try:
            session = get_session(db_name)
            try:
                mc = session.query(ModelConfig).filter_by(
                    api_url=api_url, model_id=model_id, is_active=True
                ).first()
                if mc and mc.api_keys:
                    keys = resolve_keys_list(mc.api_keys, provider)
                    if keys:
                        return provider, keys, mc.id
            finally:
                session.close()
        except Exception:
            pass

    # Fall back to .env
    keys = load_env_keys(provider)
    if not keys:
        raise RuntimeError(
            f"No API key found for provider '{provider}'. "
            f"Add {provider.upper()}_API_KEY to .env or configure a model in Settings → Model Registry."
        )
    return provider, keys, None


# ── Context builder ────────────────────────────────────────────────────────────

def _build_context_prompt(
    agent_name: str,
    tool_names: list[str],
    pipeline_agents: list[dict] | None = None,
    agent_position: int = 0,
    total_agents: int = 1,
) -> str:
    """Build a context block that is appended to the agent's system prompt.

    This ensures the agent always knows:
      - Its own name and position in the pipeline
      - What tools it has (and crucially, what it does NOT have)
      - Who the other agents are and what they do
      - Behavioral guidelines for clean execution
    """
    lines: list[str] = [
        "",
        "─── EXECUTION CONTEXT (auto-injected) ───",
        f"You are **{agent_name}** (agent {agent_position + 1} of {total_agents} in this pipeline).",
    ]

    # Tools
    if tool_names:
        lines.append(f"You have access to these tools: {', '.join(tool_names)}.")
        has_terminal = any("terminal" in t.lower() for t in tool_names)
        has_write    = any("write" in t.lower() for t in tool_names)
        if has_write and not has_terminal:
            lines.append(
                "⚠️ You do NOT have a Terminal tool. You CANNOT execute scripts. "
                "Only write files or search the web. Do not attempt to create "
                "runner/wrapper scripts — another agent with Terminal access will execute code."
            )
        if has_terminal:
            lines.append(
                "You have Terminal access. Use it to execute commands and scripts directly. "
                "Do not write wrapper scripts — run commands in one step."
            )
    else:
        lines.append("You have no tools. Respond with analysis and text only.")

    # Pipeline peers
    if pipeline_agents and len(pipeline_agents) > 1:
        lines.append("")
        lines.append("**Pipeline agents (in execution order):**")
        for i, pa in enumerate(pipeline_agents):
            marker = " ← YOU" if pa["name"] == agent_name else ""
            pa_tools = ", ".join(pa.get("tool_names", [])) or "none"
            lines.append(f"  {i+1}. **{pa['name']}** — tools: [{pa_tools}]{marker}")
        lines.append("")
        lines.append(
            "Focus ONLY on your specific role. Do not attempt tasks assigned to other agents. "
            "Your output will be passed to the next agent as their input."
        )

    # Behavioral guidelines
    lines.append("")
    lines.append("**Guidelines:**")
    lines.append("- Be concise and structured in your output.")
    lines.append("- Use tools efficiently — prefer fewer, purposeful tool calls over many exploratory ones.")
    lines.append("- When writing files, write the final version directly; do not iterate on drafts.")
    lines.append("- Summarize your work at the end so the next agent can pick up seamlessly.")
    lines.append("─── END CONTEXT ───")

    return "\n".join(lines)


# ── Single agent execution ─────────────────────────────────────────────────────

def run_single_agent(
    agent_id: int, environment_id: int, run_id: int, user_message: str,
    callback: ResourceCallbackHandler, step_offset: int = 0,
    db_name: str = "", username: str = "",
    log_fn: Callable[[str], None] | None = None,
    max_iterations: int = 10,
    pipeline_agents: list[dict] | None = None,
    agent_position: int = 0,
    total_agents: int = 1,
) -> str:

    session = get_session(db_name)
    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent:
            raise ValueError(f"Agent {agent_id} not found.")
        system_prompt = agent.system_prompt
        api_url       = agent.api_url
        model_name    = agent.model_name
        agent_name    = agent.name
    finally:
        session.close()

    # Inject agent name into callback for live log labels
    callback.agent_name = agent_name

    if log_fn: log_fn(f"▶ **{agent_name}** starting (`{model_name}`)…")

    tools    = _get_tools_for_agent(agent_id, environment_id, run_id=run_id,
                                    db_name=db_name, username=username)
    tool_names = [t.name for t in tools]
    step_num = step_offset + 1

    # Enrich system prompt with pipeline context
    context_block = _build_context_prompt(
        agent_name=agent_name,
        tool_names=tool_names,
        pipeline_agents=pipeline_agents,
        agent_position=agent_position,
        total_agents=total_agents,
    )
    enriched_prompt = system_prompt + context_block

    audit_logger.log_step(
        run_id, agent_id, step_num, "llm_request",
        {"model": model_name, "api_url": api_url,
         "system_prompt": enriched_prompt,
         "user_message": user_message,
         "tool_names": tool_names},
        db_name=db_name,
    )

    try:
        provider, keys, mc_id = _resolve_keys_and_provider(api_url, model_name, db_name)

        def _invoke(api_key: str) -> str:
            llm = make_llm(provider, api_url, model_name, api_key)
            if tools:
                prompt = ChatPromptTemplate.from_messages([
                    SystemMessage(content=enriched_prompt),
                    ("human", "{input}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ])
                lc_agent = create_tool_calling_agent(llm, tools, prompt)
                executor = AgentExecutor(agent=lc_agent, tools=tools,
                                         handle_parsing_errors=True,
                                         max_iterations=max_iterations,
                                         early_stopping_method="force")
                try:
                    result = executor.invoke(
                        {"input": user_message},
                        config={"callbacks": [callback]},
                    )
                    out = result.get("output", "")
                    if isinstance(out, list):
                        # Flatten list of content blocks (common with thinking models)
                        texts = []
                        for b in out:
                            if isinstance(b, str): texts.append(b)
                            elif isinstance(b, dict):
                                if "text" in b: texts.append(b["text"])
                        out = "".join(texts)
                    return str(out)
                except Exception as e:
                    if "Extra data" in str(e) or "Expecting value" in str(e) or "JSON" in str(e):
                        if log_fn: log_fn(f"⚠️ LLM output parsing error caught. Assuming partial success. ({e})")
                        return f"The agent completed tasks but encountered a formatting error in its final output: {e}"
                    raise
            else:
                msgs = [SystemMessage(content=enriched_prompt),
                        HumanMessage(content=user_message)]
                return invoke_llm(llm, msgs, stop_event=callback._stop_event)

        if mc_id is not None:
            final_ans = run_with_rotation(mc_id, keys, _invoke, log_fn=log_fn, stop_event=callback._stop_event)
        elif len(keys) > 1:
            final_ans = run_with_rotation(id(tuple(keys)), keys, _invoke, log_fn=log_fn, stop_event=callback._stop_event)
        else:
            final_ans = _invoke(keys[0])

    except AgentStopException as e:
        audit_logger.log_step(run_id, agent_id, step_num + 1, "run_stopped",
                               {"reason": str(e)}, db_name=db_name)
        if log_fn: log_fn(f"⏹ **{agent_name}** stopped: {e}")
        return f"[STOPPED] {e}"

    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)}"
        audit_logger.log_step(run_id, agent_id, step_num + 1, "run_error",
                               {"error": msg}, db_name=db_name)
        if log_fn: log_fn(f"❌ **{agent_name}** error: {msg}")
        if _is_credit_error(e):
            return f"[ERROR] {msg}"
        raise

    audit_logger.log_step(
        run_id, agent_id, step_num + 1, "llm_response",
        {"final_answer": final_ans, "total_llm_calls": callback.call_count},
        db_name=db_name,
    )
    if log_fn: log_fn(f"✅ **{agent_name}** done.")
    return final_ans


# ── Multi-agent sequential run ─────────────────────────────────────────────────

def run_sequential(
    agent_ids: list[int], environment_id: int, run_id: int, initial_message: str,
    max_calls: int = 10, timeout_secs: int = 60, rpm_limit: int = 0,
    stop_event: Optional[threading.Event] = None,
    db_name: str = "", username: str = "",
    log_fn: Callable[[str], None] | None = None,
    log_queue: Optional[queue.Queue] = None,
) -> dict:

    _log = log_fn or (lambda m: log_queue.put_nowait(m) if log_queue else None)

    callback = ResourceCallbackHandler(
        max_calls=max_calls, timeout_secs=timeout_secs,
        rpm_limit=rpm_limit,
        stop_event=stop_event, log_queue=log_queue,
    )
    callback.start_timeout()

    results, current_msg = [], initial_message
    step_offset, status  = 0, "completed"

    # Fair share: each agent gets at most (total calls / num agents) iterations,
    # with a minimum of 5 and a maximum of 15 to avoid runaway loops.
    num_agents = max(len(agent_ids), 1)
    per_agent_iters = max(5, min(15, max_calls // num_agents))

    # Build pipeline context so each agent knows about its peers
    pipeline_agents = []
    session = get_session(db_name)
    try:
        for aid in agent_ids:
            ag = session.query(Agent).filter_by(id=aid).first()
            if ag:
                ag_tools = _get_tools_for_agent(aid, environment_id, run_id=run_id,
                                                db_name=db_name, username=username)
                pipeline_agents.append({
                    "name": ag.name,
                    "tool_names": [t.name for t in ag_tools],
                })
            else:
                pipeline_agents.append({"name": f"Agent {aid}", "tool_names": []})
    finally:
        session.close()

    try:
        for i, agent_id in enumerate(agent_ids):
            if stop_event and stop_event.is_set():
                status = "stopped"
                break
            _log(f"--- Agent {i+1}/{len(agent_ids)} ---")
            output = run_single_agent(
                agent_id=agent_id, environment_id=environment_id, run_id=run_id,
                user_message=current_msg, callback=callback, step_offset=step_offset,
                db_name=db_name, username=username, log_fn=_log,
                max_iterations=per_agent_iters,
                pipeline_agents=pipeline_agents,
                agent_position=i,
                total_agents=num_agents,
            )
            results.append({"agent_id": agent_id, "output": output})
            current_msg  = f"Previous agent output:\n{output}\n\nContinue."
            step_offset += 10
            if output.startswith("[STOPPED]"):
                status = "stopped"
                break
    except Exception as e:
        status = "failed"
        first_id = agent_ids[0] if agent_ids else 0
        audit_logger.log_step(run_id, first_id, step_offset + 1, "run_error",
                               {"error": str(e)}, db_name=db_name)
        _log(f"❌ Run error: {e}")
    finally:
        callback.cancel_timeout()
        run_manager.update_run_status(run_id, status, db_name=db_name)

    return {
        "run_id":       run_id,
        "status":       status,
        "results":      results,
        "final_output": results[-1]["output"] if results else "",
    }
