"""
frontend/src/pages/3_Tools.py
Tool management — browse built-in tools, assign to agents, manage scope.
Changes: db_name routing, show_result() (no ternaries), sticky form defaults.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app._common import inject_css, render_sidebar, require_login, get_user_db, show_result
from backend.app.env_manager   import list_environments
from backend.app.agent_manager import list_agents
from backend.app.tool_manager  import (
    list_tools, get_agent_tools, assign_tool, remove_tool_assignment
)

st.set_page_config(page_title="Tools — AgentGround", layout="wide")
inject_css()
render_sidebar()
require_login()

db_name = get_user_db()

st.markdown("## Tools")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Assign built-in tools to agents. Scope controls which agents in the environment "
    "can access the tool at runtime."
    "</span>", unsafe_allow_html=True,
)
st.divider()

# ── Built-in library ──────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Built-in Tool Library</div>', unsafe_allow_html=True)
all_tools = list_tools(db_name=db_name)

TOOL_NOTES = {
    "Terminal":
        "Executes whitelisted shell commands in the agent's private workspace. "
        "Allowed: ls, echo, pwd, cat, mkdir, date, whoami, head, tail, wc, find, grep. "
        "Path traversal ('..') is blocked.",
    "Web Search":
        "Searches the web using Tavily Search API. "
        "Requires TAVILY_API_KEY in your .env file. "
        "Returns up to 3 results per query.",
    "File Read/Write":
        "Reads and writes plain text files within the agent's sandboxed workspace directory.",
}

if not all_tools:
    st.warning("No tools found. Run `database/seed.sql` to populate the tool library.")
else:
    cols = st.columns(len(all_tools))
    for col, tool in zip(cols, all_tools):
        with col:
            st.markdown(f"**{tool['name']}**")
            st.caption(TOOL_NOTES.get(tool["name"], tool["description"] or ""))
            st.caption(f"ID: {tool['id']}  ·  {'Built-in' if tool['is_builtin'] else 'Custom'}")

st.divider()

# ── Assign ────────────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Assign Tool to Agent</div>', unsafe_allow_html=True)

environments = list_environments(db_name=db_name)
if not environments:
    st.warning("No environments found. Create an environment and register agents first.")
    st.stop()

# Sticky defaults for assign form
for key, default in [
    ("tools_sel_env", list(e["name"] for e in environments)[0] if environments else ""),
    ("tools_sel_agent", ""),
    ("tools_sel_tool", ""),
    ("tools_sel_scope", "private"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

env_options  = {e["name"]: e["id"] for e in environments}
env_names    = list(env_options.keys())
default_env_idx = env_names.index(st.session_state["tools_sel_env"]) \
    if st.session_state["tools_sel_env"] in env_names else 0

sel_env_name = st.selectbox(
    "Environment", env_names, index=default_env_idx, key="tools_env_sel",
)
st.session_state["tools_sel_env"] = sel_env_name
sel_env_id   = env_options[sel_env_name]
agents       = list_agents(sel_env_id, db_name=db_name)

if not agents:
    st.info(f"No agents in **{sel_env_name}**. Register an agent first.")
else:
    tool_options  = {t["name"]: t["id"] for t in all_tools}
    agent_options = {a["name"]: a["id"] for a in agents}

    with st.form("assign_tool_form"):
        c1, c2 = st.columns(2)

        agent_names    = list(agent_options.keys())
        default_agent  = st.session_state["tools_sel_agent"]
        agent_def_idx  = agent_names.index(default_agent) if default_agent in agent_names else 0
        sel_agent      = c1.selectbox("Agent", agent_names, index=agent_def_idx)

        tool_names     = list(tool_options.keys())
        default_tool   = st.session_state["tools_sel_tool"]
        tool_def_idx   = tool_names.index(default_tool) if default_tool in tool_names else 0
        sel_tool       = c2.selectbox("Tool", tool_names, index=tool_def_idx)

        scope_idx = 0 if st.session_state["tools_sel_scope"] == "private" else 1
        scope = st.radio(
            "Scope", ["private", "shared"], horizontal=True, index=scope_idx,
            help=(
                "**Private** — only this agent can use the tool.  "
                "**Shared** — all agents in the environment can access it at runtime."
            ),
        )
        submitted = st.form_submit_button("Assign", type="primary")

    if submitted:
        st.session_state["tools_sel_agent"] = sel_agent
        st.session_state["tools_sel_tool"]  = sel_tool
        st.session_state["tools_sel_scope"] = scope

        ok, msg = assign_tool(
            agent_options[sel_agent], tool_options[sel_tool], scope,
            db_name=db_name,
        )
        show_result(ok, msg)
        if ok:
            st.rerun()

st.divider()

# ── Current assignments ───────────────────────────────────────────────────────
st.markdown(
    f'<div class="section-hdr">Current Assignments — {sel_env_name}</div>',
    unsafe_allow_html=True,
)
for agent in list_agents(sel_env_id, db_name=db_name):
    assigned = get_agent_tools(agent["id"], db_name=db_name)
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
                    ok, msg = remove_tool_assignment(at["assignment_id"], db_name=db_name)
                    show_result(ok, msg)
                    if ok:
                        st.rerun()
