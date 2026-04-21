"""
frontend/src/app.py
AgentGround — Home Dashboard

Run with:
    streamlit run frontend/src/app.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st

st.set_page_config(
    page_title="AgentGround",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Shared CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stSidebarNav"] { display: none; }

.ag-brand h2 {
    font-size: 1.15rem; font-weight: 700; color: #1B3A6B;
    margin: 0 0 0.15rem 0; letter-spacing: 0.02em;
}
.ag-brand p {
    font-size: 0.72rem; color: #6B7A99; margin: 0;
    text-transform: uppercase; letter-spacing: 0.07em;
}
.stat-card {
    background: #ffffff; border: 1px solid #D6E8F5;
    border-radius: 8px; padding: 1.1rem 1.4rem; text-align: center;
}
.stat-card .val {
    font-size: 2.2rem; font-weight: 700; color: #1B3A6B; line-height: 1.1;
}
.stat-card .lbl {
    font-size: 0.78rem; color: #6B7A99; margin-top: 0.2rem;
    text-transform: uppercase; letter-spacing: 0.06em;
}
.section-hdr {
    font-size: 0.74rem; font-weight: 600; color: #6B7A99;
    text-transform: uppercase; letter-spacing: 0.09em;
    margin: 1.4rem 0 0.5rem 0;
    border-bottom: 1px solid #E2EDF7; padding-bottom: 0.3rem;
}
.pill { display:inline-block; padding:0.18rem 0.55rem; border-radius:20px;
        font-size:0.72rem; font-weight:600; }
.pill-ok   { background:#D4EDDA; color:#1A5C2A; }
.pill-run  { background:#D6EAF8; color:#1A4F7C; }
.pill-fail { background:#FADBD8; color:#7B241C; }
.pill-stop { background:#FEF9E7; color:#7D6608; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
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

# ── DB connection ─────────────────────────────────────────────────────────────
db_ok = True
db_error_msg = ""
envs = []
try:
    from backend.app.env_manager import list_environments
    from backend.app.run_manager import get_runs_for_env
    envs = list_environments()
except Exception as e:
    db_ok = False
    db_error_msg = str(e)

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("## AgentGround")
st.markdown(
    "<span style='color:#6B7A99;font-size:0.9rem;'>"
    "A governed sandbox for experimenting with autonomous AI agents."
    "</span>",
    unsafe_allow_html=True,
)
st.divider()

if not db_ok:
    st.error(
        f"**Database connection failed.** "
        f"Check your `.env` file and confirm MySQL is running.\n\n`{db_error_msg}`"
    )
    st.info("Copy `.env.example` to `.env`, fill in your credentials, then restart.")
    st.stop()

# ── Stats ─────────────────────────────────────────────────────────────────────
total_envs     = len(envs)
total_agents   = sum(e["agent_count"] for e in envs)
total_runs     = 0
completed_runs = 0
for env in envs:
    try:
        runs = get_runs_for_env(env["id"])
        total_runs     += len(runs)
        completed_runs += sum(1 for r in runs if r["status"] == "completed")
    except Exception:
        pass

col1, col2, col3, col4 = st.columns(4)
for col, val, lbl in [
    (col1, total_envs,     "Environments"),
    (col2, total_agents,   "Agents"),
    (col3, total_runs,     "Total Runs"),
    (col4, completed_runs, "Completed"),
]:
    col.markdown(
        f'<div class="stat-card"><div class="val">{val}</div>'
        f'<div class="lbl">{lbl}</div></div>',
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
Attach built-in tools (Terminal, Web Search, File R/W) to agents. Each assignment is scoped as Private (one agent) or Shared (all agents in the environment).
""")
with cb:
    st.markdown("""
**Run Execution**
Trigger single-agent or multi-agent sequential runs from the Run page. In multi-agent mode each agent receives the previous agent's output as its next input.

**Resource Governance**
A LangChain callback intercepts every LLM call and tool invocation. Set a maximum call cap and a wall-clock timeout per run. Limits are enforced before each step.

**Audit Log**
Every step — LLM requests, tool calls, results, final answers — is written to MySQL in structured JSON. Browse, expand, and export the full trace from the Audit Log page.
""")

# ── Recent environments ───────────────────────────────────────────────────────
if envs:
    st.markdown('<div class="section-hdr">Recent Environments</div>', unsafe_allow_html=True)
    for env in envs[:5]:
        last_run = None
        try:
            runs = get_runs_for_env(env["id"])
            last_run = runs[0] if runs else None
        except Exception:
            pass

        with st.expander(f"{env['name']}  —  {env['agent_count']} agent(s)"):
            if env["description"]:
                st.write(env["description"])
            c1, c2 = st.columns(2)
            c1.caption(f"Created: {env['created_at']}")
            if last_run:
                cls_map = {"completed": "pill-ok", "running": "pill-run",
                           "failed": "pill-fail", "stopped": "pill-stop"}
                cls = cls_map.get(last_run["status"], "pill-run")
                c2.markdown(
                    f"Last run: <span class='pill {cls}'>{last_run['status']}</span>",
                    unsafe_allow_html=True,
                )
            else:
                c2.caption("No runs yet")
else:
    st.info("No environments found. Go to **Environments** to create your first one.")
