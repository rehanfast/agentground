"""
frontend/src/pages/1_Environments.py
Environments management page — Create, List, Delete.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager import (
    create_environment, list_environments, delete_environment
)

st.set_page_config(page_title="Environments — AgentGround", page_icon="🌍", layout="wide")

with st.sidebar:
    st.markdown("## 🤖 AgentGround")
    st.markdown("*AI Agent Sandbox Platform*")
    st.divider()
    st.page_link("app.py",                   label="🏠 Home")
    st.page_link("pages/1_Environments.py",  label="🌍 Environments")
    st.page_link("pages/2_Agents.py",        label="🤖 Agents")
    st.page_link("pages/3_Tools.py",         label="🔧 Tools")

st.title("🌍 Environments")
st.markdown("Environments are isolated sandboxes. Each has its own agents, tools, and audit logs.")
st.divider()

# ─── Create Environment Form ──────────────────────────────────────────────────
st.subheader("Create New Environment")
with st.form("create_env_form", clear_on_submit=True):
    name  = st.text_input("Environment Name *", max_chars=100,
                           placeholder="e.g. Research Pipeline")
    desc  = st.text_area("Description (optional)",
                          placeholder="Briefly describe what this environment is for.")
    submitted = st.form_submit_button("💾 Save Environment", type="primary")

if submitted:
    ok, msg = create_environment(name, desc)
    if ok:
        st.success(msg)
        st.rerun()
    else:
        st.error(msg)

st.divider()

# ─── Environment List ─────────────────────────────────────────────────────────
st.subheader("All Environments")
environments = list_environments()

if not environments:
    st.info("No environments yet. Create your first one above ☝️")
else:
    for env in environments:
        col_info, col_del = st.columns([5, 1])
        with col_info:
            with st.expander(f"🌍  **{env['name']}**  —  {env['agent_count']} agent(s)"):
                st.write(env["description"] or "*No description provided.*")
                st.caption(f"ID: {env['id']}   |   Created: {env['created_at']}")
        with col_del:
            if st.button("🗑️ Delete", key=f"del_env_{env['id']}"):
                st.session_state[f"confirm_del_{env['id']}"] = True

        # Confirmation prompt
        if st.session_state.get(f"confirm_del_{env['id']}"):
            st.warning(
                f"Are you sure you want to delete **{env['name']}**? "
                f"This will also delete all agents and data inside it."
            )
            c1, c2 = st.columns(2)
            if c1.button("✅ Yes, delete", key=f"yes_del_{env['id']}", type="primary"):
                ok, msg = delete_environment(env["id"])
                if ok:
                    st.success(msg)
                    del st.session_state[f"confirm_del_{env['id']}"]
                    st.rerun()
                else:
                    st.error(msg)
            if c2.button("❌ Cancel", key=f"no_del_{env['id']}"):
                del st.session_state[f"confirm_del_{env['id']}"]
                st.rerun()
st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)
