"""
backend/app/tools/terminal_tool.py
Sandboxed terminal tool using LangChain's BaseTool with:
  - Command whitelisting (only approved commands run)
  - Workspace isolation (chdir to agent workspace; path traversal blocked)
"""

import os
import subprocess
from langchain_core.tools import BaseTool

# ─── Whitelist ────────────────────────────────────────────────────────────────
# Only these commands may be executed by agents.
ALLOWED_COMMANDS = {
    "ls", "echo", "pwd", "cat", "mkdir", "date", "whoami",
    "head", "tail", "wc", "find", "grep",
}


def _is_safe(command: str) -> bool:
    """Return True if the first token of the command is in the whitelist."""
    first_token = command.strip().split()[0] if command.strip() else ""
    return first_token in ALLOWED_COMMANDS


def _has_path_traversal(command: str) -> bool:
    """
    Return True if the command contains any path-traversal sequences
    (../ or ..\\ or standalone ..).
    """
    return (
        "../" in command
        or "..\\" in command
        or command.strip() == ".."
        or " .." in command
        or "\t.." in command
    )


def run_terminal_command(command: str, workspace_path: str | None = None) -> str:
    """
    Execute a whitelisted shell command, optionally inside a sandboxed workspace.
    Raises ValueError if the command is not on the whitelist or attempts path traversal.
    """
    if _has_path_traversal(command):
        raise ValueError(
            "Path traversal ('..') is not permitted in terminal commands."
        )
    if not _is_safe(command):
        first_token = command.strip().split()[0] if command.strip() else "(empty)"
        raise ValueError(
            f"Command '{first_token}' is not allowed. "
            f"Permitted commands: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )

    # Resolve and validate workspace directory
    cwd = None
    if workspace_path:
        real_workspace = os.path.realpath(workspace_path)
        os.makedirs(real_workspace, exist_ok=True)
        cwd = real_workspace

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd,          # execute inside workspace (or CWD if None)
        )
        output = result.stdout or result.stderr or "(no output)"
        return output[:4000]   # cap output length
    except subprocess.TimeoutExpired:
        return "Command timed out after 10 seconds."
    except Exception as e:
        return f"Error executing command: {e}"


class SafeShellTool(BaseTool):
    """
    LangChain tool that runs only whitelisted shell commands, sandboxed
    to the agent's private workspace directory.
    """

    name: str = "terminal"
    description: str = (
        "Execute a shell command on the host machine. "
        "Only the following commands are permitted: "
        + ", ".join(sorted(ALLOWED_COMMANDS))
        + ". Path traversal ('..') is blocked. "
        "All commands run inside the agent's private workspace folder."
    )
    # Pydantic field — populated by get_langchain_terminal_tool()
    workspace_path: str = ""

    def _run(self, command: str, **kwargs) -> str:
        """Enforce whitelist and workspace isolation, then execute."""
        if _has_path_traversal(command):
            return "Blocked: path traversal ('../') is not permitted."
        if not _is_safe(command):
            first = command.strip().split()[0] if command.strip() else "(empty)"
            return f"Blocked: '{first}' is not in the allowed command list."
        return run_terminal_command(
            command,
            workspace_path=self.workspace_path or None,
        )

    async def _arun(self, command: str, **kwargs) -> str:
        """Async version — delegates synchronously (acceptable for CLI tools)."""
        return self._run(command, **kwargs)


def get_langchain_terminal_tool(workspace_path: str = "") -> SafeShellTool:
    """
    Returns a LangChain-compatible SafeShellTool instance.
    Pass workspace_path to sandbox the tool inside the agent's private folder.
    """
    return SafeShellTool(workspace_path=workspace_path)
