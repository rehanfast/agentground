"""
backend/app/resource_callback.py
LangChain callback that enforces resource limits and streams live progress.
"""

import threading
import queue
from typing import Any, Dict, List, Optional, Union
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult


class AgentStopException(Exception):
    pass


class ResourceCallbackHandler(BaseCallbackHandler):
    """
    Intercepts LangChain events to:
    - Enforce max_calls and timeout_secs limits
    - Enforce rpm_limit (calls per minute) via throttling
    - Respect an external stop_event (Stop button)
    - Push live progress messages to a log_queue (for streaming UI)
    """

    def __init__(
        self,
        max_calls:    int = 10,
        timeout_secs: int = 60,
        rpm_limit:    int = 0,
        stop_event:   Optional[threading.Event] = None,
        log_queue:    Optional[queue.Queue] = None,
        agent_name:   str = "",
    ):
        super().__init__()
        self.max_calls    = max_calls
        self.timeout_secs = timeout_secs
        self.rpm_limit    = rpm_limit   # 0 = no RPM limit
        self.call_count   = 0
        self.stop_reason  = ""
        self._stop_event  = stop_event or threading.Event()
        self._timer: Optional[threading.Timer] = None
        self._log_q       = log_queue
        self.agent_name   = agent_name
        self._call_timestamps: list[float] = []  # for RPM sliding window

    def _log(self, msg: str) -> None:
        if self._log_q is not None:
            try:
                self._log_q.put_nowait(msg)
            except Exception:
                pass

    def start_timeout(self) -> None:
        self._timer = threading.Timer(self.timeout_secs, self._trigger_timeout)
        self._timer.daemon = True
        self._timer.start()

    def cancel_timeout(self) -> None:
        if self._timer and self._timer.is_alive():
            self._timer.cancel()

    def request_stop(self, reason: str = "User requested stop.") -> None:
        self.stop_reason = reason
        self._stop_event.set()

    def _trigger_timeout(self) -> None:
        self.stop_reason = f"Timeout after {self.timeout_secs}s."
        self._stop_event.set()

    def _check_limits(self) -> None:
        if self._stop_event.is_set():
            raise AgentStopException(self.stop_reason or "Run halted.")
        if self.call_count >= self.max_calls:
            self.stop_reason = f"Max API calls reached ({self.max_calls})."
            self._stop_event.set()
            raise AgentStopException(self.stop_reason)

    def _throttle_rpm(self) -> None:
        """Sleep if RPM limit would be exceeded (sliding 60s window)."""
        if not self.rpm_limit or self.rpm_limit <= 0:
            return
        import time
        now = time.time()
        cutoff = now - 60.0
        # Remove timestamps older than 60 seconds
        self._call_timestamps = [t for t in self._call_timestamps if t > cutoff]
        if len(self._call_timestamps) >= self.rpm_limit:
            # Wait until the oldest call in the window expires
            wait = self._call_timestamps[0] - cutoff
            wait = min(wait, 30.0)  # cap at 30s to avoid deadlock
            if wait > 0:
                self._log(f"⏳ RPM limit ({self.rpm_limit}/min) reached, throttling {wait:.0f}s…")
                if self._stop_event.wait(wait):
                    raise AgentStopException("Stopped by user during RPM throttle.")
        self._call_timestamps.append(time.time())

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        self._check_limits()
        self._throttle_rpm()
        self.call_count += 1
        prefix = f"**{self.agent_name}**" if self.agent_name else "Agent"
        self._log(f"🤖 {prefix} — calling LLM (call #{self.call_count}/{self.max_calls})…")

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        prefix = f"**{self.agent_name}**" if self.agent_name else "Agent"
        try:
            text = response.generations[0][0].text[:120].replace("\n", " ")
            self._log(f"💬 {prefix} received response: _{text}…_")
        except Exception:
            self._log(f"💬 {prefix} received LLM response.")

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs) -> None:
        self._check_limits()
        name = serialized.get("name", "tool")
        prefix = f"**{self.agent_name}**" if self.agent_name else "Agent"
        self._log(f"🔧 {prefix} → using tool `{name}`: `{str(input_str)[:100]}`")

    def on_tool_end(self, output: str, **kwargs) -> None:
        prefix = f"**{self.agent_name}**" if self.agent_name else "Agent"
        self._log(f"✅ {prefix} ← tool result: `{str(output)[:120]}`")

    def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs) -> None:
        self._check_limits()

    def on_agent_finish(self, finish, **kwargs) -> None:
        prefix = f"**{self.agent_name}**" if self.agent_name else "Agent"
        try:
            ans = str(finish.return_values.get("output", ""))[:120]
            self._log(f"🏁 {prefix} finished: _{ans}…_")
        except Exception:
            self._log(f"🏁 {prefix} finished.")
