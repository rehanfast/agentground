"""
backend/app/auto_mode/master_agent.py
AgentGround Auto Mode — Master Orchestrator.

Model selection:
  - Uses the user's Model Registry (model_manager) sorted by intelligence_rank.
  - Tries best ranked model first; on API error falls back to next model.
  - Uses key_manager for per-model key rotation within each model config.
  - If all models exhausted, raises a clean error.

Execution patterns: sequential, parallel, cyclic.
Evaluation loop: re-plans or retries based on evaluator judgment.
"""

from __future__ import annotations

import json
import os
import threading
import concurrent.futures
from typing import Callable

from langchain_core.messages import SystemMessage, HumanMessage

from backend.app import env_manager, agent_manager, tool_manager, run_manager, audit_logger
from backend.app.resource_callback import ResourceCallbackHandler, AgentStopException
from backend.app.provider_adapters import make_llm, invoke_llm, detect_provider, load_env_keys
from backend.app.key_manager import run_with_rotation
from backend.app.agent_executor import run_single_agent


# ── Master system prompt ──────────────────────────────────────────────────────

MASTER_SYSTEM_PROMPT = """\
You are AgentGround's Master Orchestrator — an autonomous AI project manager, \
system architect, and quality controller.

Your mission: given a task, design and oversee a multi-agent system that completes it fully.

## Responsibilities
1. ANALYSE  — Understand exactly what the task needs.
2. DESIGN   — Plan specialised sub-agents, each with a focused role and tight system prompt.
3. ORCHESTRATE — Choose the best execution pattern for the task.
4. EVALUATE — Judge whether the combined output satisfies the task.
5. ITERATE  — If unsatisfied, re-plan with feedback and run again.

## Execution patterns
- sequential: each agent receives the previous agent's output as input (pipeline).
- parallel:   agents run concurrently on the SAME input; a synthesizer merges results.
- cyclic:     like sequential but the pipeline repeats until the evaluator is satisfied
              or max_iterations is reached. Use for tasks benefiting from refinement loops.

## Output format — respond ONLY with valid JSON, no markdown fences:
{
  "task_analysis": "2-3 sentence analysis",
  "agents": [
    {
      "name": "UniqueAgentName",
      "role": "One-sentence role",
      "system_prompt": "Full, specific system prompt. Include tone, format, constraints, expected output.",
      "tools": [],
      "complexity": "low|medium|high"
    }
  ],
  "execution_pattern": "sequential|parallel|cyclic",
  "execution_order": [[0], [1, 2], [3]],
  "synthesis_instruction": "How to merge parallel outputs (only for parallel pattern)",
  "success_criteria": "Clear, measurable criteria for task completion",
  "max_iterations": 2
}

## execution_order
Each element is a GROUP of agent indices (0-based). Within a group: concurrent. Groups: sequential.
- Simple sequential: [[0], [1], [2]]
- Fully parallel:    [[0, 1, 2], [3]]   (agents 0/1/2 concurrent, then synthesizer 3)

## Available tool names (exact strings)
- "Web Search"      — search the internet via Tavily
- "Terminal"        — run whitelisted shell commands
- "File Read/Write" — read/write files in the agent workspace

## agent.complexity
Hint for the Auto Mode model selector:
  low    — summarisation, formatting, translation
  medium — research, writing, analysis
  high   — coding, architecture design, multi-step reasoning

## Rules
- 2-4 agents is ideal; scale up only for genuinely complex multi-domain work.
- System prompts must be specific and actionable.
- NEVER include any text outside the JSON object.
"""

EVALUATION_PROMPT = """\
You are a quality evaluator for an autonomous AI system.

Task: {task}
Success criteria: {criteria}
Combined output: {outputs}

Has the task been completed satisfactorily?
Respond ONLY with valid JSON:
{{
  "satisfied": true,
  "score": 8,
  "feedback": "What was done well and what (if anything) is still missing.",
  "next_action": "done"
}}

next_action must be: "done" | "retry" | "replan"
- "done"   — task complete
- "retry"  — re-run same plan with feedback as additional context
- "replan" — approach was fundamentally wrong; redesign the plan
"""


# ── LLM with fallback chain ───────────────────────────────────────────────────

