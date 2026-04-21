"""
backend/app/run_manager.py
Creates, updates, and retrieves Run records.
"""

from datetime import datetime
from backend.app.database import get_session
from backend.app.models import Run


def create_run(environment_id: int) -> int:
    """Insert a new Run record with status='running'. Returns run_id."""
    session = get_session()
    try:
        run = Run(
            environment_id=environment_id,
            status="running",
            started_at=datetime.utcnow(),
        )
        session.add(run)
        session.commit()
        return run.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_run_status(run_id: int, status: str) -> None:
    """Update a run's status and set ended_at for terminal statuses."""
    terminal = {"completed", "stopped", "failed"}
    session = get_session()
    try:
        run = session.query(Run).filter_by(id=run_id).first()
        if run:
            run.status = status
            if status in terminal:
                run.ended_at = datetime.utcnow()
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_runs_for_env(environment_id: int) -> list[dict]:
    """Return all runs for an environment, newest first."""
    session = get_session()
    try:
        runs = (
            session.query(Run)
            .filter_by(environment_id=environment_id)
            .order_by(Run.created_at.desc())
            .all()
        )
        return [
            {
                "id":         r.id,
                "status":     r.status,
                "started_at": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else None,
                "ended_at":   r.ended_at.strftime("%Y-%m-%d %H:%M:%S")   if r.ended_at   else None,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "log_count":  len(r.audit_logs),
            }
            for r in runs
        ]
    finally:
        session.close()
