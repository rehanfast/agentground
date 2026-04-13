"""
frontend/src/pages/5_Audit_Log.py
Audit log viewer — browse run steps, expand payloads, export JSON.
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager  import list_environments
from backend.app.run_manager  import get_runs_for_env
from backend.app.audit_logger import get_logs, export_json

st.set_page_config(page_title="Audit Log — AgentGround", page_icon="📋", layout="wide")

with st.sidebar:
    st.markdown("## 🤖 AgentGround")
    st.divider()
    st.page_link("app.py",                   label="🏠 Home")
    st.page_link("pages/1_Environments.py",  label="🌍 Environments")
    st.page_link("pages/2_Agents.py",        label="🤖 Agents")
    st.page_link("pages/3_Tools.py",         label="🔧 Tools")
    st.page_link("pages/4_Run.py",           label="▶️ Run")
    st.page_link("pages/5_Audit_Log.py",     label="📋 Audit Log")

st.title("📋 Audit Log & Trace Viewer")
st.markdown("Inspect every step of any agent run — tool calls, LLM requests, responses, and errors.")
st.divider()

# ─── Environment selector ────────────────────────────────────────────────────
environments = list_environments()
if not environments:
    st.warning("No environments found.")
    st.stop()

env_options  = {e["name"]: e["id"] for e in environments}
sel_env_name = st.selectbox("Select Environment", list(env_options.keys()))
sel_env_id   = env_options[sel_env_name]

# ─── Run selector ────────────────────────────────────────────────────────────
runs = get_runs_for_env(sel_env_id)
if not runs:
    st.info(f"No runs found in **{sel_env_name}** yet. Trigger a run on the Run page first.")
    st.stop()

STATUS_ICON = {"completed":"✅","running":"🔄","stopped":"⏹️","failed":"❌","pending":"⏳"}
run_labels  = {
    f"{STATUS_ICON.get(r['status'],'?')} Run {r['id']}  [{r['status']}]  —  {r['started_at'] or 'pending'}  ({r['log_count']} steps)": r["id"]
    for r in runs
}
sel_run_label = st.selectbox("Select Run", list(run_labels.keys()))
sel_run_id    = run_labels[sel_run_label]

st.divider()

# ─── Fetch and display log ────────────────────────────────────────────────────
logs = get_logs(sel_run_id)

if not logs:
    st.info("No log entries found for this run. The run may have failed before any steps were logged.")
    st.stop()

ACTION_ICONS = {
    "llm_request":  "📤",
    "llm_response": "📥",
    "tool_call":    "🔧",
    "tool_result":  "✅",
    "run_stopped":  "⏹️",
    "run_error":    "❌",
}

col_exp, col_dl = st.columns([4, 1])
col_exp.markdown(f"### Trace — {len(logs)} step(s)")

# Export button
json_str = export_json(sel_run_id)
col_dl.download_button(
    label="⬇️ Export JSON",
    data=json_str,
    file_name=f"agentground_run_{sel_run_id}_audit.json",
    mime="application/json",
)

for log in logs:
    icon  = ACTION_ICONS.get(log["action_type"], "❓")
    label = (
        f"{icon}  **Step {log['step_number']}** — "
        f"`{log['action_type']}` — "
        f"Agent: **{log['agent_name']}** — "
        f"{log['created_at']}"
    )
    with st.expander(label):
        payload = log["payload"]
        if not payload:
            st.caption("No payload recorded for this step.")
        else:
            # Show a human-readable summary based on action type
            if log["action_type"] == "llm_request":
                st.markdown("**Model:** " + payload.get("model", "—"))
                st.markdown("**User Message:**")
                st.code(payload.get("user_message", ""), language="text")
                st.caption(f"Tools available: {payload.get('tool_names', [])}")

            elif log["action_type"] == "llm_response":
                st.markdown("**Final Answer:**")
                st.write(payload.get("final_answer", ""))
                st.caption(f"Total LLM calls in run: {payload.get('total_llm_calls', '—')}")

            elif log["action_type"] == "tool_call":
                st.markdown(f"**Tool:** `{payload.get('tool', '—')}`")
                st.markdown("**Input:**")
                st.code(str(payload.get("input", "")), language="text")

            elif log["action_type"] == "tool_result":
                st.markdown("**Output:**")
                st.code(str(payload.get("output", "")), language="text")

            elif log["action_type"] in ("run_stopped", "run_error"):
                st.error(payload.get("reason") or payload.get("error") or "No details.")

            # Always show raw JSON at the bottom
            with st.expander("🔍 Raw JSON payload"):
                st.json(payload)