def _call_with_fallback(
    fallback_chain: list[dict],
    system_prompt:  str,
    user_message:   str,
    log_fn:         Callable[[str], None] | None = None,
    stop_event:     threading.Event | None = None,
) -> str:
    """
    Try each model in the fallback chain. Smart error handling:
      - Model-level errors (404, billing, model not found) → skip to next model
      - Rate/auth errors → handled by key rotation within run_with_rotation
      - Other errors (network, task) → propagate immediately, don't waste time
    """
    def _log(msg: str):
        if log_fn: log_fn(msg)

    if not fallback_chain:
        raise RuntimeError(
            "Model registry is empty. Go to Settings → Model Registry and add a model."
        )

    skipped, last_exc = [], None
    for mc in list(fallback_chain):  # Iterate over copy so we can safely remove
        if stop_event and stop_event.is_set():
            raise AgentStopException("Stopped by user.")

        provider = mc["provider"]
        model_id = mc["model_id"]
        api_url  = mc["api_url"]

        from backend.app.provider_adapters import resolve_keys_list
        keys = resolve_keys_list(mc.get("api_keys") or [], provider)

        if not keys:
            _log(f"⏭ Skipping {mc['display_name']} — no API keys found.")
            skipped.append(mc["display_name"])
            fallback_chain.remove(mc)
            continue

        _log(f"🤖 Using **{mc['display_name']}** (`{model_id}`)…")

        def _invoke(api_key: str, _url=api_url, _mid=model_id, _prov=provider,
                    _sys=system_prompt, _usr=user_message) -> str:
            llm = make_llm(_prov, _url, _mid, api_key)
            return invoke_llm(llm, [
                SystemMessage(content=_sys),
                HumanMessage(content=_usr),
            ], stop_event=stop_event)

        try:
            return run_with_rotation(mc["id"], keys, _invoke, log_fn=log_fn, stop_event=stop_event)
        except AgentStopException:
            raise
        except Exception as exc:
            msg = str(exc).lower()
            # Model-level errors: skip to next model
            if any(t in msg for t in ("404", "not found", "does not exist",
                                       "model_not_found", "invalid model",
                                       "billing", "insufficient", "402",
                                       "resourceexhausted", "quota", "429", "rate limit",
                                       "500", "503", "internal", "unavailable")):
                last_exc = exc
                _log(f"⏭ {mc['display_name']} unavailable or quota exceeded: {str(exc).splitlines()[0][:80]}... Trying next…")
                skipped.append(mc["display_name"])
                fallback_chain.remove(mc)
                continue
            # All keys exhausted after rotation retries
            if "exhausted" in msg or "failed after" in msg:
                last_exc = exc
                _log(f"⏭ {mc['display_name']} all keys exhausted. Trying next…")
                skipped.append(mc["display_name"])
                fallback_chain.remove(mc)
                continue
            # Unknown error — propagate immediately
            raise

    raise RuntimeError(
        f"All models failed. Skipped: {', '.join(skipped) or 'none'}. "
        f"Last error: {last_exc}\n"
        "Check your API keys in Settings → Model Registry or .env."
    )


def _call_master_llm(
    fallback_chain: list[dict],
    user_message:   str,
    log_fn:         Callable[[str], None] | None = None,
    stop_event:     threading.Event | None = None,
) -> str:
    return _call_with_fallback(fallback_chain, MASTER_SYSTEM_PROMPT, user_message, log_fn, stop_event)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _parse_json(text: any) -> dict:
    if not isinstance(text, str):
        # Handle cases where invoke_llm or sub-agent might have leaked a list/dict
        if isinstance(text, list):
            # Try to find a string in the list, or just stringify it
            texts = [str(x) for x in text if isinstance(x, str)]
            text = "".join(texts) if texts else str(text)
        else:
            text = str(text)

    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.rstrip("`").strip()
    return json.loads(text)


# ── Planner ───────────────────────────────────────────────────────────────────

