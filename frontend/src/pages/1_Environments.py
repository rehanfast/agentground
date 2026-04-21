"""
frontend/src/pages/1_Environments.py
Environment management — create, list, delete.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager import create_environment, list_environments, delete_environment

st.set_page_config(page_title="Environments — AgentGround", layout="wide")

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

st.markdown("## Environments")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Each environment is an isolated workspace with its own agents, tools, run history, and audit log."
    "</span>",
    unsafe_allow_html=True,
)
st.divider()

# ── Create ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">New Environment</div>', unsafe_allow_html=True)
with st.form("create_env_form", clear_on_submit=True):
    name = st.text_input("Name", max_chars=100, placeholder="e.g. Research Pipeline")
    desc = st.text_area("Description (optional)",
                        placeholder="What is this environment for?", height=80)
    submitted = st.form_submit_button("Create Environment", type="primary")

if submitted:
    ok, msg = create_environment(name, desc)
    if ok:
        st.success(msg)
        st.rerun()
    else:
        st.error(msg)

st.divider()

# ── List ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">All Environments</div>', unsafe_allow_html=True)
environments = list_environments()

if not environments:
    st.info("No environments yet. Create one above.")
else:
    for env in environments:
        col_info, col_del = st.columns([6, 1])
        with col_info:
            with st.expander(f"**{env['name']}** — {env['agent_count']} agent(s)"):
                if env["description"]:
                    st.write(env["description"])
                st.caption(f"ID: {env['id']}   |   Created: {env['created_at']}")
        with col_del:
            if st.button("Delete", key=f"del_env_{env['id']}"):
                st.session_state[f"confirm_del_{env['id']}"] = True

        if st.session_state.get(f"confirm_del_{env['id']}"):
            st.warning(
                f"Delete **{env['name']}**? "
                "All agents, runs, and audit logs inside it will also be removed."
            )
            c1, c2 = st.columns(2)
            if c1.button("Confirm", key=f"yes_del_{env['id']}", type="primary"):
                ok, msg = delete_environment(env["id"])
                if ok:
                    st.success(msg)
                    del st.session_state[f"confirm_del_{env['id']}"]
                    st.rerun()
                else:
                    st.error(msg)
            if c2.button("Cancel", key=f"no_del_{env['id']}"):
                del st.session_state[f"confirm_del_{env['id']}"]
                st.rerun()
