"""
backend/app/tools/terminal_tool.py
Sandboxed terminal tool using LangChain's ShellTool with command whitelisting.
Only whitelisted commands are allowed to run.
"""

import subprocess
from langchain_community.tools import ShellTool

# ─── Whitelist ────────────────────────────────────────────────────────────────
# Only these commands may be executed by agents.
# Add to this list carefully — each addition is a security decision.
ALLOWED_COMMANDS = {
    "ls", "echo", "pwd", "cat", "mkdir", "date", "whoami",
    "head", "tail", "wc", "find", "grep",
}


def _is_safe(command: str) -> bool:
    """Return True if the first token of the command is in the whitelist."""
    first_token = command.strip().split()[0] if command.strip() else ""
    return first_token in ALLOWED_COMMANDS


def run_terminal_command(command: str) -> str:
    """
    Execute a whitelisted shell command and return its output as a string.
    Raises ValueError if the command is not on the whitelist.
    Used by the LangChain agent loop in Sprint 2.
    """
    if not _is_safe(command):
        first_token = command.strip().split()[0] if command.strip() else "(empty)"
        raise ValueError(
            f"Command '{first_token}' is not allowed. "
            f"Permitted commands: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,        # 10-second hard timeout per command
        )
        output = result.stdout or result.stderr or "(no output)"
        return output[:4000]   # cap output length
    except subprocess.TimeoutExpired:
        return "Command timed out after 10 seconds."
    except Exception as e:
        return f"Error executing command: {e}"


def get_langchain_terminal_tool():
    """
    Returns a LangChain ShellTool configured with the whitelist check.
    This tool object is passed to the LangChain agent in Sprint 2.
    """
    # We wrap ShellTool's _run to enforce the whitelist.
    base_tool = ShellTool()

    original_run = base_tool._run

    def safe_run(commands: str, **kwargs):
        if not _is_safe(commands):
            first = commands.strip().split()[0] if commands.strip() else "(empty)"
            return f"Blocked: '{first}' is not in the allowed command list."
        return original_run(commands, **kwargs)

    base_tool._run = safe_run
    base_tool.description = (
        "Runs whitelisted shell commands. "
        f"Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}. "
        "Any other command will be blocked."
    )
    return base_tool