def plan(
    task: str,
    fallback_chain: list[dict],
    feedback: str = "",
    log_fn: Callable[[str], None] | None = None,
    stop_event: threading.Event | None = None,
) -> dict:
    user_msg = task
    if feedback:
        user_msg = (
            f"Original task: {task}\n\n"
            f"Previous attempt feedback (improve your plan accordingly):\n{feedback}"
        )
    raw = _call_master_llm(fallback_chain, user_msg, log_fn, stop_event)
    try:
        return _parse_json(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Master agent returned invalid JSON: {e}\n\nRaw:\n{raw}")


def evaluate(
    task: str, criteria: str, outputs: str,
    fallback_chain: list[dict],
    log_fn: Callable[[str], None] | None = None,
    stop_event: threading.Event | None = None,
) -> dict:
    prompt = EVALUATION_PROMPT.format(
        task=task, criteria=criteria, outputs=outputs[:4000]
    )
    eval_sys = "You are a quality evaluator. Respond only with JSON."
    raw = _call_with_fallback(fallback_chain, eval_sys, prompt, log_fn, stop_event)
    try:
        return _parse_json(raw)
    except json.JSONDecodeError:
        return {"satisfied": True, "score": 5, "feedback": "", "next_action": "done"}


# ── Provisioning ──────────────────────────────────────────────────────────────

def _pick_model_for_agent(
    agent_spec: dict,
    fallback_chain: list[dict],
) -> dict | None:
    """Pick the best model from the chain matching agent complexity."""
    complexity = agent_spec.get("complexity", "medium")
    rank_limits = {"low": 100, "medium": 60, "high": 30}
    limit = rank_limits.get(complexity, 100)

    # Try to find a model within rank limit first
    for mc in fallback_chain:
        if mc["intelligence_rank"] <= limit:
            return mc
    # Fall back to best available
    return fallback_chain[0] if fallback_chain else None


def provision_environment(env_name: str, db_name: str) -> int:
    for env in env_manager.list_environments(db_name=db_name):
        if env["name"] == env_name:
            return env["id"]
    ok, msg = env_manager.create_environment(
        env_name, "Auto-created by Master Agent", db_name=db_name
    )
    if not ok:
        raise RuntimeError(f"Could not create environment: {msg}")
    for env in env_manager.list_environments(db_name=db_name):
        if env["name"] == env_name:
            return env["id"]
    raise RuntimeError("Environment created but could not be retrieved.")


def provision_agents(
    plan_data: dict, env_id: int, fallback_chain: list[dict], db_name: str,
) -> dict[int, int]:
    all_tools = {t["name"]: t["id"] for t in tool_manager.list_tools(db_name=db_name)}
    idx_to_id = {}

    for idx, ag_spec in enumerate(plan_data.get("agents", [])):
        name   = ag_spec.get("name", f"AutoAgent_{idx}")
        prompt = ag_spec.get("system_prompt", "You are a helpful assistant.")
        tools  = ag_spec.get("tools", [])

        # Pick best model for this agent's complexity
        mc = _pick_model_for_agent(ag_spec, fallback_chain)
        api_url    = mc["api_url"]    if mc else "http://localhost:11434/v1"
        model_name = mc["model_id"]   if mc else "llama3"

        existing = agent_manager.get_agent_by_name(env_id, name, db_name=db_name)
        if existing:
            agent_id = existing["id"]
            # Update model config in case the registry changed
            agent_manager.update_agent(agent_id, api_url=api_url,
                                       model_name=model_name, db_name=db_name)
        else:
            ok, msg = agent_manager.create_agent(
                env_id, name, api_url, model_name, prompt, db_name=db_name
            )
            if not ok:
                raise RuntimeError(f"Could not create agent '{name}': {msg}")
            existing = agent_manager.get_agent_by_name(env_id, name, db_name=db_name)
            agent_id = existing["id"]
            for tool_name in tools:
                if tool_name in all_tools:
                    tool_manager.assign_tool(agent_id, all_tools[tool_name],
                                             "private", db_name=db_name)

        idx_to_id[idx] = agent_id
    return idx_to_id


# ── Execution engine ──────────────────────────────────────────────────────────

def _run_agent_safe(
    agent_id: int, env_id: int, run_id: int, message: str,
    callback: ResourceCallbackHandler, step_offset: int,
    db_name: str, username: str, log_fn: Callable | None,
) -> tuple[int, str]:
    try:
        output = run_single_agent(
            agent_id=agent_id, environment_id=env_id, run_id=run_id,
            user_message=message, callback=callback, step_offset=step_offset,
            db_name=db_name, username=username, log_fn=log_fn,
        )
        return agent_id, output
    except Exception as e:
        return agent_id, f"[ERROR] {e}"


def execute_plan(
    plan_data: dict, idx_to_id: dict[int, int], env_id: int, run_id: int,
    initial_msg: str, callback: ResourceCallbackHandler,
    db_name: str, username: str, log_fn: Callable | None,
    stop_event: threading.Event | None = None,
) -> dict[int, str]:
    pattern = plan_data.get("execution_pattern", "sequential")
    groups  = plan_data.get(
        "execution_order",
        [[i] for i in range(len(plan_data.get("agents", [])))]
    )

    outputs: dict[int, str] = {}
    current_input = initial_msg
    step_offset   = 0

    for group in groups:
        if stop_event and stop_event.is_set():
            break
        if len(group) == 1:
            idx = group[0]
            aid = idx_to_id.get(idx)
            if aid is None:
                continue
            name = plan_data["agents"][idx]["name"]
            if log_fn: log_fn(f"▶ Running **{name}**…")
            _, out = _run_agent_safe(aid, env_id, run_id, current_input,
                                     callback, step_offset, db_name, username, log_fn)
            outputs[idx] = out
            if "[ERROR]" in out:
                if log_fn: log_fn(f"⚠️ **{name}** failed. Circuit breaker tripped! Halting pipeline.")
                break
            
            current_input = f"Previous agent ({name}) output:\n{out}\n\nContinue with the task."
            step_offset += 10
        else:
            names = [plan_data["agents"][i]["name"] for i in group if i in idx_to_id]
            if log_fn: log_fn(f"⚡ Running in parallel: **{', '.join(names)}**…")
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(group)) as ex:
                futures = {
                    ex.submit(
                        _run_agent_safe,
                        idx_to_id[idx], env_id, run_id, current_input,
                        callback, step_offset + i * 2, db_name, username, log_fn
                    ): idx
                    for i, idx in enumerate(group) if idx in idx_to_id
                }
                for future in concurrent.futures.as_completed(futures):
                    plan_idx = futures[future]
                    _, out   = future.result()
                    outputs[plan_idx] = out
            step_offset += 10

    return outputs


