"""
frontend/src/pages/2_Agents.py
Agent management — register, view, edit system prompt, delete.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager   import list_environments
from backend.app.agent_manager import (
    create_agent, list_agents, update_system_prompt, delete_agent
)

st.set_page_config(page_title="Agents — AgentGround", layout="wide")

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

st.markdown("## Agents")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Agents are external LLM endpoints registered within an environment. "
    "AgentGround calls them via their API — no model code runs locally."
    "</span>",
    unsafe_allow_html=True,
)
st.divider()

# ── Environment selector ──────────────────────────────────────────────────────
environments = list_environments()
if not environments:
    st.warning("No environments found. Create an environment first.")
    st.page_link("pages/1_Environments.py", label="Go to Environments")
    st.stop()

env_options       = {e["name"]: e["id"] for e in environments}
selected_env_name = st.selectbox("Environment", list(env_options.keys()))
selected_env_id   = env_options[selected_env_name]
st.divider()

# ── Register ──────────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Register New Agent</div>', unsafe_allow_html=True)
with st.form("register_agent_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    agent_name    = c1.text_input("Agent Name", placeholder="e.g. Researcher")
    model_name    = c2.text_input("Model Name", placeholder="e.g. gpt-4, llama3")
    api_url       = st.text_input("API Endpoint URL",
                                  placeholder="https://api.openai.com/v1  or  http://localhost:11434/v1")
    system_prompt = st.text_area("System Prompt", height=130,
                                 placeholder="You are a research assistant. Your job is to...")
    submitted = st.form_submit_button("Register Agent", type="primary")

if submitted:
    ok, msg = create_agent(selected_env_id, agent_name, api_url, model_name, system_prompt)
    if ok:
        st.success(msg)
        st.rerun()
    else:
        st.error(msg)

st.divider()

# ── Agent list ────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="section-hdr">Agents in {selected_env_name}</div>',
    unsafe_allow_html=True,
)
agents = list_agents(selected_env_id)

if not agents:
    st.info("No agents registered in this environment yet.")
else:
    for agent in agents:
        with st.expander(f"**{agent['name']}**  ·  {agent['model_name']}"):
            st.caption(
                f"ID: {agent['id']}   |   "
                f"Created: {agent['created_at']}   |   "
                f"Last edited: {agent['updated_at']}"
            )
            st.markdown(f"`{agent['api_url']}`")
            st.markdown("**System Prompt**")
            new_prompt = st.text_area(
                "system_prompt",
                value=agent["system_prompt"],
                height=110,
                key=f"prompt_{agent['id']}",
                label_visibility="collapsed",
            )
            cs, cd, _ = st.columns([1, 1, 5])
            if cs.button("Save", key=f"save_{agent['id']}", type="primary"):
                ok, msg = update_system_prompt(agent["id"], new_prompt)
                st.success(msg) if ok else st.error(msg)
                if ok:
                    st.rerun()
            if cd.button("Delete", key=f"del_ag_{agent['id']}"):
                st.session_state[f"confirm_ag_{agent['id']}"] = True

            if st.session_state.get(f"confirm_ag_{agent['id']}"):
                st.warning(f"Delete agent **{agent['name']}**? This cannot be undone.")
                ca2, cb2 = st.columns(2)
                if ca2.button("Confirm", key=f"yes_ag_{agent['id']}", type="primary"):
                    ok, msg = delete_agent(agent["id"])
                    if ok:
                        st.success(msg)
                        del st.session_state[f"confirm_ag_{agent['id']}"]
                        st.rerun()
                    else:
                        st.error(msg)
                if cb2.button("Cancel", key=f"no_ag_{agent['id']}"):
                    del st.session_state[f"confirm_ag_{agent['id']}"]
                    st.rerun()
