"""
frontend/src/pages/2_Agents.py
Agent management.
UX fixes:
  - Model ID: single text_input; previously used IDs shown as clickable pills
    that write into the input key — no separate box.
  - API URL: empty by default, suggestions shown as clickable pills below the field.
  - Per-tool scope builder with Add/Remove list.
  - Full inline edit (no delete-and-recreate).
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app._common import inject_css, render_sidebar, require_login, get_user_db, show_result
from backend.app.env_manager   import list_environments
from backend.app.agent_manager import (
    create_agent, update_agent, list_agents, delete_agent,
    get_agent_by_name, list_model_names,
)
from backend.app.tool_manager  import list_tools, assign_tool, get_agent_tools, remove_tool_assignment

st.set_page_config(page_title="Agents — AgentGround", layout="wide")
inject_css()
render_sidebar()
require_login()

db_name = get_user_db()


def _init(k, v):
    if k not in st.session_state:
        st.session_state[k] = v


def _url_hints() -> list[str]:
    hints = []
    if os.getenv("OPENAI_API_KEY"):     hints.append("https://api.openai.com/v1")
    if os.getenv("XAI_API_KEY"):        hints.append("https://api.x.ai/v1")
    if os.getenv("DEEPSEEK_API_KEY"):   hints.append("https://api.deepseek.com/v1")
    if os.getenv("GOOGLE_API_KEY"):     hints.append("https://generativelanguage.googleapis.com/v1beta/openai/")
    hints.append("http://localhost:11434/v1")   # Ollama always offered
    return hints


# ── Page header ────────────────────────────────────────────────────────────────
st.markdown("## Agents")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "Agents are LLM endpoints registered within an environment.</span>",
    unsafe_allow_html=True,
)
st.divider()

environments = list_environments(db_name=db_name)
if not environments:
    st.warning("No environments found. Create one first.")
    st.page_link("pages/1_Environments.py", label="Go to Environments")
    st.stop()

env_options = {e["name"]: e["id"] for e in environments}
env_names   = list(env_options.keys())
_init("ag_sel_env", env_names[0])

sel_env_name = st.selectbox(
    "Environment", env_names,
    index=env_names.index(st.session_state["ag_sel_env"])
          if st.session_state["ag_sel_env"] in env_names else 0,
    key="ag_env_box",
)
st.session_state["ag_sel_env"] = sel_env_name
sel_env_id = env_options[sel_env_name]
st.divider()

# ════════════════════════════════════════════════════════════════════════════
#  REGISTER NEW AGENT
# ════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="section-hdr">Register New Agent</div>', unsafe_allow_html=True)

prev_models   = list_model_names(db_name)
all_tools     = list_tools(db_name=db_name)
tool_name_map = {t["name"]: t["id"] for t in all_tools}
url_hints     = _url_hints()

_init("ag_name",       "")
_init("ag_api_url",    "")   # empty — not prefilled
_init("ag_model_id",   "")
_init("ag_prompt",     "")
_init("ag_tools_list", [])

c1, c2 = st.columns(2)
ag_name = c1.text_input("Agent Name", value=st.session_state["ag_name"],
                         placeholder="e.g. Researcher", key="ag_name_input")

# ── API Endpoint URL — empty, suggestions as pills ────────────────────────────
ag_url = c2.text_input(
    "API Endpoint URL",
    value=st.session_state["ag_api_url"],
    placeholder="Paste your provider's base URL…",
    key="ag_url_input",
)
# Suggestion pills — clicking writes to the input key
if url_hints:
    st.caption("Suggestions (click to use):")
    url_cols = st.columns(len(url_hints))
    for col, hint in zip(url_cols, url_hints):
        def set_url(h=hint): st.session_state["ag_url_input"] = h
        col.button(hint, key=f"urlhint_{hint}", on_click=set_url, use_container_width=True)

# ── Model ID — text input, previously used as clickable pills ─────────────────
ag_model = st.text_input(
    "Model ID",
    value=st.session_state["ag_model_id"],
    placeholder="e.g. llama3, gpt-4o, mistral, claude-3-opus-20240229",
    key="ag_model_input",
    help="The model identifier sent in the API request.",
)
if prev_models:
    st.caption("Previously used (click to fill):")
    pill_cols = st.columns(min(len(prev_models), 6))
    for col, m in zip(pill_cols, prev_models[:6]):
        def set_model(m_val=m): st.session_state["ag_model_input"] = m_val
        col.button(m, key=f"modelpill_{m}", on_click=set_model, use_container_width=True)

# ── System Prompt ─────────────────────────────────────────────────────────────
ag_prompt = st.text_area(
    "System Prompt", height=110,
    value=st.session_state["ag_prompt"],
    placeholder="You are a helpful assistant…",
    key="ag_prompt_input",
)

# ── Tool assignment builder ────────────────────────────────────────────────────
st.markdown("---")
st.markdown("**Assign Tools** *(optional — also available on the Tools page)*")

if all_tools:
    already_names = [x["tool_name"] for x in st.session_state["ag_tools_list"]]
    avail_tools = [t for t in tool_name_map if t not in already_names]
    ta_c1, ta_c2, ta_c3 = st.columns([3, 2, 1])
    ta_tool  = ta_c1.selectbox(
        "Tool", avail_tools if avail_tools else ["(all assigned)"],
        key="ag_ta_tool_sel", label_visibility="collapsed"
    )
    ta_scope = ta_c2.radio("Scope", ["private", "shared"], horizontal=True,
                            key="ag_ta_scope_sel", label_visibility="collapsed")
    if ta_c3.button("➕ Add", disabled=not avail_tools, use_container_width=True):
        st.session_state["ag_tools_list"].append({
            "tool_name": ta_tool,
            "tool_id":   tool_name_map[ta_tool],
            "scope":     ta_scope,
        })
        st.rerun()

    for i, entry in enumerate(st.session_state["ag_tools_list"]):
        sc_cls = "scope-private" if entry["scope"] == "private" else "scope-shared"
        lc, rc = st.columns([5, 1])
        lc.markdown(
            f"**{entry['tool_name']}** &nbsp;"
            f"<span class='{sc_cls}'>{entry['scope']}</span>",
            unsafe_allow_html=True,
        )
        if rc.button("✕", key=f"rm_pending_{i}"):
            st.session_state["ag_tools_list"].pop(i)
            st.rerun()
else:
    st.caption("No tools available in the database.")
    st.session_state["ag_tools_list"] = []

st.markdown("")
if st.button("Register Agent", type="primary", use_container_width=True):
    # Persist sticky values
    for key, val in [
        ("ag_name", ag_name), ("ag_api_url", ag_url),
        ("ag_model_id", ag_model), ("ag_prompt", ag_prompt)
    ]:
        st.session_state[key] = val

    ok, msg = create_agent(sel_env_id, ag_name, ag_url, ag_model, ag_prompt, db_name=db_name)
    show_result(ok, msg)
    if ok:
        if st.session_state["ag_tools_list"]:
            new_ag = get_agent_by_name(sel_env_id, ag_name, db_name=db_name)
            if new_ag:
                errs = []
                for entry in st.session_state["ag_tools_list"]:
                    tok, tmsg = assign_tool(new_ag["id"], entry["tool_id"],
                                            entry["scope"], db_name=db_name)
                    if not tok: errs.append(f"{entry['tool_name']}: {tmsg}")
                if errs:
                    show_result(False, "Tool assignment issues:\n" + "\n".join(errs))
                else:
                    st.success(f"{len(st.session_state['ag_tools_list'])} tool(s) assigned.")
        # Clear form
        for k in ("ag_name", "ag_api_url", "ag_model_id", "ag_prompt"):
            st.session_state[k] = ""
        st.session_state.pop("ag_name_input", None)
        st.session_state.pop("ag_url_input", None)
        st.session_state.pop("ag_model_input", None)
        st.session_state.pop("ag_prompt_input", None)
        st.session_state["ag_tools_list"]   = []
        st.rerun()

st.divider()

# ════════════════════════════════════════════════════════════════════════════
#  AGENT LIST
# ════════════════════════════════════════════════════════════════════════════
st.markdown(f'<div class="section-hdr">Agents in {sel_env_name}</div>', unsafe_allow_html=True)
agent_list = list_agents(sel_env_id, db_name=db_name)

if not agent_list:
    st.info("No agents registered yet.")
else:
    for agent in agent_list:
        aid = agent["id"]
        _init(f"ag_edit_{aid}", False)

        with st.expander(
            f"**{agent['name']}**  ·  `{agent['model_name']}`",
            expanded=st.session_state.get(f"ag_edit_{aid}", False),
        ):
            st.caption(f"ID: {aid}   |   Created: {agent['created_at']}   |   Updated: {agent['updated_at']}")

            if not st.session_state[f"ag_edit_{aid}"]:
                # ── View mode ─────────────────────────────────────────────
                st.markdown(f"**Endpoint:** `{agent['api_url']}`")
                st.markdown("**System Prompt:**")
                st.code(agent["system_prompt"], language="text")
                ce, cd = st.columns([1, 1])
                if ce.button("✏️ Edit", key=f"edit_btn_{aid}", type="primary"):
                    st.session_state[f"ag_edit_{aid}"] = True
                    st.rerun()
                if cd.button("🗑 Delete", key=f"del_btn_{aid}"):
                    st.session_state[f"confirm_del_ag_{aid}"] = True

                if st.session_state.get(f"confirm_del_ag_{aid}"):
                    st.warning(f"Delete **{agent['name']}**? Cannot be undone.")
                    cy, cn = st.columns(2)
                    if cy.button("Confirm", key=f"yes_del_{aid}", type="primary"):
                        ok, msg = delete_agent(aid, db_name=db_name)
                        show_result(ok, msg)
                        if ok:
                            del st.session_state[f"confirm_del_ag_{aid}"]
                            st.rerun()
                    if cn.button("Cancel", key=f"no_del_{aid}"):
                        del st.session_state[f"confirm_del_ag_{aid}"]
                        st.rerun()
            else:
                # ── Edit mode ─────────────────────────────────────────────
                ec1, ec2 = st.columns(2)
                e_name  = ec1.text_input("Name",  value=agent["name"],      key=f"e_name_{aid}")
                e_url   = ec2.text_input("API URL", value=agent["api_url"], key=f"e_url_{aid}")

                # Model ID with pills for previously used models
                e_model = st.text_input("Model ID", value=agent["model_name"],
                                        key=f"e_model_{aid}")
                if prev_models:
                    ep_cols = st.columns(min(len(prev_models), 6))
                    for col, m in zip(ep_cols, prev_models[:6]):
                        def set_ep_model(m_val=m, a_id=aid): st.session_state[f"e_model_{a_id}"] = m_val
                        col.button(m, key=f"ep_{aid}_{m}", on_click=set_ep_model)

                e_prompt = st.text_area("System Prompt", value=agent["system_prompt"],
                                        height=110, key=f"e_prompt_{aid}")
                sb, cb = st.columns(2)
                if sb.button("💾 Save", key=f"save_{aid}", type="primary"):
                    ok, msg = update_agent(
                        aid, name=e_name, api_url=e_url,
                        model_name=e_model, system_prompt=e_prompt, db_name=db_name,
                    )
                    show_result(ok, msg)
                    if ok:
                        st.session_state[f"ag_edit_{aid}"] = False
                        st.rerun()
                if cb.button("Cancel", key=f"cancel_{aid}"):
                    st.session_state[f"ag_edit_{aid}"] = False
                    st.rerun()

            # ── Tool assignments ───────────────────────────────────────────
            st.markdown("---")
            st.markdown("**Tool Assignments**")
            assigned     = get_agent_tools(aid, db_name=db_name)
            already_ids  = {at["tool_id"] for at in assigned}

            for at in assigned:
                sc_cls = "scope-private" if at["scope"] == "private" else "scope-shared"
                atc1, atc2 = st.columns([5, 1])
                atc1.markdown(
                    f"**{at['tool_name']}** &nbsp;<span class='{sc_cls}'>{at['scope']}</span>",
                    unsafe_allow_html=True,
                )
                if atc2.button("✕", key=f"rm_at_{at['assignment_id']}"):
                    ok, msg = remove_tool_assignment(at["assignment_id"], db_name=db_name)
                    show_result(ok, msg)
                    if ok: st.rerun()

            avail = [t["name"] for t in all_tools if t["id"] not in already_ids]
            if avail:
                at_c1, at_c2, at_c3 = st.columns([3, 2, 1])
                new_tool  = at_c1.selectbox("Add tool", avail, key=f"at_tool_{aid}",
                                             label_visibility="collapsed")
                new_scope = at_c2.radio("Scope", ["private", "shared"], horizontal=True,
                                        key=f"at_scope_{aid}", label_visibility="collapsed")
                if at_c3.button("Add", key=f"add_at_{aid}", use_container_width=True):
                    ok, msg = assign_tool(aid, tool_name_map[new_tool], new_scope, db_name=db_name)
                    show_result(ok, msg)
                    if ok: st.rerun()
