"""
backend/app/agent_manager.py
CRUD for Agents, including full-field updates.
"""

from urllib.parse import urlparse
from sqlalchemy.exc import IntegrityError
from backend.app.database import get_session
from backend.app.models import Agent


def _is_valid_url(url: str) -> bool:
    try:
        r = urlparse(url)
        return r.scheme in ("http", "https") and bool(r.netloc)
    except Exception:
        return False


def create_agent(environment_id, name, api_url, model_name, system_prompt,
                 db_name="") -> tuple[bool, str]:
    name = name.strip()
    api_url = api_url.strip()
    model_name = model_name.strip()
    system_prompt = system_prompt.strip()
    if not name:
        return False, "Agent name cannot be empty."
    if not _is_valid_url(api_url):
        return False, "Enter a valid URL (http/https)."
    if not system_prompt: return False, "System prompt cannot be empty."
    if not model_name:    return False, "Model ID cannot be empty."

    session = get_session(db_name)
    try:
        session.add(Agent(environment_id=environment_id, name=name,
                          api_url=api_url, model_name=model_name,
                          system_prompt=system_prompt))
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


def update_agent(agent_id, name=None, api_url=None, model_name=None,
                 system_prompt=None, db_name="") -> tuple[bool, str]:
    """Update any combination of agent fields."""
    session = get_session(db_name)
    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent:
            return False, "Agent not found."
        if name is not None:
            name = name.strip()
            if not name: return False, "Name cannot be empty."
            agent.name = name
        if api_url is not None:
            api_url = api_url.strip()
            if not _is_valid_url(api_url): return False, "Enter a valid URL."
            agent.api_url = api_url
        if model_name is not None:
            model_name = model_name.strip()
            if not model_name: return False, "Model ID cannot be empty."
            agent.model_name = model_name
        if system_prompt is not None:
            system_prompt = system_prompt.strip()
            if not system_prompt: return False, "System prompt cannot be empty."
            agent.system_prompt = system_prompt
        session.commit()
        return True, "Agent updated."
    except IntegrityError:
        session.rollback()
        return False, "An agent with that name already exists in this environment."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def list_agents(environment_id, db_name="") -> list[dict]:
    session = get_session(db_name)
    try:
        agents = session.query(Agent).filter_by(environment_id=environment_id)\
                        .order_by(Agent.created_at.desc()).all()
        return [_to_dict(a) for a in agents]
    finally:
        session.close()


def get_agent(agent_id, db_name="") -> dict | None:
    session = get_session(db_name)
    try:
        a = session.query(Agent).filter_by(id=agent_id).first()
        return _to_dict(a) if a else None
    finally:
        session.close()


def get_agent_by_name(environment_id, name, db_name="") -> dict | None:
    session = get_session(db_name)
    try:
        a = session.query(Agent).filter_by(environment_id=environment_id,
                                           name=name.strip()).first()
        return _to_dict(a) if a else None
    finally:
        session.close()


def list_model_names(db_name="") -> list[str]:
    session = get_session(db_name)
    try:
        rows = session.query(Agent.model_name).distinct().all()
        return sorted({r[0] for r in rows if r[0]})
    except Exception:
        return []
    finally:
        session.close()


def delete_agent(agent_id, db_name="") -> tuple[bool, str]:
    session = get_session(db_name)
    try:
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent: return False, "Agent not found."
        session.delete(agent)
        session.commit()
        return True, "Agent deleted."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def _to_dict(a: Agent) -> dict:
    return {
        "id": a.id, "name": a.name, "api_url": a.api_url,
        "model_name": a.model_name, "system_prompt": a.system_prompt,
        "environment_id": a.environment_id,
        "created_at": a.created_at.strftime("%Y-%m-%d %H:%M"),
        "updated_at": a.updated_at.strftime("%Y-%m-%d %H:%M"),
    }
