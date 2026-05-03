"""
frontend/src/pages/0_Login.py
- Logged-out users see Login and Create Account tabs.
- Logged-in users see an Account Management page (change password, delete account).
  They are NEVER silently redirected away; this page is reachable from the
  sidebar "Account" button at all times.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import streamlit as st
from backend.app._common import (
    persist_login, _clear_token,
    inject_css, render_sidebar, _restore_session_from_cookie,
    PAGE_CSS, SIDEBAR_BRAND, SIDEBAR_CAPTION, show_result,
)
from backend.app.auth_manager import (
    register_user, login_user, create_session_token,
    change_password, delete_account, revoke_session_token,
)

st.set_page_config(page_title="Account — AgentGround", layout="centered")
inject_css()

# Always try to restore session first
_restore_session_from_cookie()

user = st.session_state.get("user")

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGED-IN  →  Account Management
# ══════════════════════════════════════════════════════════════════════════════
if user:
    render_sidebar()  # full sidebar with nav links
    st.markdown("## Account Management")
    st.markdown(
        f"<span style='color:#6B7A99;font-size:0.9rem;'>Signed in as "
        f"<strong>{user['username']}</strong></span>",
        unsafe_allow_html=True,
    )
    st.divider()

    tab_pw, tab_del = st.tabs(["Change Password", "Delete Account"])

    # ── Change Password ───────────────────────────────────────────────────────
    with tab_pw:
        st.markdown('<div class="section-hdr">Change Password</div>',
                    unsafe_allow_html=True)
        with st.form("change_pw_form"):
            old_pw  = st.text_input("Current Password", type="password",
                                    placeholder="Enter your current password")
            new_pw  = st.text_input("New Password", type="password",
                                    placeholder="At least 8 characters")
            conf_pw = st.text_input("Confirm New Password", type="password",
                                    placeholder="Repeat new password")
            submitted = st.form_submit_button("Update Password", type="primary",
                                              use_container_width=True)
        if submitted:
            if new_pw != conf_pw:
                show_result(False, "New passwords do not match.")
            else:
                ok, msg = change_password(user["id"], old_pw, new_pw)
                show_result(ok, msg)

    # ── Delete Account ────────────────────────────────────────────────────────
    with tab_del:
        st.markdown('<div class="section-hdr">Delete Account</div>',
                    unsafe_allow_html=True)
        st.warning(
            "⚠️ This is **permanent**. Your account, all environments, "
            "agents, run history, and audit logs will be erased and cannot be recovered."
        )
        with st.form("delete_acct_form"):
            confirm_pw = st.text_input("Confirm Password", type="password",
                                       placeholder="Enter your password to confirm")
            submitted  = st.form_submit_button("Permanently Delete My Account",
                                               type="primary",
                                               use_container_width=True)
        if submitted:
            ok, msg = delete_account(user["id"], confirm_pw)
            if ok:
                # Revoke session and clear state
                token = st.session_state.pop("session_token", "")
                revoke_session_token(token)
                st.session_state.pop("user", None)
                _clear_token()
                st.success(msg + " You have been logged out.")
                st.rerun()
            else:
                show_result(False, msg)

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGED-OUT  →  Login / Register
# ══════════════════════════════════════════════════════════════════════════════
else:
    # Minimal sidebar on the login page (no nav links)
    with st.sidebar:
        st.markdown(SIDEBAR_BRAND, unsafe_allow_html=True)
        st.divider()
        st.caption(SIDEBAR_CAPTION)

    st.markdown("## AgentGround")
    st.markdown(
        "<span style='color:#6B7A99;font-size:0.88rem;'>AI Agent Sandbox Platform</span>",
        unsafe_allow_html=True,
    )
    st.divider()

    def _show_auth_error(msg: str) -> None:
        """Display auth error; formats schema command as a code block."""
        if "database/schema.sql" in msg:
            parts = msg.split("\n\n    ", 1)
            st.error(parts[0])
            if len(parts) > 1:
                st.code(parts[1].strip(), language="bash")
        else:
            st.error(msg)

    tab_login, tab_register = st.tabs(["Log In", "Create Account"])

    # ── Login ─────────────────────────────────────────────────────────────────
    with tab_login:
        st.markdown('<div class="section-hdr">Sign In</div>',
                    unsafe_allow_html=True)
        with st.form("login_form"):
            identifier = st.text_input("Username or Email",
                                       placeholder="Enter your username or email")
            password   = st.text_input("Password", type="password",
                                       placeholder="Enter your password")
            submitted  = st.form_submit_button("Log In", type="primary",
                                               use_container_width=True)
        if submitted:
            ok, result = login_user(identifier, password)
            if ok:
                token = create_session_token(result["id"])
                persist_login(result, token)
                st.success(f"Welcome back, {result['username']}.")
                st.switch_page("app.py")
            else:
                _show_auth_error(result)

    # ── Register ──────────────────────────────────────────────────────────────
    with tab_register:
        st.markdown('<div class="section-hdr">Create Account</div>',
                    unsafe_allow_html=True)
        st.caption(
            "Username: 1–50 characters, letters/numbers/underscores only.  "
            "Password: minimum 8 characters."
        )
        with st.form("register_form"):
            new_username = st.text_input("Username", max_chars=50,
                                         placeholder="e.g. johndoe")
            new_email    = st.text_input("Email",
                                         placeholder="e.g. john@example.com")
            new_password = st.text_input("Password", type="password",
                                         placeholder="At least 8 characters")
            new_confirm  = st.text_input("Confirm Password", type="password",
                                         placeholder="Repeat your password")
            submitted    = st.form_submit_button("Create Account", type="primary",
                                                 use_container_width=True)
        if submitted:
            if new_password != new_confirm:
                st.error("Passwords do not match.")
            else:
                ok, msg = register_user(new_username, new_email, new_password)
                if ok:
                    st.success(msg)
                else:
                    _show_auth_error(msg)
