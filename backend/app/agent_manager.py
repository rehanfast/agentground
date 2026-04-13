"""
backend/app/agent_manager.py
CRUD operations for Agents.
"""

from urllib.parse import urlparse
from sqlalchemy.exc import IntegrityError
from backend.app.database import get_session
from backend.app.models import Agent


def _is_valid_url(url: str) -> bool:
    """Return True if url is a valid http/https URL."""
    try:
        result = urlparse(url)
        return result.scheme in ("http", "https") and bool(result.netloc)
    except Exception:
        return False


def create_agent(
    environment_id: int,
    name: str,
    api_url: str,
    model_name: str,
    system_prompt: str,
) -> tuple[bool, str]:
    """
    Register a new agent in a given environment.
    Returns (True, "ok") on success, (False, error_message) on failure.
    """
    name          = name.strip()
    api_url       = api_url.strip()
    model_name    = model_name.strip()
    system_prompt = system_prompt.strip()

    if not name:
        return False, "Agent name cannot be empty."
    if not _is_valid_url(api_url):
        return False, "Please enter a valid URL starting with http:// or https://"
    if not system_prompt:
        return False, "System prompt cannot be empty."
    if not model_name:
        model_name = "gpt-4"

    session = get_session()
    try:
        agent = Agent(
            environment_id=environment_id,
            name=name,
            api_url=api_url,
            model_name=model_name,
            system_prompt=system_prompt,
        )
        session.add(agent)
        session.commit()
        return True, "Agent registered successfully."
    except IntegrityError:
        session.rollback()
        return False, f"An agent named '{name}' already exists in this environment."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def list_agents(environment_id: int) -> list[dict]:
    """Return all agents in a given environment."""
    session = get_session()
    try:
        agents = (
            session.query(Agent)
            .filter_by(environment_id=environment_id)
            .order_by(Agent.created_at.desc())
            .all()
        )
        return [
            {
                "id":            a.id,
                "name":          a.name,
                "api_url":       a.api_url,
                "model_name":    a.model_name,
                "system_prompt": a.system_prompt,
                "created_at":    a.created_at.strftime("%Y-%m-%d %H:%M"),
                "updated_at":    a.updated_at.strftime("%Y-%m-%d %H:%M"),
            }
            for a in agents
        ]
    finally:
        session.close()


def get_agent(agent_id: int) -> dict | None:
    """Return a single agent dict by ID, or None."""
    session = get_session()
    try:
        a = session.query(Agent).filter_by(id=agent_id).first()
        if not a:
            return None
        return {
            "id":            a.id,
            "name":          a.name,
            "api_url":       a.api_url,
            "model_name":    a.model_name,
            "system_prompt": a.system_prompt,
            "environment_id":a.environment_id,
            "created_at":    a.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at":    a.updated_at.strftime("%Y-%m-%d %H:%M"),
        }
    finally:
        session.close()


def update_system_prompt(agent_id: int, new_prompt: str) -> tuple[bool, str]:
    """Update the system prompt of an existing agent."""
    new_prompt = new_prompt.strip()
    if not new_prompt:
        return False, "System prompt cannot be empty."

    session = get_session()
    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent:
            return False, "Agent not found."
        agent.system_prompt = new_prompt
        session.commit()
        return True, "System prompt updated successfully."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def delete_agent(agent_id: int) -> tuple[bool, str]:
    """Delete an agent and all its tool assignments."""
    session = get_session()
    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent:
            return False, "Agent not found."
        session.delete(agent)
        session.commit()
        return True, "Agent deleted successfully."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()
