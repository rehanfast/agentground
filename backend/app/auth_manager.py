"""
backend/app/auth_manager.py
User registration, login, session management, and account deletion.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError, ProgrammingError, OperationalError

from backend.app.database import (
    get_master_session, create_user_database, drop_user_database, user_db_name
)
from backend.app.models import User, Session

SESSION_TTL_DAYS = 30  # session tokens last 30 days
_MYSQL_TABLE_NOT_FOUND = 1146

_TABLE_MISSING_MSG = (
    "The 'users' table does not exist yet.\n"
    "Run this to create it:\n\n"
    "    mysql -u root -p agentground < database/schema.sql"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(32)
    key  = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return f"{salt}:{key.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, key_hex = stored.split(":", 1)
    except ValueError:
        return False
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 260_000)
    return secrets.compare_digest(key.hex(), key_hex)


def _is_table_missing(exc: Exception) -> bool:
    orig = getattr(exc, "orig", None)
    return orig is not None and getattr(orig, "args", (None,))[0] == _MYSQL_TABLE_NOT_FOUND


def _user_to_dict(user: User) -> dict:
    return {
        "id":       user.id,
        "username": user.username,
        "email":    user.email,
        "db_name":  user_db_name(user.username),
    }


# ── Registration ──────────────────────────────────────────────────────────────

def register_user(username: str, email: str, password: str) -> tuple[bool, str]:
    """
    Register a new user and create their dedicated MySQL database.

    BVA-enforced boundaries:
      username : 1–50 chars, alphanumeric + underscore
      email    : must contain '@' and '.' after '@'
      password : minimum 8 characters
    """
    username = username.strip()
    email    = email.strip().lower()
    password = password.strip()

    if not username:
        return False, "Username is required."
    if len(username) > 50:
        return False, "Username must not exceed 50 characters."
    if not all(c.isalnum() or c == "_" for c in username):
        return False, "Username may only contain letters, numbers, and underscores."
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return False, "Please enter a valid email address."
    if len(email) > 255:
        return False, "Email address is too long."
    if not password:
        return False, "Password is required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."

    session = get_master_session()
    try:
        session.add(User(
            username=username,
            email=email,
            password_hash=_hash_password(password),
        ))
        session.commit()
    except (ProgrammingError, OperationalError) as e:
        session.rollback()
        if _is_table_missing(e):
            return False, _TABLE_MISSING_MSG
        return False, f"Database error: {e}"
    except IntegrityError as e:
        session.rollback()
        msg = str(getattr(e, "orig", e)).lower()
        if "username" in msg:
            return False, f"Username '{username}' is already taken."
        if "email" in msg:
            return False, "An account with this email already exists."
        return False, "Registration failed."
    except Exception as e:
        session.rollback()
        return False, f"Unexpected error: {e}"
    finally:
        session.close()

    # Create the user's private database
    try:
        create_user_database(username)
    except Exception as e:
        return False, f"Account created but database setup failed: {e}"

    # Create the user's workspace folder
    _create_workspace(username)

    return True, "Account created. You can now log in."


# ── Login ─────────────────────────────────────────────────────────────────────

def login_user(identifier: str, password: str) -> tuple[bool, dict | str]:
    """Authenticate and return (True, user_dict) or (False, error_message)."""
    identifier = identifier.strip()
    password   = password.strip()

    if not identifier:
        return False, "Username or email is required."
    if not password:
        return False, "Password is required."

    session = get_master_session()
    try:
        user = (
            session.query(User)
            .filter(
                (User.username == identifier) |
                (User.email == identifier.lower())
            ).first()
        )
        if not user or not _verify_password(password, user.password_hash):
            return False, "Invalid credentials."
        return True, _user_to_dict(user)
    except (ProgrammingError, OperationalError) as e:
        if _is_table_missing(e):
            return False, _TABLE_MISSING_MSG
        return False, f"Database error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"
    finally:
        session.close()


# ── Session tokens (persistent login) ────────────────────────────────────────

def create_session_token(user_id: int) -> str:
    """Create a persistent session token valid for SESSION_TTL_DAYS days."""
    token   = secrets.token_hex(32)
    expires = datetime.utcnow() + timedelta(days=SESSION_TTL_DAYS)
    session = get_master_session()
    try:
        session.add(Session(token=token, user_id=user_id, expires_at=expires))
        session.commit()
    finally:
        session.close()
    return token


def validate_session_token(token: str) -> dict | None:
    """
    Return user dict if token is valid and not expired, else None.
    Also deletes expired tokens lazily.
    """
    if not token:
        return None
    session = get_master_session()
    try:
        row = (
            session.query(Session)
            .filter_by(token=token)
            .first()
        )
        if not row:
            return None
        if row.expires_at < datetime.utcnow():
            session.delete(row)
            session.commit()
            return None
        user = session.query(User).filter_by(id=row.user_id).first()
        return _user_to_dict(user) if user else None
    except Exception:
        return None
    finally:
        session.close()


def revoke_session_token(token: str) -> None:
    """Delete a session token on logout."""
    if not token:
        return
    session = get_master_session()
    try:
        row = session.query(Session).filter_by(token=token).first()
        if row:
            session.delete(row)
            session.commit()
    except Exception:
        pass
    finally:
        session.close()


# ── Account deletion ──────────────────────────────────────────────────────────

def delete_account(user_id: int, password: str) -> tuple[bool, str]:
    """
    Permanently delete an account:
    - Verifies password first
    - Drops the user's MySQL database
    - Deletes their workspace folder
    - Removes the user row (cascades sessions)
    """
    session = get_master_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False, "Account not found."
        if not _verify_password(password, user.password_hash):
            return False, "Incorrect password."

        username = user.username

        # Delete workspace
        _delete_workspace(username)

        # Drop user database
        drop_user_database(username)

        # Delete user row (cascade removes sessions)
        session.delete(user)
        session.commit()
        return True, "Account permanently deleted."
    except Exception as e:
        session.rollback()
        return False, f"Error deleting account: {e}"
    finally:
        session.close()


# ── Workspace management ──────────────────────────────────────────────────────

def _workspace_root() -> str:
    base = os.getenv("WORKSPACE_ROOT", "workspace")
    os.makedirs(base, exist_ok=True)
    return base


def _create_workspace(username: str) -> None:
    path = os.path.join(_workspace_root(), username)
    os.makedirs(path, mode=0o700, exist_ok=True)


def _delete_workspace(username: str) -> None:
    import shutil
    path = os.path.join(_workspace_root(), username)
    if os.path.exists(path):
        shutil.rmtree(path)


def get_env_workspace(username: str, env_id: int) -> str:
    """Return the shared folder path for an environment (creates it if needed)."""
    base = os.path.join(_workspace_root(), username, f"env_{env_id}")
    shared = os.path.join(base, "shared")
    os.makedirs(shared, mode=0o700, exist_ok=True)
    return shared


def get_agent_workspace(username: str, env_id: int, agent_id: int) -> str:
    """Return the private folder path for an agent (creates it if needed)."""
    path = os.path.join(_workspace_root(), username, f"env_{env_id}", f"agent_{agent_id}")
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


def get_run_workspace(username: str, env_id: int, run_id: int, agent_id: int) -> str:
    """
    Return the per-run per-agent workspace path (creates it if needed).
    Structure: workspace/<username>/env_<env_id>/run_<run_id>/agent_<agent_id>/
    This isolates each run's file output so runs don't overwrite each other.
    """
    path = os.path.join(
        _workspace_root(), username,
        f"env_{env_id}", f"run_{run_id}", f"agent_{agent_id}"
    )
    os.makedirs(path, mode=0o700, exist_ok=True)
    return path


# ── Password change ───────────────────────────────────────────────────────────

def change_password(
    user_id: int,
    old_password: str,
    new_password: str,
) -> tuple[bool, str]:
    """
    Change a user's password after verifying the current one.
    Enforces the same minimum-length rule as registration (≥8 chars).
    """
    old_password = old_password.strip()
    new_password = new_password.strip()

    if not old_password:
        return False, "Current password is required."
    if not new_password:
        return False, "New password is required."
    if len(new_password) < 8:
        return False, "New password must be at least 8 characters."

    session = get_master_session()
    try:
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            return False, "Account not found."
        if not _verify_password(old_password, user.password_hash):
            return False, "Current password is incorrect."
        user.password_hash = _hash_password(new_password)
        session.commit()
        return True, "Password changed successfully."
    except Exception as e:
        session.rollback()
        return False, f"Error changing password: {e}"
    finally:
        session.close()
