"""
frontend/src/pages/7_Auto_Mode.py
Auto Mode — master orchestrator UI with live streaming progress.
"""

import sys, os, time, threading, queue
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app._common          import inject_css, render_sidebar, require_login, get_user_db, show_result
from backend.app.env_manager      import list_environments
from backend.app.settings_manager import get_all as get_settings
from backend.app.model_manager    import get_model_fallback_chain
from backend.app.auto_mode.master_agent import run_auto

st.set_page_config(page_title="Auto Mode — AgentGround", layout="wide")
inject_css()
render_sidebar()
require_login()

db_name  = get_user_db()
username = st.session_state.get("user", {}).get("username", "")


def _init(k, v):
    if k not in st.session_state:
        st.session_state[k] = v


st.markdown("## ⚡ Auto Mode")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Describe your goal. The Master Agent plans, provisions sub-agents, "
    "executes them, evaluates results, and iterates — automatically. "
    "Models are selected from your <a href='/6_Settings' target='_self'>Model Registry</a>."
    "</span>", unsafe_allow_html=True,
)
st.divider()

# ── Check registry ─────────────────────────────────────────────────────────────
all_models = get_model_fallback_chain(db_name=db_name, free_tier_only=False)
if not all_models:
    st.warning(
        "**No models configured.** "
        "Go to **Settings → Model Registry** and add at least one model."
    )
    st.page_link("pages/6_Settings.py", label="→ Open Model Registry")
    st.stop()

settings = get_settings(db_name=db_name)

