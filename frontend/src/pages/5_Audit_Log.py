"""
frontend/src/pages/5_Audit_Log.py
Audit log and trace viewer — browse every step of any run, export as JSON.
"""

import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager  import list_environments
from backend.app.run_manager  import get_runs_for_env
from backend.app.audit_logger import get_logs, export_json

st.set_page_config(page_title="Audit Log — AgentGround", layout="wide")

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
.step-tag {
    display:inline-block; padding:0.15rem 0.5rem; border-radius:4px;
    font-size:0.70rem; font-weight:600; letter-spacing:0.04em; margin-right:0.3rem;
}
.tag-llm-req  { background:#EAF2FB; color:#1A4F7C; }
.tag-llm-resp { background:#E8F8F5; color:#0E6655; }
.tag-tool     { background:#FEF9E7; color:#7D6608; }
.tag-result   { background:#D4EDDA; color:#1A5C2A; }
.tag-stop     { background:#FEF9E7; color:#7D6608; }
.tag-error    { background:#FADBD8; color:#7B241C; }
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

st.markdown("## Audit Log")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Every LLM request, tool call, and response is recorded here. "
    "Logs are immutable once written."
    "</span>",
    unsafe_allow_html=True,
)
st.divider()

# ── Selectors ─────────────────────────────────────────────────────────────────
environments = list_environments()
if not environments:
    st.warning("No environments found.")
    st.stop()

env_options  = {e["name"]: e["id"] for e in environments}
sel_env_name = st.selectbox("Environment", list(env_options.keys()))
sel_env_id   = env_options[sel_env_name]

runs = get_runs_for_env(sel_env_id)
if not runs:
    st.info(f"No runs in **{sel_env_name}** yet. Trigger a run on the Run page first.")
    st.stop()

cls_map = {
    "completed": "pill-ok", "running": "pill-run",
    "failed": "pill-fail",  "stopped": "pill-stop",
}
run_labels = {}
for r in runs:
    cls = cls_map.get(r["status"], "pill-run")
    label = f"Run {r['id']}  [{r['status']}]  —  {r['started_at'] or 'pending'}  ({r['log_count']} steps)"
    run_labels[label] = r["id"]

sel_run_label = st.selectbox("Run", list(run_labels.keys()))
sel_run_id    = run_labels[sel_run_label]

st.divider()

# ── Log ───────────────────────────────────────────────────────────────────────
logs = get_logs(sel_run_id)

if not logs:
    st.info("No log entries for this run. It may have failed before any steps were recorded.")
    st.stop()

hdr_col, export_col = st.columns([4, 1])
hdr_col.markdown(
    f'<div class="section-hdr">Trace — {len(logs)} step(s)  ·  Run {sel_run_id}</div>',
    unsafe_allow_html=True,
)
export_col.download_button(
    label="Export JSON",
    data=export_json(sel_run_id),
    file_name=f"agentground_run_{sel_run_id}.json",
    mime="application/json",
)

# Tag styles by action type
TAG_MAP = {
    "llm_request":  ("LLM REQUEST",  "tag-llm-req"),
    "llm_response": ("LLM RESPONSE", "tag-llm-resp"),
    "tool_call":    ("TOOL CALL",     "tag-tool"),
    "tool_result":  ("TOOL RESULT",   "tag-result"),
    "run_stopped":  ("STOPPED",       "tag-stop"),
    "run_error":    ("ERROR",         "tag-error"),
}

for log in logs:
    tag_text, tag_cls = TAG_MAP.get(log["action_type"], (log["action_type"].upper(), "tag-llm-req"))
    header_html = (
        f"<span class='step-tag {tag_cls}'>{tag_text}</span>"
        f"Step {log['step_number']}  ·  "
        f"<strong>{log['agent_name']}</strong>  ·  "
        f"<span style='color:#999;font-size:0.78rem;'>{log['created_at']}</span>"
    )
    with st.expander(f"Step {log['step_number']} — {log['action_type']} — {log['agent_name']}"):
        st.markdown(header_html, unsafe_allow_html=True)

        payload = log.get("payload") or {}
        if not payload:
            st.caption("No payload recorded.")
        else:
            at = log["action_type"]
            if at == "llm_request":
                st.markdown(f"**Model:** `{payload.get('model', '—')}`")
                st.markdown(f"**Tools available:** {payload.get('tool_names', [])}")
                st.markdown("**User message:**")
                st.code(payload.get("user_message", ""), language="text")

            elif at == "llm_response":
                st.markdown("**Final answer:**")
                st.markdown(payload.get("final_answer", ""))
                st.caption(f"Total LLM calls in this run: {payload.get('total_llm_calls', '—')}")

            elif at == "tool_call":
                st.markdown(f"**Tool:** `{payload.get('tool', '—')}`")
                st.markdown("**Input:**")
                st.code(str(payload.get("input", "")), language="text")

            elif at == "tool_result":
                st.markdown("**Output:**")
                st.code(str(payload.get("output", "")), language="text")

            elif at in ("run_stopped", "run_error"):
                msg = payload.get("reason") or payload.get("error") or "No detail recorded."
                st.error(msg)

            st.divider()
            st.markdown("**Raw JSON**")
            st.json(payload, expanded=False)
