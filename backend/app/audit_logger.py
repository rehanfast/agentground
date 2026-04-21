"""
backend/app/audit_logger.py
Writes and reads audit log entries for agent runs.
"""

import json
from datetime import datetime
from backend.app.database import get_session
from backend.app.models import AuditLog, Run


def log_step(
    run_id:      int,
    agent_id:    int,
    step_number: int,
    action_type: str,
    payload:     dict | None = None,
) -> None:
    """
    Insert one step into the audit_logs table.

    action_type should be one of:
        'llm_request'  — prompt sent to LLM
        'llm_response' — response received from LLM
        'tool_call'    — tool invocation with input
        'tool_result'  — tool output returned
        'run_stopped'  — run halted by limit or user
        'run_error'    — unexpected error during run
    """
    session = get_session()
    try:
        entry = AuditLog(
            run_id=run_id,
            agent_id=agent_id,
            step_number=step_number,
            action_type=action_type,
            payload=payload or {},
        )
        session.add(entry)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_logs(run_id: int) -> list[dict]:
    """Return all audit log entries for a run, ordered by step_number."""
    session = get_session()
    try:
        logs = (
            session.query(AuditLog)
            .filter_by(run_id=run_id)
            .order_by(AuditLog.step_number)
            .all()
        )
        return [
            {
                "id":          e.id,
                "run_id":      e.run_id,
                "agent_id":    e.agent_id,
                "agent_name":  e.agent.name if e.agent else "Unknown",
                "step_number": e.step_number,
                "action_type": e.action_type,
                "payload":     e.payload or {},
                "created_at":  e.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for e in logs
        ]
    finally:
        session.close()


def export_json(run_id: int) -> str:
    """Return the full audit log for a run as a JSON string."""
    logs = get_logs(run_id)
    return json.dumps(logs, indent=2, default=str)
