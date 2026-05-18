"""
project_command_tools.py
~~~~~~~~~~~~~~~~~~~~~~~~
Tokuye-specific tools for running project commands defined in config.yaml.

Two tools are provided:

  list_project_commands()
      Returns the list of allowed commands so the Agent can discover what is
      available before calling run_project_command.

  run_project_command(name, extra_args)
      Executes a named command after obtaining explicit user approval via the
      TUI.  The command is always run with ``subprocess.run(..., shell=False)``
      in the project root directory.

Approval flow
-------------
``run_project_command`` is defined as ``async def`` so Strands invokes it
directly on the event loop (not via asyncio.to_thread).  This lets us
``await approval_event.wait()`` while the TUI handles the next user message
in a separate ``@work`` coroutine on the same loop.

The TUI must:
  1. Call ``set_command_approval_callbacks`` once at startup to register the
     ``add_system_message`` and ``set_thinking`` callbacks.
  2. Check ``is_waiting_for_command_approval()`` in ``on_message`` and call
     ``resolve_command_approval(approved)`` with the user's y/n answer.

Root execution guard
--------------------
If the process is running as root (UID 0), ``run_project_command`` refuses to
execute any command.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, List, Optional

from strands import tool

from tokuye.utils.config import CommandPolicy, settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level approval state
# ---------------------------------------------------------------------------
# These are set once by set_command_approval_callbacks() called from the TUI.

_add_system_message: Optional[Callable[[str], None]] = None
_set_thinking: Optional[Callable[[bool], None]] = None

# asyncio.Event used to pause run_project_command until the user responds.
# A new Event is created for each approval request.
_approval_event: Optional[asyncio.Event] = None
_approval_result: bool = False  # True = approved, False = rejected


# ---------------------------------------------------------------------------
# Public setup API (called by TUI at startup)
# ---------------------------------------------------------------------------

def set_command_approval_callbacks(
    add_system_message: Callable[[str], None],
    set_thinking: Callable[[bool], None],
) -> None:
    """Register TUI callbacks used during the approval flow.

    Must be called once before any ``run_project_command`` invocation.
    """
    global _add_system_message, _set_thinking
    _add_system_message = add_system_message
    _set_thinking = set_thinking


def is_waiting_for_command_approval() -> bool:
    """Return True if run_project_command is currently waiting for approval."""
    return _approval_event is not None and not _approval_event.is_set()


def resolve_command_approval(approved: bool) -> None:
    """Called by the TUI when the user answers y/n.

    Sets the approval result and fires the event so run_project_command can
    resume.
    """
    global _approval_result, _approval_event
    _approval_result = approved
    if _approval_event is not None:
        _approval_event.set()


# ---------------------------------------------------------------------------
# Helper: resolve effective cwd
# ---------------------------------------------------------------------------

def _resolve_cwd(override: Optional[Path] = None) -> Path:
    """Return the working directory for subprocess execution.

    Priority:
      1. ``override`` (used by Epic Worker factory to bind a specific repo root)
      2. ``settings.project_root``
    """
    if override is not None:
        return override.resolve()
    if settings.project_root is None:
        raise ValueError("settings.project_root is not set; cannot determine cwd")
    return settings.project_root.resolve()


# ---------------------------------------------------------------------------
# Helper: resolve effective command policy
# ---------------------------------------------------------------------------

def _get_policy() -> CommandPolicy:
    """Return the active CommandPolicy, or an empty one if not configured."""
    if settings.command_policy is not None:
        return settings.command_policy  # type: ignore[return-value]
    return CommandPolicy()


# ---------------------------------------------------------------------------
# Tool: list_project_commands
# ---------------------------------------------------------------------------

@tool
def list_project_commands() -> dict:
    """List all project commands available for execution.

    Returns the commands defined in config.yaml ``command_policy.commands``.
    Use this tool first to discover what commands are available before calling
    ``run_project_command``.

    Returns:
        A dict with a ``commands`` list.  Each entry contains:
          - name: identifier used in run_project_command
          - description: human-readable description
          - resolved_prefix: the argv prefix that will be executed
          - allow_extra_args: whether extra_args are accepted
          - timeout: effective timeout in seconds
          - usage: example invocation dict
    """
    policy = _get_policy()
    result = []
    for cmd in policy.commands:
        effective_timeout = cmd.timeout if cmd.timeout is not None else policy.default_timeout
        result.append({
            "name": cmd.name,
            "description": cmd.description,
            "resolved_prefix": [cmd.command, *cmd.fixed_args],
            "allow_extra_args": cmd.allow_extra_args,
            "timeout": effective_timeout,
            "usage": {
                "name": cmd.name,
                "extra_args": ["<arg1>", "<arg2>"] if cmd.allow_extra_args else [],
            },
        })
    return {"commands": result}


# ---------------------------------------------------------------------------
# Tool: run_project_command
# ---------------------------------------------------------------------------

@tool
async def run_project_command(
    name: str,
    extra_args: Optional[List[str]] = None,
) -> dict:
    """Execute a project command defined in config.yaml after user approval.

    The command must be listed in ``command_policy.commands`` in config.yaml.
    Use ``list_project_commands`` first to see what is available.

    The tool will:
      1. Look up the command by name.
      2. Validate extra_args against allow_extra_args.
      3. Display the planned command in the TUI and ask for y/n approval.
      4. If approved, run the command with subprocess (shell=False).
      5. Return stdout / stderr / exit_code to the Agent.

    Args:
        name: The command name as defined in config.yaml (e.g. "test", "lint").
        extra_args: Additional arguments appended after fixed_args.
                    Only allowed when allow_extra_args is true for the command.

    Returns:
        A dict with keys: status, command, cwd, exit_code, stdout, stderr.
        status is one of: "success", "error", "cancelled", "timeout".
    """
    # Refuse root execution
    if os.getuid() == 0:
        return {
            "status": "error",
            "message": "Refusing to run project commands as root.",
        }

    if extra_args is None:
        extra_args = []

    policy = _get_policy()
    cmd_entry = policy.find(name)

    if cmd_entry is None:
        available = [c.name for c in policy.commands]
        return {
            "status": "error",
            "message": (
                f"Unknown command name: {name!r}. "
                f"Available commands: {available}. "
                "Use list_project_commands to see the full list."
            ),
        }

    if extra_args and not cmd_entry.allow_extra_args:
        return {
            "status": "error",
            "message": (
                f"Command {name!r} does not allow extra_args, "
                f"but received: {extra_args!r}"
            ),
        }

    argv = [cmd_entry.command, *cmd_entry.fixed_args, *extra_args]
    effective_timeout = (
        cmd_entry.timeout if cmd_entry.timeout is not None else policy.default_timeout
    )

    try:
        cwd = _resolve_cwd()
    except ValueError as e:
        return {"status": "error", "message": str(e)}

    # --- Approval flow ---------------------------------------------------
    approved = await _request_approval(argv, cwd)
    if not approved:
        return {
            "status": "cancelled",
            "message": "Command execution was rejected by the user.",
        }

    # --- Execute ---------------------------------------------------------
    result = await _run_subprocess(argv, cwd, effective_timeout, policy.max_output_chars)
    _report_result(argv, result)
    return result


# ---------------------------------------------------------------------------
# Epic Worker factory: cwd-bound variants
# ---------------------------------------------------------------------------

def make_project_command_tools_for(repo_root: Path) -> list:
    """Return run_project_command / list_project_commands bound to *repo_root*.

    Used by make_epic_worker_tools to give Epic Workers a sandboxed cwd.
    The returned tools have the same names as the standard tools so the
    Worker's system prompt needs no changes.
    """
    from strands import tool as _tool

    repo_root = repo_root.resolve()

    @_tool(
        name="list_project_commands",
        description=(
            "List all project commands available for execution. "
            "Returns the commands defined in config.yaml command_policy.commands."
        ),
    )
    def _list_project_commands() -> dict:
        policy = _get_policy()
        result = []
        for cmd in policy.commands:
            effective_timeout = cmd.timeout if cmd.timeout is not None else policy.default_timeout
            result.append({
                "name": cmd.name,
                "description": cmd.description,
                "resolved_prefix": [cmd.command, *cmd.fixed_args],
                "allow_extra_args": cmd.allow_extra_args,
                "timeout": effective_timeout,
                "usage": {
                    "name": cmd.name,
                    "extra_args": ["<arg1>", "<arg2>"] if cmd.allow_extra_args else [],
                },
            })
        return {"commands": result}

    @_tool(
        name="run_project_command",
        description=(
            "Execute a project command defined in config.yaml after user approval. "
            "The command is run in the worker's repository root directory."
        ),
    )
    async def _run_project_command(
        name: str,
        extra_args: Optional[List[str]] = None,
    ) -> dict:
        if os.getuid() == 0:
            return {
                "status": "error",
                "message": "Refusing to run project commands as root.",
            }

        if extra_args is None:
            extra_args = []

        policy = _get_policy()
        cmd_entry = policy.find(name)

        if cmd_entry is None:
            available = [c.name for c in policy.commands]
            return {
                "status": "error",
                "message": (
                    f"Unknown command name: {name!r}. "
                    f"Available commands: {available}."
                ),
            }

        if extra_args and not cmd_entry.allow_extra_args:
            return {
                "status": "error",
                "message": (
                    f"Command {name!r} does not allow extra_args, "
                    f"but received: {extra_args!r}"
                ),
            }

        argv = [cmd_entry.command, *cmd_entry.fixed_args, *extra_args]
        effective_timeout = (
            cmd_entry.timeout if cmd_entry.timeout is not None else policy.default_timeout
        )
        cwd = repo_root

        approved = await _request_approval(argv, cwd)
        if not approved:
            return {
                "status": "cancelled",
                "message": "Command execution was rejected by the user.",
            }

        result = await _run_subprocess(argv, cwd, effective_timeout, policy.max_output_chars)
        _report_result(argv, result)
        return result

    return [_list_project_commands, _run_project_command]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _request_approval(argv: List[str], cwd: Path) -> bool:
    """Display approval prompt in TUI and await user response.

    Returns True if the user approved, False otherwise.

    Guards against concurrent calls: if another approval is already in
    progress (``_approval_event`` exists and has not been set yet), this
    call rejects immediately rather than overwriting the shared state.
    """
    global _approval_event, _approval_result

    # Guard: reject immediately if a concurrent approval is already pending.
    if _approval_event is not None and not _approval_event.is_set():
        logger.warning(
            "run_project_command: concurrent approval request detected; rejecting."
        )
        return False

    cmd_str = " ".join(argv)
    prompt = (
        "Planned command:\n"
        f"{cmd_str}\n\n"
        "Working directory:\n"
        f"{cwd}\n\n"
        "Execute? y/n"
    )

    if _add_system_message is None or _set_thinking is None:
        # Callbacks not registered (e.g. in tests); default to reject for safety.
        logger.warning(
            "run_project_command: approval callbacks not registered; rejecting."
        )
        return False

    # Create a fresh Event for this approval request.
    _approval_event = asyncio.Event()
    _approval_result = False

    # Show prompt and temporarily re-enable input so the user can type.
    _add_system_message(prompt)
    _set_thinking(False)

    try:
        # Yield control to the event loop until resolve_command_approval() fires.
        await _approval_event.wait()
    finally:
        # Always restore thinking state and clear the event, even if the
        # coroutine is cancelled (e.g. CancelledError) or another exception
        # is raised.
        _set_thinking(True)
        _approval_event = None

    return _approval_result


async def _run_subprocess(
    argv: List[str],
    cwd: Path,
    timeout: int,
    max_output_chars: int,
) -> dict:
    """Run *argv* as a subprocess and return a result dict."""
    try:
        completed = await asyncio.to_thread(
            subprocess.run,
            argv,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout_partial = exc.stdout or ""
        stderr_partial = exc.stderr or ""
        return {
            "status": "timeout",
            "command": argv,
            "cwd": str(cwd),
            "exit_code": 124,
            "stdout": _truncate(stdout_partial, max_output_chars),
            "stderr": _truncate(
                stderr_partial + f"\nCommand timed out after {timeout} seconds",
                max_output_chars,
            ),
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Failed to execute command: {exc}",
            "command": argv,
            "cwd": str(cwd),
        }

    status = "success" if completed.returncode == 0 else "error"
    return {
        "status": status,
        "command": argv,
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "stdout": _truncate(completed.stdout, max_output_chars),
        "stderr": _truncate(completed.stderr, max_output_chars),
    }


def _report_result(argv: List[str], result: dict) -> None:
    """Post a system message to the TUI summarising the execution result."""
    if _add_system_message is None:
        return

    cmd_str = " ".join(argv)
    status = result.get("status", "unknown")
    exit_code = result.get("exit_code", "N/A")

    lines = [
        "Command executed:",
        cmd_str,
        "",
        f"Exit code: {exit_code}",
        "",
        f"Status: {status}",
    ]

    if status in ("error", "timeout"):
        stderr = result.get("stderr", "")
        if stderr:
            # Show up to 500 chars of stderr in the TUI message.
            stderr_preview = stderr[:500] + ("..." if len(stderr) > 500 else "")
            lines += ["", "Stderr:", stderr_preview]

    _add_system_message("\n".join(lines))


def _truncate(text: str, max_chars: int) -> str:
    """Truncate *text* to *max_chars* characters, appending a notice if cut."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n... (truncated at {max_chars} chars)"