_init("am_task",       "")
_init("am_free_only",  True)
_init("am_env_name",   "AutoMode")
_init("am_max_calls",  int(settings.get("max_calls_default", 20)))
_init("am_timeout",    int(settings.get("timeout_default", 120)) // 60 or 1)
_init("am_running",    False)
_init("am_result",     None)
_init("am_error",      None)
_init("am_log",        [])
_init("am_stop_event", None)
_init("am_result_q",   None)
_init("am_log_q",      None)

# ── Task input ────────────────────────────────────────────────────────────────
task = st.text_area(
    "What do you want to accomplish?", height=130,
    placeholder=(
        "Examples:\n"
        "• Research the latest developments in quantum computing and write a summary.\n"
        "• Write a Python script that scrapes the top 10 Hacker News posts.\n"
        "• Design a REST API for a todo-list app and document the endpoints."
    ),
    key="am_task_input",
)

# ── Settings ──────────────────────────────────────────────────────────────────
with st.expander("⚙️ Auto Mode Settings", expanded=False):
    am_free_only = st.toggle("Free-tier models only",
                              value=st.session_state["am_free_only"],
                              key="am_free_only_toggle")
    chain_preview = get_model_fallback_chain(db_name=db_name, free_tier_only=am_free_only)
    if chain_preview:
        st.caption(f"Fallback chain ({len(chain_preview)} model(s)):")
        for i, m in enumerate(chain_preview[:6]):
            badge = "🆓" if m["is_free_tier"] else "💰"
            st.caption(f"  {i+1}. {badge} **{m['display_name']}** (rank {m['intelligence_rank']})")
    else:
        st.warning("No models match filter.")

    env_mode = st.radio("Environment", ["Auto-create", "Use existing"],
                         horizontal=True, key="am_env_mode_r")
    if env_mode == "Auto-create":
        am_env_name = st.text_input("Environment name",
                                     value=st.session_state["am_env_name"],
                                     key="am_env_name_input")
    else:
        existing = list_environments(db_name=db_name)
        if existing:
            am_env_name = st.selectbox("Environment",
                                        [e["name"] for e in existing],
                                        key="am_env_sel")
        else:
            st.warning("No environments found — will auto-create.")
            am_env_name = st.session_state["am_env_name"]

    rc1, rc2 = st.columns(2)
    am_max_calls = rc1.number_input("Max API calls/run", min_value=1, max_value=500,
                                     value=st.session_state["am_max_calls"],
                                     key="am_max_calls_input")
    am_timeout_min = rc2.number_input("Timeout (min)", min_value=1, max_value=60,
                                     value=st.session_state["am_timeout"],
                                     key="am_timeout_input")

# Read from widget keys (safe whether expander is open or collapsed)
am_free_only = st.session_state.get("am_free_only_toggle", st.session_state["am_free_only"])
am_env_name  = st.session_state.get("am_env_name_input",   st.session_state["am_env_name"])
am_max_calls = st.session_state.get("am_max_calls_input",  st.session_state["am_max_calls"])
am_timeout_min = st.session_state.get("am_timeout_input",    st.session_state["am_timeout"])

st.divider()

# ── Controls ──────────────────────────────────────────────────────────────────
rb1, rb2, _ = st.columns([1, 1, 5])
_task_val   = (task or "").strip()
run_btn  = rb1.button("⚡ Run", type="primary",
                       disabled=bool(st.session_state.am_running) or not _task_val)
stop_btn = rb2.button("⏹ Stop", disabled=not st.session_state.am_running)

if stop_btn and st.session_state.am_stop_event:
    st.session_state.am_stop_event.set()
    st.warning("Stop signal sent to master agent.")

if run_btn and _task_val:
    st.session_state.update({
        "am_free_only": am_free_only,
        "am_env_name":  am_env_name,
        "am_max_calls": am_max_calls,
        "am_timeout":   am_timeout_min,
    })

    launch_chain = get_model_fallback_chain(db_name=db_name, free_tier_only=am_free_only)
    if not launch_chain:
        st.error("No models available. Add models in Settings → Model Registry.")
    else:
        stop_event = threading.Event()
        result_q   = queue.Queue()
        log_q      = queue.Queue()

        st.session_state.update({
            "am_running":    True,
            "am_result":     None,
            "am_error":      None,
            "am_log":        [],
            "am_stop_event": stop_event,
            "am_result_q":   result_q,
            "am_log_q":      log_q,
        })

        _db, _user, _chain       = db_name, username, launch_chain
        _env, _mc, _to, _task   = am_env_name, int(am_max_calls), int(am_timeout_min) * 60, _task_val

        def _worker():
            def _log(msg): log_q.put_nowait(msg)
            try:
                result = run_auto(
                    task=_task, env_name=_env, fallback_chain=_chain,
                    max_calls=_mc, timeout_secs=_to,
                    db_name=_db, username=_user,
                    stop_event=stop_event, log_fn=_log,
                )
                result_q.put(("ok", result))
            except Exception as exc:
                import traceback
                log_q.put_nowait(f"❌ Fatal error: {exc}")
                result_q.put(("err", f"{exc}\n{traceback.format_exc()}"))

        threading.Thread(target=_worker, daemon=True).start()
        st.rerun()

# ── Poll + live log ───────────────────────────────────────────────────────────
if st.session_state.am_running:
    lq = st.session_state.get("am_log_q")
    if lq:
        while True:
            try: st.session_state["am_log"].append(lq.get_nowait())
            except queue.Empty: break

    try:
        kind, payload = st.session_state.am_result_q.get_nowait()
        st.session_state.am_running = False
        if kind == "ok": st.session_state.am_result = payload
        else:            st.session_state.am_error  = payload
    except queue.Empty:
        pass

    # Live progress display
    st.markdown('<div class="section-hdr">Live Progress</div>', unsafe_allow_html=True)
    log_items = st.session_state["am_log"]
    if log_items:
        for msg in log_items[-40:]:
            st.markdown(msg)
    else:
        st.markdown("_Waiting for master agent to start…_")

    if st.session_state.am_running:
        with st.spinner(""):
            time.sleep(0.6)
        st.rerun()

# ── Error ─────────────────────────────────────────────────────────────────────
if st.session_state.am_error:
    st.error(f"Auto Mode failed:\n\n{st.session_state.am_error}")
    st.session_state.am_error = None

# ── Result ─────────────────────────────────────────────────────────────────────
if st.session_state.am_result:
    result = st.session_state.am_result
    fn = {"completed": st.success, "stopped": st.warning, "failed": st.error}
    fn.get(result.get("status","completed"), st.info)(
        f"Auto Mode {result.get('status','completed')} — {result.get('iterations',1)} iteration(s)"
    )

    if result.get("final_answer"):
        st.markdown('<div class="section-hdr">Final Answer</div>', unsafe_allow_html=True)
        st.markdown(result["final_answer"])

    ev = result.get("evaluation", {})
    if ev:
        c1, c2 = st.columns([1, 4])
        c1.metric("Quality Score", f"{ev.get('score','—')}/10")
        if ev.get("feedback"): c2.info(ev["feedback"])

    plan_data = result.get("plan", {})
    with st.expander("📋 Execution Plan", expanded=False):
        st.markdown(f"**Pattern:** `{plan_data.get('execution_pattern','—')}`")
        st.markdown(f"**Analysis:** {plan_data.get('task_analysis','—')}")
        for ag in plan_data.get("agents", []):
            st.markdown(f"- **{ag['name']}** `{ag.get('complexity','medium')}` — {ag.get('role','')}")

    outputs = result.get("outputs", {})
    agents_spec = plan_data.get("agents", [])
    if outputs:
        with st.expander("🤖 Agent Outputs", expanded=False):
            for idx, out in sorted(outputs.items()):
                name = agents_spec[idx]["name"] if idx < len(agents_spec) else f"Agent {idx}"
                st.markdown(f"**{name}:**")
                st.markdown(out)
                st.divider()

    if st.session_state["am_log"]:
        with st.expander("📜 Execution Log", expanded=False):
            for msg in st.session_state["am_log"]:
                st.markdown(msg)

    if st.button("Clear & Start New"):
        st.session_state.am_result = None
        st.session_state.am_log = []
        if "am_task_input" in st.session_state:
            st.session_state.pop("am_task_input")
        st.rerun()

# ── How it works ───────────────────────────────────────────────────────────────
with st.expander("ℹ️ How Auto Mode works", expanded=not st.session_state.am_result):
    st.markdown("""
**Planning** — The Master Agent analyses the task and produces a JSON plan:
agent roles, system prompts, tools, and execution pattern.

**Model Selection** — Each sub-agent gets the best model matching its complexity.
If a model errors, the next in the fallback chain is tried automatically.
Keys are rotated; rate-limited keys cool down for 65 seconds before retry.

**Patterns:** Sequential (pipeline), Parallel (concurrent + synthesis), Cyclic (refinement loop).

**Evaluation** — A separate LLM call scores the output (1-10). Low scores trigger re-iteration.

**Configure models** in **Settings → Model Registry**.
Store keys as the actual key value, or as an env var name like `GOOGLE_API_KEY` (resolved at runtime).
    """)
