"""
backend/app/resource_callback.py
LangChain Callback that enforces:
  - Maximum LLM API call limit per run
  - Execution timeout (set externally via stop_flag)
  - Stop-on-demand (set via stop_flag in session or externally)
"""

import threading
from typing import Any, Dict, List, Optional, Union
from langchain.callbacks.base import BaseCallbackHandler
from langchain.schema import LLMResult


class ResourceCallbackHandler(BaseCallbackHandler):
    """
    Intercepts LangChain agent events to enforce resource limits.

    Usage:
        callback = ResourceCallbackHandler(max_calls=10, timeout_secs=60)
        callback.start_timeout()
        executor.invoke(..., config={"callbacks": [callback]})
    """

    def __init__(self, max_calls: int = 10, timeout_secs: int = 60):
        super().__init__()
        self.max_calls    = max_calls
        self.timeout_secs = timeout_secs
        self.call_count   = 0
        self.stop_flag    = False
        self.stop_reason  = ""
        self._timer: Optional[threading.Timer] = None

    # ── Timeout ────────────────────────────────────────────────────────────────
    def start_timeout(self):
        """Start the wall-clock timeout timer."""
        self._timer = threading.Timer(self.timeout_secs, self._trigger_timeout)
        self._timer.daemon = True
        self._timer.start()

    def cancel_timeout(self):
        """Cancel the timer on clean completion."""
        if self._timer and self._timer.is_alive():
            self._timer.cancel()

    def _trigger_timeout(self):
        self.stop_flag  = True
        self.stop_reason = f"Execution timeout after {self.timeout_secs} seconds."

    # ── Stop on demand ─────────────────────────────────────────────────────────
    def request_stop(self, reason: str = "User requested stop."):
        """Call this to stop the agent from outside the callback."""
        self.stop_flag  = True
        self.stop_reason = reason

    # ── LangChain hooks ────────────────────────────────────────────────────────
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Called before every LLM API call."""
        self._check_limits()
        self.call_count += 1

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        pass

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        """Called before every tool execution."""
        self._check_limits()

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        self._check_limits()

    # ── Internal ───────────────────────────────────────────────────────────────
    def _check_limits(self):
        """Raise StopIteration if any limit is breached."""
        if self.stop_flag:
            raise StopIteration(self.stop_reason or "Run halted.")
        if self.call_count >= self.max_calls:
            self.stop_flag  = True
            self.stop_reason = f"API call limit reached ({self.max_calls} calls)."
            raise StopIteration(self.stop_reason)
