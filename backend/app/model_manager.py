"""
backend/app/model_manager.py
CRUD for ModelConfig — the user-curated model registry.
Also provides model selection logic for Auto Mode.
"""

from __future__ import annotations

from backend.app.database import get_session
from backend.app.models import ModelConfig


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_models(db_name: str = "", active_only: bool = False) -> list[dict]:
    session = get_session(db_name)
    try:
        q = session.query(ModelConfig)
        if active_only:
            q = q.filter_by(is_active=True)
        models = q.order_by(ModelConfig.intelligence_rank, ModelConfig.display_name).all()
        return [_to_dict(m) for m in models]
    finally:
        session.close()


def get_model(model_config_id: int, db_name: str = "") -> dict | None:
    session = get_session(db_name)
    try:
        m = session.query(ModelConfig).filter_by(id=model_config_id).first()
        return _to_dict(m) if m else None
    finally:
        session.close()


def create_model(
    display_name: str, provider: str, model_id: str, api_url: str,
    api_keys: list[str], intelligence_rank: int, is_free_tier: bool,
    notes: str = "", db_name: str = "",
) -> tuple[bool, str]:
    display_name = display_name.strip()
    model_id     = model_id.strip()
    api_url      = api_url.strip()
    api_keys     = [k.strip() for k in api_keys if k.strip()]

    if not display_name: return False, "Display name required."
    if not model_id:     return False, "Model ID required."
    if not api_url:      return False, "API URL required."
    if not api_keys and provider != "ollama":
        return False, "At least one API key is required."

    session = get_session(db_name)
    try:
        m = ModelConfig(
            display_name=display_name, provider=provider, model_id=model_id,
            api_url=api_url, api_keys=api_keys, intelligence_rank=intelligence_rank,
            is_free_tier=is_free_tier, is_active=True, notes=notes,
        )
        session.add(m)
        session.commit()
        return True, f"Model '{display_name}' added."
    except Exception as e:
        session.rollback()
        if "Duplicate" in str(e) or "1062" in str(e):
            return False, f"A model named '{display_name}' already exists."
        return False, f"Database error: {e}"
    finally:
        session.close()


def update_model(model_config_id: int, db_name: str = "", **kwargs) -> tuple[bool, str]:
    session = get_session(db_name)
    try:
        m = session.query(ModelConfig).filter_by(id=model_config_id).first()
        if not m: return False, "Model not found."
        for k, v in kwargs.items():
            if hasattr(m, k):
                setattr(m, k, v)
        session.commit()
        return True, "Model updated."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


def delete_model(model_config_id: int, db_name: str = "") -> tuple[bool, str]:
    session = get_session(db_name)
    try:
        m = session.query(ModelConfig).filter_by(id=model_config_id).first()
        if not m: return False, "Model not found."
        session.delete(m)
        session.commit()
        return True, "Model deleted."
    except Exception as e:
        session.rollback()
        return False, f"Database error: {e}"
    finally:
        session.close()


# ── Auto Mode model selection ─────────────────────────────────────────────────

def pick_best_model(
    db_name: str = "",
    free_tier_only: bool = True,
    task_complexity: str = "medium",   # low | medium | high
) -> dict | None:
    """
    Return the highest-ranked active model for Auto Mode.
    Complexity adjusts how far down the rank list we're willing to go.
    """
    session = get_session(db_name)
    try:
        q = session.query(ModelConfig).filter_by(is_active=True)
        if free_tier_only:
            q = q.filter_by(is_free_tier=True)
        models = q.order_by(ModelConfig.intelligence_rank).all()
        if not models:
            # Fallback: any active model
            models = session.query(ModelConfig)\
                            .filter_by(is_active=True)\
                            .order_by(ModelConfig.intelligence_rank).all()
        return _to_dict(models[0]) if models else None
    finally:
        session.close()


def get_model_fallback_chain(db_name: str = "", free_tier_only: bool = True) -> list[dict]:
    """
    Return all active models sorted by intelligence_rank.
    Used by Auto Mode to try the best model first, falling back on error.
    """
    session = get_session(db_name)
    try:
        q = session.query(ModelConfig).filter_by(is_active=True)
        if free_tier_only:
            q = q.filter_by(is_free_tier=True)
        models = q.order_by(ModelConfig.intelligence_rank).all()
        if not models:
            models = session.query(ModelConfig)\
                            .filter_by(is_active=True)\
                            .order_by(ModelConfig.intelligence_rank).all()
        return [_to_dict(m) for m in models]
    finally:
        session.close()


def _to_dict(m: ModelConfig) -> dict:
    return {
        "id":                m.id,
        "display_name":      m.display_name,
        "provider":          m.provider,
        "model_id":          m.model_id,
        "api_url":           m.api_url,
        "api_keys":          m.api_keys or [],
        "intelligence_rank": m.intelligence_rank,
        "is_free_tier":      m.is_free_tier,
        "is_active":         m.is_active,
        "notes":             m.notes or "",
        "updated_at":        m.updated_at.strftime("%Y-%m-%d %H:%M"),
    }
