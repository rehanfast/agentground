"""
frontend/src/app.py
AgentGround — Home Dashboard.
Changes: db_name routing to per-user DB on all service calls.

Run with:
    streamlit run frontend/src/app.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st
from backend.app._common import inject_css, render_sidebar, require_login, get_user_db

st.set_page_config(page_title="AgentGround", layout="wide",
                   initial_sidebar_state="expanded")
inject_css()
render_sidebar()
require_login()

db_name = get_user_db()

# ── DB ────────────────────────────────────────────────────────────────────────
db_ok, db_err, envs = True, "", []
try:
    from backend.app.env_manager import list_environments
    from backend.app.run_manager import get_runs_for_env
    envs = list_environments(db_name=db_name)
except Exception as e:
    db_ok, db_err = False, str(e)

# ── Header ────────────────────────────────────────────────────────────────────
user = st.session_state.get("user", {})
st.markdown("## AgentGround")
st.markdown(
    f"<span style='color:#6B7A99;font-size:0.9rem;'>"
    f"A governed sandbox for experimenting with autonomous AI agents. "
    f"Logged in as <strong>{user.get('username', '')}</strong>."
    f"</span>",
    unsafe_allow_html=True,
)
st.divider()

if not db_ok:
    st.error(f"**Database connection failed.** Check `.env` and confirm MySQL is running.\n\n`{db_err}`")
    st.info("Copy `.env.example` to `.env`, fill in your credentials, then restart.")
    st.stop()

# ── Stats ─────────────────────────────────────────────────────────────────────
total_envs, total_agents, total_runs, completed_runs = len(envs), 0, 0, 0
total_agents = sum(e["agent_count"] for e in envs)
for env in envs:
    try:
        runs = get_runs_for_env(env["id"], db_name=db_name)
        total_runs     += len(runs)
        completed_runs += sum(1 for r in runs if r["status"] == "completed")
    except Exception:
        pass

cols = st.columns(4)
for col, val, lbl in [
    (cols[0], total_envs,     "Environments"),
    (cols[1], total_agents,   "Agents"),
    (cols[2], total_runs,     "Total Runs"),
    (cols[3], completed_runs, "Completed"),
]:
    col.markdown(
        f'<div style="background:#fff;border:1px solid #D6E8F5;border-radius:8px;'
        f'padding:1rem 1.2rem;text-align:center;">'
        f'<div style="font-size:2rem;font-weight:700;color:#1B3A6B;">{val}</div>'
        f'<div style="font-size:0.75rem;color:#6B7A99;text-transform:uppercase;'
        f'letter-spacing:0.06em;margin-top:0.2rem;">{lbl}</div></div>',
        unsafe_allow_html=True,
    )

st.markdown("")

# ── Capabilities ──────────────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Platform Capabilities</div>', unsafe_allow_html=True)
ca, cb = st.columns(2)
with ca:
    st.markdown("""
**Environment Management**
Create isolated workspaces. Each environment holds its own agents, tool assignments, run history, and audit logs. Deleting an environment cascades cleanly.

**Agent Registration**
Register any OpenAI-compatible API endpoint as an agent. Provide a system prompt, model name, and URL. Prompts are editable at any time without re-registering.

**Tool Assignment**
Attach built-in tools (Terminal, Web Search, File R/W) to agents. Scope each assignment as Private (one agent) or Shared (all agents in the environment).
""")
with cb:
    st.markdown("""
**Run Execution**
Trigger single-agent or multi-agent sequential runs. In multi-agent mode each agent receives the previous agent's output as its next input.

**Resource Governance**
A LangChain callback intercepts every LLM call and tool invocation. Set a maximum call cap and a wall-clock timeout. A Stop button signals the callback via a threading.Event.

**Audit Log**
Every step — LLM requests, tool calls, results, final answers — is written to MySQL in structured JSON. Browse and export the full trace from the Audit Log page.
""")

# ── Recent environments ───────────────────────────────────────────────────────
if envs:
    st.markdown('<div class="section-hdr">Recent Environments</div>', unsafe_allow_html=True)
    cls_map = {
        "completed": "pill-ok", "running": "pill-run",
        "failed": "pill-fail", "stopped": "pill-stop",
    }
    for env in envs[:5]:
        last_run = None
        try:
            runs = get_runs_for_env(env["id"], db_name=db_name)
            last_run = runs[0] if runs else None
        except Exception:
            pass
        with st.expander(f"**{env['name']}** — {env['agent_count']} agent(s)"):
            if env["description"]:
                st.write(env["description"])
            c1, c2 = st.columns(2)
            c1.caption(f"Created: {env['created_at']}")
            if last_run:
                cls = cls_map.get(last_run["status"], "pill-run")
                c2.markdown(
                    f"Last run: <span class='pill {cls}'>{last_run['status']}</span>",
                    unsafe_allow_html=True,
                )
            else:
                c2.caption("No runs yet")
else:
    st.info("No environments found. Go to **Environments** to create your first one.")
