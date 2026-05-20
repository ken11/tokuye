"""
session.py
~~~~~~~~~~
API mode session management.

Each session holds:
  - A StrandsAgent (or EpicManagerAgent) instance
  - An asyncio.Queue for SSE events emitted by agent callbacks
  - The session_id (= agent thread_id, prefixed with "api-")

Session lifecycle
-----------------
  POST /new   → create_session() → returns session_id
  POST /sse   → get_session(session_id) → run one turn
  (process exit) → sessions are lost; FileSessionManager persists conversation history
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from tokuye.agent.strands_agent import StrandsAgent
from tokuye.utils.config import settings


@dataclass
class ApiSession:
    session_id: str
    agent: StrandsAgent
    # Queue of SSE event dicts; None is the sentinel for stream end.
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)


# ---------------------------------------------------------------------------
# Module-level session store
# ---------------------------------------------------------------------------

_sessions: Dict[str, ApiSession] = {}
_lock = asyncio.Lock()


def _make_thread_id() -> str:
    """Return a thread_id with the 'api-' prefix so FileSession files are
    distinguishable from TUI sessions at a glance."""
    return f"api-{uuid.uuid4()}"


async def create_session() -> ApiSession:
    """Instantiate a new agent and register the session.

    The agent's callbacks write SSE event dicts into the session queue.
    MCP initialisation is deferred to the first __call__ (lazy).
    """
    session_id = _make_thread_id()
    queue: asyncio.Queue = asyncio.Queue()

    def _add_ai_message(content: str) -> None:
        queue.put_nowait({"type": "ai_message", "content": content})

    def _add_system_message(content: str) -> None:
        queue.put_nowait({"type": "system_message", "content": content})

    def _set_thinking(flag: bool) -> None:
        # thinking=False is called by _request_approval() immediately after
        # posting the "Execute? y/n" system_message.  At that point
        # is_waiting_for_command_approval() is True, so we close the current
        # SSE stream with a sentinel.  The client will open a new /sse request
        # with "y" or "n" to resume the paused agent.
        if not flag:
            from tokuye.tools.strands_tools.project_command_tools import (
                is_waiting_for_command_approval,
            )
            if is_waiting_for_command_approval():
                queue.put_nowait(None)  # sentinel: close current SSE stream

    def _update_token_usage(_text: str) -> None:
        # Not surfaced in API mode
        pass

    agent = StrandsAgent(
        thread_id=session_id,
        max_steps=settings.max_steps,
        add_ai_message=_add_ai_message,
        add_system_message=_add_system_message,
        set_thinking=_set_thinking,
        update_token_usage=_update_token_usage,
    )

    # Register approval callbacks so run_project_command can prompt via SSE.
    from tokuye.tools.strands_tools.project_command_tools import (
        set_command_approval_callbacks,
    )
    set_command_approval_callbacks(
        add_system_message=_add_system_message,
        set_thinking=_set_thinking,
    )

    session = ApiSession(session_id=session_id, agent=agent, queue=queue)

    async with _lock:
        _sessions[session_id] = session

    return session


async def get_session(session_id: str) -> Optional[ApiSession]:
    """Return the session for *session_id*, or None if not found."""
    async with _lock:
        return _sessions.get(session_id)


async def delete_session(session_id: str) -> None:
    """Remove a session and clean up its agent."""
    async with _lock:
        session = _sessions.pop(session_id, None)
    if session is not None:
        await session.agent.cleanup()
