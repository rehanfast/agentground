"""
backend/app/env_manager.py
CRUD operations for Environments.
All public functions accept db_name to route queries to the correct
per-user database (agentground_<username>).
"""

from sqlalchemy.exc import IntegrityError
from backend.app.database import get_session
from backend.app.models import Environment


def create_environment(name: str, description: str = "", db_name: str = "") -> tuple[bool, str]:
    """
    Create a new environment.
    Returns (True, "ok") on success, (False, error_message) on failure.
    """
    name = name.strip()
    if not name:
        return False, "Environment name cannot be empty."
    if len(name) > 100:
        return False, "Environment name must not exceed 100 characters."

    session = get_session(db_name)
    try:
        env = Environment(name=name, description=description.strip())
        session.add(env)
        session.commit()
        return True, "Environment created successfully."
    except IntegrityError:
        session.rollback()
        return False, f"An environment named '{name}' already exists."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def list_environments(db_name: str = "") -> list[dict]:
    """Return all environments as a list of dicts."""
    session = get_session(db_name)
    try:
        envs = session.query(Environment).order_by(Environment.created_at.desc()).all()
        return [
            {
                "id":          e.id,
                "name":        e.name,
                "description": e.description or "",
                "created_at":  e.created_at.strftime("%Y-%m-%d %H:%M"),
                "agent_count": len(e.agents),
            }
            for e in envs
        ]
    finally:
        session.close()


def get_environment(env_id: int, db_name: str = "") -> dict | None:
    """Return a single environment dict by ID, or None."""
    session = get_session(db_name)
    try:
        e = session.query(Environment).filter_by(id=env_id).first()
        if not e:
            return None
        return {
            "id":          e.id,
            "name":        e.name,
            "description": e.description or "",
            "created_at":  e.created_at.strftime("%Y-%m-%d %H:%M"),
            "agent_count": len(e.agents),
        }
    finally:
        session.close()


def delete_environment(env_id: int, db_name: str = "") -> tuple[bool, str]:
    """Delete an environment and all its children (cascade)."""
    session = get_session(db_name)
    try:
        env = session.query(Environment).filter_by(id=env_id).first()
        if not env:
            return False, "Environment not found."
        session.delete(env)
        session.commit()
        return True, "Environment deleted successfully."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()
