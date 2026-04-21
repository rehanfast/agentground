"""
frontend/src/pages/3_Tools.py
Tool management — browse built-in tools, assign to agents, manage scope.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app.env_manager   import list_environments
from backend.app.agent_manager import list_agents
from backend.app.tool_manager  import (
    list_tools, get_agent_tools, assign_tool, remove_tool_assignment
)

st.set_page_config(page_title="Tools — AgentGround", layout="wide")

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
.scope-private { background:#EBF5FB; border:1px solid #AED6F1;
                 border-radius:4px; padding:0.1rem 0.45rem;
                 font-size:0.72rem; color:#1A4F7C; font-weight:600; }
.scope-shared  { background:#E8F8F5; border:1px solid #A2D9CE;
                 border-radius:4px; padding:0.1rem 0.45rem;
                 font-size:0.72rem; color:#0E6655; font-weight:600; }
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

st.markdown("## Tools")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Assign built-in tools to agents. Scope controls which agents in the environment "
    "can access the tool at runtime."
    "</span>",
    unsafe_allow_html=True,
)
st.divider()

# ── Built-in tool library ─────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Built-in Tool Library</div>', unsafe_allow_html=True)
all_tools = list_tools()

if not all_tools:
    st.warning("No tools found. Run `database/seed.sql` to populate the tool library.")
else:
    TOOL_NOTES = {
        "Terminal":       "Executes whitelisted shell commands. Allowed: ls, echo, pwd, cat, mkdir, date, whoami, head, tail, wc, find, grep.",
        "Web Search":     "Searches the web via DuckDuckGo. No API key required.",
        "File Read/Write":"Reads and writes plain text files within the agent's working directory.",
    }
    cols = st.columns(len(all_tools))
    for col, tool in zip(cols, all_tools):
        with col:
            st.markdown(f"**{tool['name']}**")
            st.caption(TOOL_NOTES.get(tool["name"], tool["description"] or ""))
            st.caption(f"ID: {tool['id']}  ·  {'Built-in' if tool['is_builtin'] else 'Custom'}")

st.divider()

# ── Assign ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Assign Tool to Agent</div>', unsafe_allow_html=True)

environments = list_environments()
if not environments:
    st.warning("No environments found. Create an environment and register agents first.")
    st.stop()

env_options  = {e["name"]: e["id"] for e in environments}
sel_env_name = st.selectbox("Environment", list(env_options.keys()), key="assign_env")
sel_env_id   = env_options[sel_env_name]
agents       = list_agents(sel_env_id)

if not agents:
    st.info(f"No agents in **{sel_env_name}**. Register an agent first.")
else:
    agent_options = {a["name"]: a["id"] for a in agents}
    tool_options  = {t["name"]: t["id"] for t in all_tools}

    with st.form("assign_tool_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        sel_agent = c1.selectbox("Agent", list(agent_options.keys()))
        sel_tool  = c2.selectbox("Tool",  list(tool_options.keys()))
        scope = st.radio(
            "Scope",
            ["private", "shared"],
            horizontal=True,
            help=(
                "**Private** — only this agent can use the tool.  "
                "**Shared** — all agents in the environment can access it during a run."
            ),
        )
        submitted = st.form_submit_button("Assign", type="primary")

    if submitted:
        ok, msg = assign_tool(
            agent_id=agent_options[sel_agent],
            tool_id=tool_options[sel_tool],
            scope=scope,
        )
        st.success(msg) if ok else st.error(msg)
        if ok:
            st.rerun()

st.divider()

# ── Assignments per agent ─────────────────────────────────────────────────────
st.markdown(
    f'<div class="section-hdr">Current Assignments — {sel_env_name}</div>',
    unsafe_allow_html=True,
)
agents = list_agents(sel_env_id)

if not agents:
    st.info("No agents to show.")
else:
    for agent in agents:
        assigned = get_agent_tools(agent["id"])
        with st.expander(f"**{agent['name']}** — {len(assigned)} tool(s)"):
            if not assigned:
                st.caption("No tools assigned.")
            else:
                for at in assigned:
                    scope_cls = "scope-private" if at["scope"] == "private" else "scope-shared"
                    c_info, c_rm = st.columns([6, 1])
                    c_info.markdown(
                        f"**{at['tool_name']}** &nbsp;"
                        f"<span class='{scope_cls}'>{at['scope']}</span>"
                        f"<br><small style='color:#999;'>Assigned: {at['created_at']}</small>",
                        unsafe_allow_html=True,
                    )
                    if c_rm.button("Remove", key=f"rm_{at['assignment_id']}"):
                        ok, msg = remove_tool_assignment(at["assignment_id"])
                        st.success(msg) if ok else st.error(msg)
                        if ok:
                            st.rerun()
