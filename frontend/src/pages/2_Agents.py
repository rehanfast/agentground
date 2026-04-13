"""
frontend/src/pages/2_Agents.py
Agents management page — Register, List, Edit system prompt, Delete.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager   import list_environments
from backend.app.agent_manager import (
    create_agent, list_agents, get_agent,
    update_system_prompt, delete_agent
)

st.set_page_config(page_title="Agents — AgentGround", page_icon="🤖", layout="wide")

with st.sidebar:
    st.markdown("## 🤖 AgentGround")
    st.markdown("*AI Agent Sandbox Platform*")
    st.divider()
    st.page_link("app.py",                   label="🏠 Home")
    st.page_link("pages/1_Environments.py",  label="🌍 Environments")
    st.page_link("pages/2_Agents.py",        label="🤖 Agents")
    st.page_link("pages/3_Tools.py",         label="🔧 Tools")

st.title("🤖 Agents")
st.markdown("Register AI agents by providing their API endpoint and a system prompt.")
st.divider()

# ─── Environment selector ────────────────────────────────────────────────────
environments = list_environments()
if not environments:
    st.warning("No environments found. Please create an environment first.")
    st.page_link("pages/1_Environments.py", label="➡️ Go to Environments")
    st.stop()

env_options = {e["name"]: e["id"] for e in environments}
selected_env_name = st.selectbox("Select Environment", list(env_options.keys()))
selected_env_id   = env_options[selected_env_name]

st.divider()

# ─── Register Agent Form ──────────────────────────────────────────────────────
st.subheader(f"Register New Agent in: {selected_env_name}")
with st.form("register_agent_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    agent_name  = col1.text_input("Agent Name *",   placeholder="e.g. Researcher Agent")
    model_name  = col2.text_input("Model Name *",   placeholder="e.g. gpt-4, claude-3-sonnet")
    api_url     = st.text_input( "API Endpoint URL *",
                                  placeholder="https://api.openai.com/v1")
    system_prompt = st.text_area("System Prompt *", height=150,
                                  placeholder="You are a research assistant. Your job is to...")
    submitted = st.form_submit_button("💾 Register Agent", type="primary")

if submitted:
    ok, msg = create_agent(selected_env_id, agent_name, api_url, model_name, system_prompt)
    if ok:
        st.success(msg)
        st.rerun()
    else:
        st.error(msg)

st.divider()

# ─── Agent List ───────────────────────────────────────────────────────────────
st.subheader(f"Agents in: {selected_env_name}")
agents = list_agents(selected_env_id)

if not agents:
    st.info("No agents registered in this environment yet. Register one above ☝️")
else:
    for agent in agents:
        with st.expander(f"🤖  **{agent['name']}**  |  Model: {agent['model_name']}"):
            st.caption(f"ID: {agent['id']}   |   Created: {agent['created_at']}   |   Updated: {agent['updated_at']}")
            st.markdown(f"**API URL:** `{agent['api_url']}`")

            # Prompt editor
            st.markdown("**System Prompt:**")
            new_prompt = st.text_area(
                "Edit system prompt",
                value=agent["system_prompt"],
                height=120,
                key=f"prompt_{agent['id']}",
                label_visibility="collapsed",
            )
            col_save, col_del, _ = st.columns([1, 1, 4])
            if col_save.button("💾 Save Changes", key=f"save_{agent['id']}", type="primary"):
                ok, msg = update_system_prompt(agent["id"], new_prompt)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)

            if col_del.button("🗑️ Delete Agent", key=f"del_ag_{agent['id']}"):
                st.session_state[f"confirm_del_ag_{agent['id']}"] = True

            if st.session_state.get(f"confirm_del_ag_{agent['id']}"):
                st.warning(f"Delete agent **{agent['name']}**? This cannot be undone.")
                c1, c2 = st.columns(2)
                if c1.button("✅ Confirm", key=f"yes_ag_{agent['id']}", type="primary"):
                    ok, msg = delete_agent(agent["id"])
                    if ok:
                        st.success(msg)
                        del st.session_state[f"confirm_del_ag_{agent['id']}"]
                        st.rerun()
                    else:
                        st.error(msg)
                if c2.button("❌ Cancel", key=f"no_ag_{agent['id']}"):
                    del st.session_state[f"confirm_del_ag_{agent['id']}"]
                    st.rerun()
st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)
