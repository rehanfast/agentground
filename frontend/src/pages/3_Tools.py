"""
frontend/src/pages/3_Tools.py
Tools management page — Browse built-in tools, assign to agents, remove assignments.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager  import list_environments
from backend.app.agent_manager import list_agents
from backend.app.tool_manager  import (
    list_tools, get_agent_tools, assign_tool, remove_tool_assignment
)

st.set_page_config(page_title="Tools — AgentGround", page_icon="🔧", layout="wide")

with st.sidebar:
    st.markdown("## 🤖 AgentGround")
    st.markdown("*AI Agent Sandbox Platform*")
    st.divider()
    st.page_link("app.py",                   label="🏠 Home")
    st.page_link("pages/1_Environments.py",  label="🌍 Environments")
    st.page_link("pages/2_Agents.py",        label="🤖 Agents")
    st.page_link("pages/3_Tools.py",         label="🔧 Tools")

st.title("🔧 Tools")
st.markdown("Browse built-in tools and assign them to agents within an environment.")
st.divider()

# ─── Available Tools Library ──────────────────────────────────────────────────
st.subheader("Available Built-in Tools")
all_tools = list_tools()

if not all_tools:
    st.warning("No tools found. Run `database/seed.sql` to populate the built-in tool library.")
else:
    ICONS = {"Terminal": "💻", "Web Search": "🌐", "File Read/Write": "📁"}
    for tool in all_tools:
        icon = ICONS.get(tool["name"], "🔧")
        with st.expander(f"{icon}  **{tool['name']}**  {'(Built-in)' if tool['is_builtin'] else ''}"):
            st.write(tool["description"])
            st.caption(f"Tool ID: {tool['id']}")

st.divider()

# ─── Assign Tool Section ──────────────────────────────────────────────────────
st.subheader("Assign a Tool to an Agent")

environments = list_environments()
if not environments:
    st.warning("No environments found. Create an environment and register agents first.")
    st.stop()

env_options = {e["name"]: e["id"] for e in environments}
sel_env_name = st.selectbox("Select Environment", list(env_options.keys()),
                             key="assign_env_select")
sel_env_id   = env_options[sel_env_name]

agents = list_agents(sel_env_id)
if not agents:
    st.info(f"No agents in **{sel_env_name}**. Register an agent first.")
else:
    agent_options = {a["name"]: a["id"] for a in agents}
    tool_options  = {t["name"]: t["id"] for t in all_tools}

    with st.form("assign_tool_form", clear_on_submit=True):
        sel_agent_name = st.selectbox("Select Agent",   list(agent_options.keys()))
        sel_tool_name  = st.selectbox("Select Tool",    list(tool_options.keys()))
        scope = st.radio(
            "Tool Scope",
            ["private", "shared"],
            help="**Private** — only this agent can use the tool.  "
                 "**Shared** — all agents in the environment can use the tool.",
            horizontal=True,
        )
        submitted = st.form_submit_button("✅ Assign Tool", type="primary")

    if submitted:
        ok, msg = assign_tool(
            agent_id=agent_options[sel_agent_name],
            tool_id=tool_options[sel_tool_name],
            scope=scope,
        )
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)

st.divider()

# ─── View Assigned Tools Per Agent ───────────────────────────────────────────
st.subheader(f"Assigned Tools by Agent — {sel_env_name}")
agents = list_agents(sel_env_id)

if not agents:
    st.info("No agents to show.")
else:
    for agent in agents:
        assigned = get_agent_tools(agent["id"])
        label = f"🤖 **{agent['name']}** — {len(assigned)} tool(s) assigned"
        with st.expander(label):
            if not assigned:
                st.caption("No tools assigned to this agent yet.")
            else:
                for at in assigned:
                    scope_badge = "🔒 Private" if at["scope"] == "private" else "🔗 Shared"
                    col_info, col_rm = st.columns([5, 1])
                    col_info.markdown(
                        f"**{at['tool_name']}** — {scope_badge}  \n"
                        f"<small>Assigned: {at['created_at']}</small>",
                        unsafe_allow_html=True,
                    )
                    if col_rm.button("Remove", key=f"rm_{at['assignment_id']}"):
                        ok, msg = remove_tool_assignment(at["assignment_id"])
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)
