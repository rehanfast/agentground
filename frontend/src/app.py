"""
frontend/src/app.py
AgentGround — Main Streamlit Entry Point (Home Page)

Run with:
    streamlit run frontend/src/app.py
"""

import sys
import os

# Add project root to path so backend modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import streamlit as st

# ─── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="AgentGround",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Try to import backend modules ────────────────────────────────────────────
db_ok = True
try:
    from backend.app.env_manager import list_environments
    from backend.app.agent_manager import list_agents
    # Quick connection check
    envs = list_environments()
    db_ok = True
except Exception as db_err:
    db_ok = False
    db_error_msg = str(db_err)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🤖 AgentGround")
    st.markdown("*AI Agent Sandbox Platform*")
    st.divider()
    st.markdown("**Navigation**")
    st.page_link("app.py",              label="🏠 Home",         icon=None)
    st.page_link("pages/1_Environments.py", label="🌍 Environments", icon=None)
    st.page_link("pages/2_Agents.py",   label="🤖 Agents",       icon=None)
    st.page_link("pages/3_Tools.py",    label="🔧 Tools",         icon=None)
    st.divider()
    st.caption("Sprint 1 — Foundation & UI Shell")

# ─── Main content ─────────────────────────────────────────────────────────────
st.title("🏠 AgentGround Dashboard")
st.markdown("*A sandbox platform for experimenting with autonomous AI agents.*")
st.divider()

if not db_ok:
    st.error(
        f"**Could not connect to the database.**\n\n"
        f"Please check your `.env` file and make sure MySQL is running.\n\n"
        f"Error: `{db_error_msg}`"
    )
    st.info("Set up your `.env` file using `.env.example` as a template, then restart the app.")
    st.stop()

# ─── Stats cards ──────────────────────────────────────────────────────────────
environments = list_environments()
total_envs   = len(environments)
total_agents = sum(e["agent_count"] for e in environments)

col1, col2, col3 = st.columns(3)
col1.metric("🌍 Environments", total_envs,   help="Total isolated environments created")
col2.metric("🤖 Agents",       total_agents, help="Total agents registered across all environments")
col3.metric("🔧 Sprint",       "1 — Foundation", help="Current sprint scope")

st.divider()

# ─── Quick overview ───────────────────────────────────────────────────────────
st.subheader("About AgentGround")
st.markdown("""
AgentGround is a Python-native sandbox for experimenting with autonomous AI agents safely.

**What you can do in Sprint 1:**
- 🌍 **Create Environments** — isolated workspaces for your agent experiments
- 🤖 **Register Agents** — connect external AI API endpoints with system prompts
- 🔧 **Assign Tools** — give agents access to built-in tools like Terminal and Web Search

**Coming in Sprint 2:**
- ▶️ Run agents and observe their behaviour in real time
- 📋 View detailed audit logs of every agent action
- ⚙️ Enforce resource limits (call caps, timeouts, token budgets)
""")

st.divider()

# ─── Recent environments ───────────────────────────────────────────────────────
if environments:
    st.subheader("Recent Environments")
    for env in environments[:5]:
        with st.expander(f"🌍 {env['name']}  —  {env['agent_count']} agent(s)"):
            st.write(env["description"] or "*No description provided.*")
            st.caption(f"Created: {env['created_at']}")
else:
    st.info("No environments yet. Go to **Environments** to create your first one.")
st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] {display: none;}
    </style>
    """,
    unsafe_allow_html=True,
)
