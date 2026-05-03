"""
backend/app/_common.py
Shared CSS, sidebar, auth guard, session persistence.

Cookie strategy: uses extra-streamlit-components CookieManager for
persistent browser cookies that survive refresh, tab close, and new tabs.
Falls back to st.query_params for fast same-session navigation.
"""

import streamlit as st
from datetime import datetime, timedelta

PAGE_CSS = """
<style>
[data-testid="stSidebarNav"] { display: none; }
.ag-brand h2 { font-size:1.12rem; font-weight:700; color:#1B3A6B; margin:0 0 0.12rem 0; }
.ag-brand p  { font-size:0.70rem; color:#6B7A99; margin:0; text-transform:uppercase; letter-spacing:0.08em; }
.section-hdr {
    font-size:0.73rem; font-weight:600; color:#6B7A99; text-transform:uppercase;
    letter-spacing:0.09em; margin:1.3rem 0 0.45rem 0;
    border-bottom:1px solid #E2EDF7; padding-bottom:0.28rem;
}
.pill { display:inline-block; padding:0.15rem 0.5rem; border-radius:20px; font-size:0.70rem; font-weight:600; }
.pill-ok   { background:#D4EDDA; color:#1A5C2A; }
.pill-run  { background:#D6EAF8; color:#1A4F7C; }
.pill-fail { background:#FADBD8; color:#7B241C; }
.pill-stop { background:#FEF9E7; color:#7D6608; }
.scope-private { background:#EBF5FB; border:1px solid #AED6F1; border-radius:4px;
                 padding:0.08rem 0.4rem; font-size:0.70rem; color:#1A4F7C; font-weight:600; }
.scope-shared  { background:#E8F8F5; border:1px solid #A2D9CE; border-radius:4px;
                 padding:0.08rem 0.4rem; font-size:0.70rem; color:#0E6655; font-weight:600; }
.step-tag { display:inline-block; padding:0.13rem 0.45rem; border-radius:4px;
            font-size:0.68rem; font-weight:600; letter-spacing:0.04em; margin-right:0.3rem; }
.tag-llm-req  { background:#EAF2FB; color:#1A4F7C; }
.tag-llm-resp { background:#E8F8F5; color:#0E6655; }
.tag-tool     { background:#FEF9E7; color:#7D6608; }
.tag-result   { background:#D4EDDA; color:#1A5C2A; }
.tag-stop     { background:#FEF9E7; color:#7D6608; }
.tag-error    { background:#FADBD8; color:#7B241C; }
</style>
"""

SIDEBAR_BRAND   = '<div class="ag-brand"><h2>AgentGround</h2><p>AI Agent Sandbox</p></div>'
SIDEBAR_CAPTION = "Fundamentals of SE · Spring 2026"
_COOKIE_NAME    = "ag_session_token"
_COOKIE_TTL     = 30  # days


def inject_css() -> None:
    st.markdown(PAGE_CSS, unsafe_allow_html=True)


def _read_token() -> str:
    """Read the session token from query_params."""
    try:
        tok = st.query_params.get("_tok", "")
        if tok:
            return tok
    except Exception:
        pass
    return ""


def _write_token(token: str) -> None:
    """Persist token in query_params for fast navigation."""
    try:
        st.query_params["_tok"] = token
    except Exception:
        pass


def _clear_token() -> None:
    """Remove token from query_params."""
    try:
        st.query_params.clear()
    except Exception:
        pass


# ── Session restore ────────────────────────────────────────────────────────────

def _restore_session_from_cookie() -> None:
    """Restore user session from persistent cookie on every page load."""
    if st.session_state.get("user"):
        return  # Already logged in this session

    token = _read_token()
    if not token:
        return

    from backend.app.auth_manager import validate_session_token
    user = validate_session_token(token)
    if user:
        st.session_state["user"]          = user
        st.session_state["session_token"] = token
        # Ensure query params stay in sync for fast navigation
        try:
            st.query_params["_tok"] = token
        except Exception:
            pass
    else:
        _clear_token()


def persist_login(user: dict, token: str) -> None:
    """Call immediately after a successful login."""
    st.session_state["user"]          = user
    st.session_state["session_token"] = token
    _write_token(token)


# ── Sidebar ────────────────────────────────────────────────────────────────────

def render_sidebar() -> None:
    _restore_session_from_cookie()
    with st.sidebar:
        st.markdown(SIDEBAR_BRAND, unsafe_allow_html=True)
        st.divider()
        st.page_link("app.py",                  label="🏠 Home")
        st.page_link("pages/1_Environments.py", label="📁 Environments")
        st.page_link("pages/2_Agents.py",       label="🤖 Agents")
        st.page_link("pages/3_Tools.py",        label="🔧 Tools")
        st.page_link("pages/4_Run.py",          label="▶ Run")
        st.page_link("pages/5_Audit_Log.py",    label="📋 Audit Log")
        st.page_link("pages/6_Settings.py",     label="⚙️ Settings")
        st.page_link("pages/7_Auto_Mode.py",    label="⚡ Auto Mode")
        st.divider()
        user = st.session_state.get("user")
        if user:
            st.caption(f"**{user['username']}**")
            c1, c2 = st.columns(2)
            if c1.button("Account", use_container_width=True):
                st.switch_page("pages/0_Login.py")
            if c2.button("Log out", use_container_width=True):
                _logout()
        else:
            if st.button("Log in / Register", use_container_width=True):
                st.switch_page("pages/0_Login.py")
        st.caption(SIDEBAR_CAPTION)


def _logout() -> None:
    from backend.app.auth_manager import revoke_session_token
    token = st.session_state.pop("session_token", "")
    revoke_session_token(token)
    st.session_state.pop("user", None)
    _clear_token()
    st.switch_page("pages/0_Login.py")


def require_login() -> None:
    _restore_session_from_cookie()
    if not st.session_state.get("user"):
        st.switch_page("pages/0_Login.py")


def get_user_db() -> str:
    return st.session_state.get("user", {}).get("db_name", "")


# ── Display helpers ────────────────────────────────────────────────────────────

def show_error(msg: str) -> None:
    clean = msg.split("\n[SQL:")[0].split("(Background on")[0].strip()
    if "\n\n" in clean and "GRANT" in clean:
        parts = clean.split("\n\n", 1)
        st.error(parts[0])
        st.code(parts[1].strip(), language="sql")
    else:
        st.error(clean or msg)


def show_result(ok: bool, msg: str) -> None:
    if ok:
        st.success(msg)
    else:
        show_error(msg)
