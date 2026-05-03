"""
backend/app/key_manager.py
Multi-key rotation and rate-limit-aware fallback for LLM providers.

Strategy:
  1. Keys for a model are stored as a JSON array in ModelConfig.api_keys.
  2. A process-level rotating index advances after every use.
  3. On 429 / quota / auth error, that key is cooled down for COOLDOWN_SECS.
  4. If ALL keys are cooled down, we wait up to EXHAUSTION_WAIT_SECS for one
     to recover, then try again.
  5. If still failing after MAX_GLOBAL_RETRIES, raise a clean error.

Thread-safe: all state lives in a threading.Lock-protected dict.
"""

from __future__ import annotations

import time
import threading
from typing import Callable, Optional

# Circular import prevention
try:
    from backend.app.resource_callback import AgentStopException
except ImportError:
    class AgentStopException(Exception): pass

COOLDOWN_SECS       = 65     # wait after a 429 before retrying a key (Google quotas reset per min)
EXHAUSTION_WAIT_SECS = 65    # how long to wait when ALL keys are cooled
MAX_GLOBAL_RETRIES  = 5      # total attempts across all keys before giving up


_lock  = threading.Lock()
# { model_config_id: { "index": int, "cooldowns": { key: expires_at_unix } } }
_state: dict[int, dict] = {}


def _get_state(model_id: int) -> dict:
    if model_id not in _state:
        _state[model_id] = {"index": 0, "cooldowns": {}}
    return _state[model_id]


def _is_cooled(state: dict, key: str) -> bool:
    expires = state["cooldowns"].get(key, 0)
    return time.time() < expires


def _cool(state: dict, key: str) -> None:
    state["cooldowns"][key] = time.time() + COOLDOWN_SECS


def _available_keys(keys: list[str], state: dict) -> list[str]:
    return [k for k in keys if not _is_cooled(state, k)]


def _is_rate_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    if "too many tool" in msg or "tool execution" in msg:
        return False
    return any(t in msg for t in ("429", "rate limit", "quota", "too many requests"))


def _is_auth_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(t in msg for t in ("401", "403", "authentication", "unauthorized", "invalid api key"))


def _is_network_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(t in msg for t in ("network is unreachable", "connecterror", "connection refused", "timeout", "readtimeout", "connectionerror", "101", "111"))


def _is_model_error(exc: Exception) -> bool:
    """Non-transient errors where retrying the same model won't help."""
    msg = str(exc).lower()
    return any(t in msg for t in (
        "404", "not found", "does not exist", "model_not_found",
        "invalid model", "unsupported model", "no such model",
        "billing", "insufficient", "payment required", "402",
    ))


def get_next_key(model_config_id: int, keys: list[str]) -> str | None:
    """Return the next available (non-cooled) key, rotating round-robin."""
    if not keys:
        return None
    with _lock:
        state = _get_state(model_config_id)
        avail = _available_keys(keys, state)
        if not avail:
            return None
        # Advance to next available key from current index
        n = len(keys)
        start = state["index"] % n
        for offset in range(n):
            key = keys[(start + offset) % n]
            if not _is_cooled(state, key):
                state["index"] = (start + offset + 1) % n
                return key
        return None


def mark_key_failed(model_config_id: int, key: str, exc: Exception) -> None:
    """Cool down a key after a rate-limit or auth failure."""
    with _lock:
        state = _get_state(model_config_id)
        _cool(state, key)


def run_with_rotation(
    model_config_id: int,
    keys: list[str],
    fn: Callable[[str], any],
    log_fn: Callable[[str], None] | None = None,
    stop_event: Optional[threading.Event] = None,
) -> any:
    """
    Call fn(api_key) with automatic key rotation and retry.

    fn must accept a single string (the API key) and either return a result
    or raise an exception. Exceptions matching _is_rate_error or _is_auth_error
    trigger key cooldown + retry.

    Raises RuntimeError if all retries are exhausted.
    """
    def _log(msg: str):
        if log_fn: log_fn(msg)

    for attempt in range(MAX_GLOBAL_RETRIES):
        key = get_next_key(model_config_id, keys)

        if key is None:
            # All keys cooled — wait briefly for recovery
            _log(f"⏳ All keys on cooldown, waiting {EXHAUSTION_WAIT_SECS}s…")
            if stop_event:
                if stop_event.wait(EXHAUSTION_WAIT_SECS):
                    raise AgentStopException("Stopped by user during cooldown.")
            else:
                time.sleep(EXHAUSTION_WAIT_SECS)
            # Reset cooldowns that have expired
            with _lock:
                state = _get_state(model_config_id)
                now = time.time()
                state["cooldowns"] = {k: v for k, v in state["cooldowns"].items()
                                      if v > now}
            key = get_next_key(model_config_id, keys)
            if key is None:
                raise RuntimeError(
                    "All API keys are exhausted and still rate-limited. "
                    "Add more keys in Settings → Model Registry."
                )

        try:
            return fn(key)
        except Exception as exc:
            if _is_model_error(exc):
                # Non-transient: retrying this model won't help
                raise
            elif _is_network_error(exc):
                _log(f"🌐 Network error (attempt {attempt+1}/{MAX_GLOBAL_RETRIES}). Waiting 5s… ({exc})")
                if stop_event:
                    if stop_event.wait(5):
                        raise AgentStopException("Stopped by user during retry wait.")
                else:
                    time.sleep(5)
                # Do not cool down the key, just rotate/retry
            elif _is_rate_error(exc):
                _log(f"⚠️ Rate limit hit (attempt {attempt+1}/{MAX_GLOBAL_RETRIES}), "
                     f"cooling key and rotating…")
                mark_key_failed(model_config_id, key, exc)
            elif _is_auth_error(exc):
                _log(f"🔑 Auth error on key …{key[-6:]}, skipping.")
                mark_key_failed(model_config_id, key, exc)
            else:
                raise  # non-rate errors propagate immediately

    raise RuntimeError(
        f"API call failed after {MAX_GLOBAL_RETRIES} attempts across all keys."
    )
