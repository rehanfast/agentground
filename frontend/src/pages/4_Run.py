"""
frontend/src/pages/4_Run.py
Run execution page — Trigger single or multi-agent runs with resource limits.
"""

import sys, os, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager   import list_environments
from backend.app.agent_manager import list_agents
from backend.app.run_manager   import create_run, update_run_status, get_runs_for_env
from backend.app.agent_executor import run_sequential

st.set_page_config(page_title="Run — AgentGround", page_icon="▶️", layout="wide")

with st.sidebar:
    st.markdown("## 🤖 AgentGround")
    st.divider()
    st.page_link("app.py",                   label="🏠 Home")
    st.page_link("pages/1_Environments.py",  label="🌍 Environments")
    st.page_link("pages/2_Agents.py",        label="🤖 Agents")
    st.page_link("pages/3_Tools.py",         label="🔧 Tools")
    st.page_link("pages/4_Run.py",           label="▶️ Run")
    st.page_link("pages/5_Audit_Log.py",     label="📋 Audit Log")

st.title("▶️ Run Agents")
st.markdown("Configure a run, set resource limits, then trigger one or more agents.")
st.divider()

# ─── Environment selector ────────────────────────────────────────────────────
environments = list_environments()
if not environments:
    st.warning("No environments found. Please create an environment first.")
    st.stop()

env_options     = {e["name"]: e["id"] for e in environments}
sel_env_name    = st.selectbox("Select Environment", list(env_options.keys()))
sel_env_id      = env_options[sel_env_name]

agents = list_agents(sel_env_id)
if not agents:
    st.warning(f"No agents in **{sel_env_name}**. Register agents first.")
    st.stop()

# ─── Agent selector ──────────────────────────────────────────────────────────
st.subheader("Agent Selection")
agent_map   = {a["name"]: a["id"] for a in agents}
sel_agents  = st.multiselect(
    "Select agent(s) — for multi-agent runs, order matters",
    list(agent_map.keys()),
    default=[list(agent_map.keys())[0]],
    help="For multi-agent runs, each agent receives the previous agent's output as its input.",
)

if not sel_agents:
    st.info("Select at least one agent to run.")
    st.stop()

# ─── User message ────────────────────────────────────────────────────────────
st.subheader("User Message")
user_msg = st.text_area(
    "Initial message to send to the agent(s)",
    height=120,
    placeholder="What task should the agent(s) perform?"
)

# ─── Resource limits ─────────────────────────────────────────────────────────
st.subheader("Resource Limits")
col1, col2 = st.columns(2)
max_calls   = col1.number_input("Max API Calls", min_value=1, max_value=100, value=10,
                                 help="Maximum number of LLM API calls per run.")
timeout_sec = col2.number_input("Timeout (seconds)", min_value=5, max_value=300, value=60,
                                 help="Run is halted if it exceeds this wall-clock time.")

st.divider()

# ─── Run control ─────────────────────────────────────────────────────────────
col_run, col_stop, _ = st.columns([1, 1, 4])

run_clicked  = col_run.button("▶️ Run", type="primary",
                               disabled=not user_msg.strip())
stop_clicked = col_stop.button("⏹️ Stop",
                                disabled=not st.session_state.get("run_active", False))

if stop_clicked:
    st.session_state["stop_flag"] = True
    st.warning("Stop requested. The agent will halt at the next step.")

# ─── Execute run ─────────────────────────────────────────────────────────────
if run_clicked and user_msg.strip():
    agent_ids = [agent_map[name] for name in sel_agents]
    run_id    = create_run(sel_env_id)

    st.session_state["run_active"] = True
    st.session_state["stop_flag"]  = False
    st.session_state["current_run_id"] = run_id

    with st.spinner(f"Running {len(agent_ids)} agent(s)... (Run ID: {run_id})"):
        try:
            result = run_sequential(
                agent_ids=agent_ids,
                environment_id=sel_env_id,
                run_id=run_id,
                initial_message=user_msg,
                max_calls=max_calls,
                timeout_secs=timeout_sec,
            )
        except Exception as e:
            update_run_status(run_id, "failed")
            st.error(f"Run failed with an unexpected error: {e}")
            st.session_state["run_active"] = False
            st.stop()

    st.session_state["run_active"] = False

    # Display results
    status = result["status"]
    if status == "completed":
        st.success(f"✅ Run {run_id} completed successfully.")
    elif status == "stopped":
        st.warning(f"⏹️ Run {run_id} was stopped.")
    else:
        st.error(f"❌ Run {run_id} failed.")

    for r in result["results"]:
        agent_name = next((a["name"] for a in agents if a["id"] == r["agent_id"]), "Unknown")
        with st.expander(f"🤖 **{agent_name}** output", expanded=True):
            st.write(r["output"])

    st.info(f"📋 View the full audit trace on the **Audit Log** page (Run ID: {run_id})")

st.divider()

# ─── Recent runs ─────────────────────────────────────────────────────────────
st.subheader(f"Recent Runs — {sel_env_name}")
runs = get_runs_for_env(sel_env_id)

STATUS_ICON = {
    "completed": "✅", "running": "🔄", "stopped": "⏹️",
    "failed": "❌", "pending": "⏳"
}

if not runs:
    st.info("No runs yet in this environment.")
else:
    for run in runs[:10]:
        icon = STATUS_ICON.get(run["status"], "❓")
        st.markdown(
            f"{icon} **Run {run['id']}** — `{run['status']}`  |  "
            f"Started: {run['started_at'] or '—'}  |  "
            f"Steps logged: {run['log_count']}"
        )