def synthesize_outputs(
    outputs: dict[int, str], plan_data: dict, task: str,
    fallback_chain: list[dict], log_fn: Callable | None,
    stop_event: threading.Event | None = None,
) -> str:
    agents  = plan_data.get("agents", [])
    pattern = plan_data.get("execution_pattern", "sequential")

    if pattern != "parallel" or len(outputs) <= 1:
        last_idx = max(outputs.keys()) if outputs else 0
        return outputs.get(last_idx, "")

    parts = [
        f"=== {agents[idx]['name'] if idx < len(agents) else f'Agent {idx}'} ===\n{out}"
        for idx, out in sorted(outputs.items())
    ]
    combined  = "\n\n".join(parts)
    synth_ins = plan_data.get("synthesis_instruction", "Combine all outputs into a comprehensive answer.")
    prompt    = f"Task: {task}\n\nSynthesis instruction: {synth_ins}\n\nAgent outputs:\n{combined}"
    return _call_with_fallback(
        fallback_chain,
        "Synthesise the agent outputs into one coherent, complete answer.",
        prompt,
        log_fn,
        stop_event=stop_event,
    )


# ── Main orchestration loop ───────────────────────────────────────────────────

def run_auto(
    task:           str,
    env_name:       str,
    fallback_chain: list[dict],   # from model_manager.get_model_fallback_chain()
    max_calls:      int,
    timeout_secs:   int,
    db_name:        str,
    username:       str,
    stop_event:     threading.Event | None = None,
    log_fn:         Callable[[str], None] | None = None,
) -> dict:

    def _log(msg: str):
        if log_fn: log_fn(msg)

    if not fallback_chain:
        raise RuntimeError(
            "No active models in the Model Registry. "
            "Go to Settings → Model Registry and add at least one model."
        )

    # 1. Plan
    _log("🧠 Master agent planning…")
    current_plan = plan(task, fallback_chain, log_fn=log_fn, stop_event=stop_event)
    max_iter     = min(int(current_plan.get("max_iterations", 2)), 5)
    _log(f"📋 Pattern: {current_plan['execution_pattern']} · "
         f"{len(current_plan.get('agents', []))} agents · up to {max_iter} iteration(s)")

    # 2. Provision
    _log("🏗 Provisioning environment and agents…")
    env_id    = provision_environment(env_name, db_name)
    idx_to_id = provision_agents(current_plan, env_id, fallback_chain, db_name)

    # 3. Iterate
    final_answer, all_outputs, evaluation = "", {}, {}
    iteration, feedback, status = 0, "", "completed"

    for iteration in range(1, max_iter + 1):
        if stop_event and stop_event.is_set():
            status = "stopped"
            break

        _log(f"\n--- Iteration {iteration}/{max_iter} ---")
        callback = ResourceCallbackHandler(
            max_calls=max_calls, timeout_secs=timeout_secs, stop_event=stop_event,
        )
        callback.start_timeout()

        run_id = run_manager.create_run(env_id, config={
            "auto_mode": True, "task": task[:200],
            "iteration": iteration, "pattern": current_plan.get("execution_pattern"),
        }, db_name=db_name)

        try:
            initial = task if iteration == 1 else f"{task}\n\nFeedback:\n{feedback}"
            all_outputs = execute_plan(
                plan_data=current_plan, idx_to_id=idx_to_id, env_id=env_id,
                run_id=run_id, initial_msg=initial, callback=callback,
                db_name=db_name, username=username, log_fn=log_fn,
            )
            
            # Check if any sub-agent failed due to API credits / quota / rate limits / missing keys
            is_credit_err = False
            for out in all_outputs.values():
                if "[ERROR]" in out:
                    low_out = out.lower()
                    if any(t in low_out for t in ("402", "insufficient", "payment", "quota", "billing", "exhausted", "429", "rate limit", "too many requests", "no api keys", "500", "503", "internal", "unavailable")):
                        is_credit_err = True
                        break

            if is_credit_err:
                if len(fallback_chain) > 1:
                    dead_model = fallback_chain.pop(0)
                    if log_fn: log_fn(f"⚠️ Sub-agent hit API failure/quota limit on {dead_model['display_name']}. Re-provisioning agents with next model...")
                    idx_to_id = provision_agents(current_plan, env_id, fallback_chain, db_name)
                    # Force evaluation to trigger a replan/retry instantly without doing synthesis
                    evaluation = {"satisfied": False, "next_action": "replan", "feedback": "Previous execution failed due to model quota. Retry the exact same plan with the new fallback model."}
                    run_manager.update_run_status(run_id, "failed", db_name=db_name)
                    feedback = evaluation["feedback"]
                    continue
                else:
                    raise RuntimeError("Sub-agent hit quota limit and no fallback models remain.")
        except AgentStopException:
            status = "stopped"
            run_manager.update_run_status(run_id, "stopped", db_name=db_name)
            callback.cancel_timeout()
            break
        except Exception as e:
            _log(f"❌ Execution error: {e}")
            status = "failed"
            run_manager.update_run_status(run_id, "failed", db_name=db_name)
            callback.cancel_timeout()
            break
        finally:
            callback.cancel_timeout()

        if stop_event and stop_event.is_set():
            _log("🛑 Run stopped by user or iteration timed out.")
            status = "stopped"
            run_manager.update_run_status(run_id, "stopped", db_name=db_name)
            break

        run_manager.update_run_status(run_id, "completed", db_name=db_name)
        _log("🔀 Synthesising…")
        final_answer = synthesize_outputs(all_outputs, current_plan, task, fallback_chain, log_fn, stop_event=stop_event)
        _log("🔍 Evaluating…")
        evaluation = evaluate(task, current_plan.get("success_criteria", ""),
                               final_answer, fallback_chain, log_fn, stop_event)
        score = evaluation.get("score", "?")
        action = evaluation.get("next_action", "done")
        _log(f"Score: {score}/10 — {action}")

        if evaluation.get("satisfied") or action == "done" or iteration == max_iter:
            _log("✅ Done.")
            break

        feedback = evaluation.get("feedback", "")
        if action == "replan":
            _log("↩️ Re-planning…")
            current_plan = plan(task, fallback_chain, feedback=feedback, log_fn=log_fn, stop_event=stop_event)
            idx_to_id    = provision_agents(current_plan, env_id, fallback_chain, db_name)

    return {
        "status":       status,
        "plan":         current_plan,
        "outputs":      all_outputs,
        "final_answer": final_answer,
        "iterations":   iteration,
        "evaluation":   evaluation,
        "env_id":       env_id,
    }
