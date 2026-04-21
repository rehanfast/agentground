"""
frontend/src/pages/4_Run.py
Run execution — trigger single or multi-agent runs with resource governance.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager    import list_environments
from backend.app.agent_manager  import list_agents
from backend.app.run_manager    import create_run, update_run_status, get_runs_for_env
from backend.app.agent_executor import run_sequential

st.set_page_config(page_title="Run — AgentGround", layout="wide")

st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none; }
.ag-brand h2 { font-size:1.15rem; font-weight:700; color:#1B3A6B; margin:0 0 0.15rem 0; }
.ag-brand p  { font-size:0.72rem; color:#6B7A99; margin:0; text-transform:uppercase; letter-spacing:0.07em; }
.section-hdr {
    font-size:0.74rem; font-weight:600; color:#6B7A99; text-transform:uppercase;
    letter-spacing:0.09em; margin:1.4rem 0 0.5rem 0;
    border-bottom:1px solid #E2EDF7; padding-bottom:0.3rem;
}
.pill { display:inline-block; padding:0.18rem 0.55rem; border-radius:20px;
        font-size:0.72rem; font-weight:600; }
.pill-ok   { background:#D4EDDA; color:#1A5C2A; }
.pill-run  { background:#D6EAF8; color:#1A4F7C; }
.pill-fail { background:#FADBD8; color:#7B241C; }
.pill-stop { background:#FEF9E7; color:#7D6608; }
.run-output {
    background:#F4F8FD; border:1px solid #D6E8F5; border-radius:6px;
    padding:1rem 1.2rem; font-size:0.88rem; line-height:1.6;
    white-space:pre-wrap; word-break:break-word;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown('<div class="ag-brand"><h2>AgentGround</h2><p>AI Agent Sandbox</p></div>',
                unsafe_allow_html=True)
    st.divider()
    st.page_link("app.py",                  label="Home")
    st.page_link("pages/1_Environments.py", label="Environments")
    st.page_link("pages/2_Agents.py",       label="Agents")
    st.page_link("pages/3_Tools.py",        label="Tools")
    st.page_link("pages/4_Run.py",          label="Run")
    st.page_link("pages/5_Audit_Log.py",    label="Audit Log")
    st.divider()
    st.caption("Rehan Abid · 24L-2573\nFundamentals of SE · Spring 2026")

st.markdown("## Run")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Trigger agent runs, set resource limits, and monitor execution. "
    "In multi-agent mode each agent receives the previous agent's output as its next input."
    "</span>",
    unsafe_allow_html=True,
)
st.divider()

# ── Environment ───────────────────────────────────────────────────────────────
environments = list_environments()
if not environments:
    st.warning("No environments found. Create an environment first.")
    st.stop()

env_options  = {e["name"]: e["id"] for e in environments}
sel_env_name = st.selectbox("Environment", list(env_options.keys()))
sel_env_id   = env_options[sel_env_name]

agents = list_agents(sel_env_id)
if not agents:
    st.warning(f"No agents registered in **{sel_env_name}**. Register agents first.")
    st.stop()

st.divider()

# ── Configuration ─────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Run Configuration</div>', unsafe_allow_html=True)

agent_map  = {a["name"]: a["id"] for a in agents}
sel_agents = st.multiselect(
    "Agent(s) — select multiple for a sequential pipeline",
    list(agent_map.keys()),
    default=[list(agent_map.keys())[0]],
)
if not sel_agents:
    st.info("Select at least one agent.")
    st.stop()

user_msg = st.text_area("Initial message", height=110,
                        placeholder="What task should the agent(s) perform?")

c1, c2 = st.columns(2)
max_calls   = c1.number_input("Max API calls per run", min_value=1, max_value=100, value=10)
timeout_sec = c2.number_input("Timeout (seconds)",     min_value=5, max_value=300, value=60)

if len(sel_agents) > 1:
    st.caption(
        f"Multi-agent run: {' → '.join(sel_agents)}. "
        "Each agent receives the previous agent's final answer prepended to its input."
    )

st.divider()

# ── Controls ──────────────────────────────────────────────────────────────────
c_run, c_stop, _ = st.columns([1, 1, 5])
run_btn  = c_run.button("Run",  type="primary", disabled=not user_msg.strip())
stop_btn = c_stop.button("Stop", disabled=not st.session_state.get("run_active", False))

if stop_btn:
    st.session_state["stop_flag"] = True
    st.warning("Stop requested. The agent will halt at the next step boundary.")

# ── Execute ───────────────────────────────────────────────────────────────────
if run_btn and user_msg.strip():
    agent_ids = [agent_map[n] for n in sel_agents]
    run_id    = create_run(sel_env_id)

    st.session_state.update({
        "run_active":      True,
        "stop_flag":       False,
        "current_run_id":  run_id,
    })

    with st.spinner(f"Running — Run ID: {run_id}"):
        try:
            result = run_sequential(
                agent_ids=agent_ids,
                environment_id=sel_env_id,
                run_id=run_id,
                initial_message=user_msg,
                max_calls=max_calls,
                timeout_secs=timeout_sec,
            )
        except Exception as exc:
            update_run_status(run_id, "failed")
            st.session_state["run_active"] = False
            st.error(f"Run failed unexpectedly: {exc}")
            st.stop()

    st.session_state["run_active"] = False
    status = result["status"]

    status_msg = {
        "completed": ("success", f"Run {run_id} completed."),
        "stopped":   ("warning", f"Run {run_id} was stopped."),
        "failed":    ("error",   f"Run {run_id} failed."),
    }.get(status, ("info", f"Run {run_id} finished with status: {status}."))

    getattr(st, status_msg[0])(status_msg[1])

    for r in result["results"]:
        agent_name = next((a["name"] for a in agents if a["id"] == r["agent_id"]), "Unknown")
        with st.expander(f"Output — {agent_name}", expanded=True):
            st.markdown(
                f'<div class="run-output">{r["output"]}</div>',
                unsafe_allow_html=True,
            )

    st.info(f"Full step-by-step trace available on the **Audit Log** page — Run ID: {run_id}")

# ── Run history ───────────────────────────────────────────────────────────────
st.divider()
st.markdown(
    f'<div class="section-hdr">Run History — {sel_env_name}</div>',
    unsafe_allow_html=True,
)
runs = get_runs_for_env(sel_env_id)

if not runs:
    st.info("No runs yet in this environment.")
else:
    cls_map = {
        "completed": "pill-ok", "running": "pill-run",
        "failed": "pill-fail",  "stopped": "pill-stop",
    }
    header = st.columns([1, 2, 3, 2, 1])
    for col, h in zip(header, ["Run ID", "Status", "Started", "Steps", ""]):
        col.markdown(f"<small style='color:#999;font-weight:600;'>{h}</small>",
                     unsafe_allow_html=True)
    for run in runs[:15]:
        cls = cls_map.get(run["status"], "pill-run")
        c1, c2, c3, c4, c5 = st.columns([1, 2, 3, 2, 1])
        c1.write(run["id"])
        c2.markdown(
            f"<span class='pill {cls}'>{run['status']}</span>",
            unsafe_allow_html=True,
        )
        c3.caption(run["started_at"] or "—")
        c4.caption(str(run["log_count"]))
        c5.page_link("pages/5_Audit_Log.py", label="Trace")
