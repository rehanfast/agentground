"""
frontend/src/pages/1_Environments.py
Environment management — create, list, delete.
Changes: db_name routing, show_result() (no ternaries), sticky form defaults.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app._common import inject_css, render_sidebar, require_login, get_user_db, show_result
from backend.app.env_manager import create_environment, list_environments, delete_environment

st.set_page_config(page_title="Environments — AgentGround", layout="wide")
inject_css()
render_sidebar()
require_login()

db_name = get_user_db()

st.markdown("## Environments")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Each environment is an isolated workspace with its own agents, tools, run history, and audit log."
    "</span>", unsafe_allow_html=True,
)
st.divider()

# ── Sticky defaults initialisation ────────────────────────────────────────────
for key, default in [("env_form_name", ""), ("env_form_desc", "")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Create ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">New Environment</div>', unsafe_allow_html=True)
with st.form("create_env_form"):
    name = st.text_input(
        "Name", max_chars=100,
        placeholder="e.g. Research Pipeline",
        value=st.session_state["env_form_name"],
    )
    desc = st.text_area(
        "Description (optional)",
        placeholder="What is this environment for?",
        height=75,
        value=st.session_state["env_form_desc"],
    )
    submitted = st.form_submit_button("Create Environment", type="primary")

if submitted:
    # Save values so they survive rerun (sticky default on failure)
    st.session_state["env_form_name"] = name
    st.session_state["env_form_desc"] = desc

    ok, msg = create_environment(name, desc, db_name=db_name)
    show_result(ok, msg)
    if ok:
        # Clear sticky values after success
        st.session_state["env_form_name"] = ""
        st.session_state["env_form_desc"] = ""
        st.rerun()

st.divider()

# ── List ──────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">All Environments</div>', unsafe_allow_html=True)
environments = list_environments(db_name=db_name)

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
                ok, msg = delete_environment(env["id"], db_name=db_name)
                show_result(ok, msg)
                if ok:
                    del st.session_state[f"confirm_del_{env['id']}"]
                    st.rerun()
            if c2.button("Cancel", key=f"no_del_{env['id']}"):
                del st.session_state[f"confirm_del_{env['id']}"]
                st.rerun()
