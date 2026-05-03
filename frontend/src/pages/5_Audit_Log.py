"""
frontend/src/pages/5_Audit_Log.py
Audit log and trace viewer — browse every step of any run, export as JSON.
Changes: db_name routing to per-user DB.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app._common      import inject_css, render_sidebar, require_login, get_user_db
from backend.app.env_manager  import list_environments
from backend.app.run_manager  import get_runs_for_env
from backend.app.audit_logger import get_logs, export_json

st.set_page_config(page_title="Audit Log — AgentGround", layout="wide")
inject_css()
render_sidebar()
require_login()

db_name = get_user_db()

st.markdown("## Audit Log")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Every LLM request, tool call, and response is recorded here. "
    "Logs are immutable once written."
    "</span>", unsafe_allow_html=True,
)
st.divider()

# ── Selectors ─────────────────────────────────────────────────────────────────
environments = list_environments(db_name=db_name)
if not environments:
    st.warning("No environments found.")
    st.stop()

env_options  = {e["name"]: e["id"] for e in environments}
sel_env_name = st.selectbox("Environment", list(env_options.keys()))
sel_env_id   = env_options[sel_env_name]

runs = get_runs_for_env(sel_env_id, db_name=db_name)
if not runs:
    st.info(f"No runs in **{sel_env_name}** yet. Trigger a run on the Run page first.")
    st.stop()

run_labels = {
    f"Run {r['id']}  [{r['status']}]  —  {r['started_at'] or 'pending'}  "
    f"({r['log_count']} steps)": r["id"]
    for r in runs
}
sel_run_id = run_labels[st.selectbox("Run", list(run_labels.keys()))]

st.divider()

# ── Log ───────────────────────────────────────────────────────────────────────
logs = get_logs(sel_run_id, db_name=db_name)
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
    data=export_json(sel_run_id, db_name=db_name),
    file_name=f"agentground_run_{sel_run_id}.json",
    mime="application/json",
)

TAG_MAP = {
    "llm_request":  ("LLM REQUEST",  "tag-llm-req"),
    "llm_response": ("LLM RESPONSE", "tag-llm-resp"),
    "tool_call":    ("TOOL CALL",    "tag-tool"),
    "tool_result":  ("TOOL RESULT",  "tag-result"),
    "run_stopped":  ("STOPPED",      "tag-stop"),
    "run_error":    ("ERROR",        "tag-error"),
}

for log in logs:
    tag_text, tag_cls = TAG_MAP.get(
        log["action_type"],
        (log["action_type"].upper(), "tag-llm-req"),
    )
    with st.expander(
        f"Step {log['step_number']} — {log['action_type']} — {log['agent_name']}"
    ):
        st.markdown(
            f"<span class='step-tag {tag_cls}'>{tag_text}</span>"
            f"Step {log['step_number']}  ·  "
            f"<strong>{log['agent_name']}</strong>  ·  "
            f"<span style='color:#999;font-size:0.78rem;'>{log['created_at']}</span>",
            unsafe_allow_html=True,
        )

        payload = log.get("payload") or {}
        if not payload:
            st.caption("No payload recorded.")
        else:
            at = log["action_type"]
            if at == "llm_request":
                st.markdown(f"**Model:** `{payload.get('model', '—')}`")
                st.markdown(f"**Tools available:** {payload.get('tool_names', [])}")
                st.markdown("**System prompt:**")
                st.code(payload.get("system_prompt", ""), language="text")
                st.markdown("**User message:**")
                st.code(payload.get("user_message", ""), language="text")
            elif at == "llm_response":
                st.markdown("**Final answer:**")
                st.markdown(payload.get("final_answer", ""))
                st.caption(
                    f"Total LLM calls in this run: "
                    f"{payload.get('total_llm_calls', '—')}"
                )
            elif at == "tool_call":
                st.markdown(f"**Tool:** `{payload.get('tool', '—')}`")
                st.markdown("**Input:**")
                st.code(str(payload.get("input", "")), language="text")
            elif at == "tool_result":
                st.markdown("**Output:**")
                st.code(str(payload.get("output", "")), language="text")
            elif at in ("run_stopped", "run_error"):
                st.error(
                    payload.get("reason") or payload.get("error") or
                    "No detail recorded."
                )

            st.divider()
            st.markdown("**Raw JSON**")
            st.json(payload, expanded=False)
