"""
backend/app/tool_manager.py
Manages built-in tool listing and agent-tool assignments.
"""

from sqlalchemy.exc import IntegrityError
from backend.app.database import get_session
from backend.app.models import Tool, AgentTool, Agent


def list_tools() -> list[dict]:
    """Return all tools in the tools table."""
    session = get_session()
    try:
        tools = session.query(Tool).order_by(Tool.id).all()
        return [
            {
                "id":          t.id,
                "name":        t.name,
                "description": t.description or "",
                "is_builtin":  t.is_builtin,
            }
            for t in tools
        ]
    finally:
        session.close()


def get_agent_tools(agent_id: int) -> list[dict]:
    """Return all tools assigned to a specific agent."""
    session = get_session()
    try:
        assignments = (
            session.query(AgentTool)
            .filter_by(agent_id=agent_id)
            .all()
        )
        return [
            {
                "assignment_id": at.id,
                "tool_id":       at.tool_id,
                "tool_name":     at.tool.name,
                "description":   at.tool.description,
                "scope":         at.scope,
                "created_at":    at.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for at in assignments
        ]
    finally:
        session.close()


def assign_tool(agent_id: int, tool_id: int, scope: str = "private") -> tuple[bool, str]:
    """
    Assign a tool to an agent.
    scope must be 'private' or 'shared'.
    """
    if scope not in ("private", "shared"):
        return False, "Scope must be 'private' or 'shared'."

    session = get_session()
    try:
        # Verify agent exists
        agent = session.query(Agent).filter_by(id=agent_id).first()
        if not agent:
            return False, "Agent not found."
        # Verify tool exists
        tool = session.query(Tool).filter_by(id=tool_id).first()
        if not tool:
            return False, "Tool not found."

        assignment = AgentTool(agent_id=agent_id, tool_id=tool_id, scope=scope)
        session.add(assignment)
        session.commit()
        return True, f"'{tool.name}' assigned to '{agent.name}' (scope: {scope})."
    except IntegrityError:
        session.rollback()
        return False, "This tool is already assigned to the selected agent."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def remove_tool_assignment(assignment_id: int) -> tuple[bool, str]:
    """Remove a tool assignment from an agent."""
    session = get_session()
    try:
        at = session.query(AgentTool).filter_by(id=assignment_id).first()
        if not at:
            return False, "Assignment not found."
        session.delete(at)
        session.commit()
        return True, "Tool assignment removed."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()
