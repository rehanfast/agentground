"""
backend/app/run_manager.py
Creates, updates, and retrieves Run records.
Auto-migrates the `config` column if it's missing (handles upgrades gracefully).
"""

from datetime import datetime
from sqlalchemy import text
from backend.app.database import get_session, _get_user_engine
from backend.app.models import Run

def create_run(environment_id: int, config: dict | None = None,
               db_name: str = "") -> int:
    session = get_session(db_name)
    try:
        run = Run(environment_id=environment_id, status="running",
                  started_at=datetime.utcnow(), config=config or {})
        session.add(run)
        session.commit()
        return run.id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_run_status(run_id: int, status: str, db_name: str = "") -> None:
    session = get_session(db_name)
    try:
        run = session.query(Run).filter_by(id=run_id).first()
        if run:
            run.status = status
            if status in {"completed", "stopped", "failed"}:
                run.ended_at = datetime.utcnow()
            session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_runs_for_env(environment_id: int, db_name: str = "") -> list[dict]:
    session = get_session(db_name)
    try:
        runs = session.query(Run).filter_by(environment_id=environment_id) \
                      .order_by(Run.created_at.desc()).all()
        return [_to_dict(r) for r in runs]
    finally:
        session.close()


def get_run(run_id: int, db_name: str = "") -> dict | None:
    if db_name:
        _ensure_config_column(db_name)
    session = get_session(db_name)
    try:
        r = session.query(Run).filter_by(id=run_id).first()
        return _to_dict(r) if r else None
    finally:
        session.close()


def _to_dict(r: Run) -> dict:
    config = {}
    try:
        config = r.config or {}
    except Exception:
        pass
    return {
        "id":         r.id,
        "status":     r.status,
        "started_at": r.started_at.strftime("%Y-%m-%d %H:%M:%S") if r.started_at else None,
        "ended_at":   r.ended_at.strftime("%Y-%m-%d %H:%M:%S")   if r.ended_at   else None,
        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        "log_count":  len(r.audit_logs),
        "config":     config,
    }
