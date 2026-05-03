"""
backend/app/settings_manager.py
Read/write per-user application settings stored in the user_settings table.
"""

from backend.app.database import get_session
from backend.app.models import UserSetting

DEFAULTS = {
    "rpm_limit":         "20",    # max LLM API calls per minute per run
    "daily_run_limit":   "100",   # max run starts per calendar day
    "max_calls_default": "10",    # default max calls per run
    "timeout_default":   "60",    # default timeout per run (seconds)
}


def get_setting(key: str, db_name: str = "") -> str:
    session = get_session(db_name)
    try:
        row = session.query(UserSetting).filter_by(key=key).first()
        return row.value if row else DEFAULTS.get(key, "")
    finally:
        session.close()


def set_setting(key: str, value: str, db_name: str = "") -> tuple[bool, str]:
    session = get_session(db_name)
    try:
        row = session.query(UserSetting).filter_by(key=key).first()
        if row:
            row.value = str(value)
        else:
            session.add(UserSetting(key=key, value=str(value)))
        session.commit()
        return True, "Setting saved."
    except Exception as e:
        session.rollback()
        return False, f"Error saving setting: {e}"
    finally:
        session.close()


def get_all(db_name: str = "") -> dict:
    """Return all settings merged with defaults."""
    result = dict(DEFAULTS)
    session = get_session(db_name)
    try:
        for row in session.query(UserSetting).all():
            result[row.key] = row.value
        return result
    finally:
        session.close()
