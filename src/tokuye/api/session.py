"""
session.py
~~~~~~~~~~
API mode session management.

Each session holds:
  - A StrandsAgent (or EpicManagerAgent) instance
  - An asyncio.Queue for SSE events emitted by agent callbacks  (POST /sse)
  - A TurnStore for the async turn / event API  (POST /turn + GET /events)
  - The session_id (= agent thread_id, prefixed with "api-")

Session lifecycle
-----------------
  POST /new   → create_session() → returns session_id
  POST /sse   → get_session(session_id) → run one turn (legacy)
  POST /turn  → get_session(session_id) → start_turn() → returns turn_id immediately
  GET /events → stream events from TurnStore
  (process exit) → sessions are lost; FileSessionManager persists conversation history

Session restore after process restart
--------------------------------------
  FileSessionManager persists conversation history under
  <project_root>/.tokuye/sessions/session_<session_id>/.
  When a request arrives with a session_id that is not in the in-memory
  store (e.g. after a process restart), restore_session_if_exists() checks
  whether that directory exists and, if so, calls create_session() with the
  existing session_id so the agent picks up the persisted history.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, Union

from tokuye.agent.strands_agent import StrandsAgent
from tokuye.api.turn_store import TurnStore
from tokuye.utils.config import settings

logger = logging.getLogger(__name__)


@dataclass
class ApiSession:
    session_id: str
    agent: Union[StrandsAgent, "EpicManagerAgent"]  # type: ignore[type-arg]
    # Queue of SSE event dicts; None is the sentinel for stream end.  (POST /sse)
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    # Event log store for the async turn API.  (POST /turn + GET /events)
    turn_store: TurnStore = field(default_factory=TurnStore)
    # turn_id of the currently running turn, or None when idle.
    _current_turn_id: Optional[str] = field(default=None, repr=False)


# ---------------------------------------------------------------------------
# Module-level session store
# ---------------------------------------------------------------------------

_sessions: Dict[str, ApiSession] = {}
_lock = asyncio.Lock()


def _make_thread_id() -> str:
    """Return a thread_id with the 'api-' prefix so FileSession files are
    distinguishable from TUI sessions at a glance."""
    return f"api-{uuid.uuid4()}"


async def create_session(session_id: Optional[str] = None) -> ApiSession:
    """Instantiate a new agent and register the session.

    If *session_id* is provided, the agent is initialised with that id so
    FileSessionManager will load the persisted conversation history from
    <project_root>/.tokuye/sessions/session_<session_id>/.
    If omitted, a new unique id is generated.

    The agent's callbacks write SSE event dicts into the session queue
    (for POST /sse compatibility) AND into the TurnStore (for GET /events).
    MCP initialisation is deferred to the first __call__ (lazy).
    """
    if session_id is None:
        session_id = _make_thread_id()
    queue: asyncio.Queue = asyncio.Queue()

    # session is assigned after construction; callbacks close over it via
    # a one-element list so the lambda can reference the not-yet-created object.
    _session_ref: list[ApiSession] = []

    def _add_ai_message(content: str) -> None:
        # POST /sse compatibility
        queue.put_nowait({"type": "ai_message", "content": content})
        # Async turn API: write to TurnStore if a turn is active.
        # Capture turn_id immediately (before call_soon_threadsafe schedules
        # the lambda) so the lambda does not see a stale / None value.
        if _session_ref and _session_ref[0]._current_turn_id:
            session = _session_ref[0]
            _tid = session._current_turn_id
            asyncio.get_event_loop().call_soon_threadsafe(
                lambda tid=_tid, c=content: asyncio.ensure_future(
                    session.turn_store.append_event(
                        session_id,
                        tid,
                        {"type": "ai_delta", "content": c},
                    )
                )
            )

    def _add_system_message(content: str) -> None:
        # POST /sse compatibility
        queue.put_nowait({"type": "system_message", "content": content})
        # Async turn API
        if _session_ref and _session_ref[0]._current_turn_id:
            session = _session_ref[0]
            _tid = session._current_turn_id
            asyncio.get_event_loop().call_soon_threadsafe(
                lambda tid=_tid, c=content: asyncio.ensure_future(
                    session.turn_store.append_event(
                        session_id,
                        tid,
                        {"type": "system_message", "content": c},
                    )
                )
            )

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
                # POST /sse compatibility: sentinel closes the SSE stream
                queue.put_nowait(None)
                # Async turn API: emit approval_required event
                if _session_ref and _session_ref[0]._current_turn_id:
                    session = _session_ref[0]
                    _tid = session._current_turn_id
                    asyncio.get_event_loop().call_soon_threadsafe(
                        lambda tid=_tid: asyncio.ensure_future(
                            session.turn_store.append_event(
                                session_id,
                                tid,
                                {"type": "approval_required"},
                            )
                        )
                    )

    def _update_token_usage(_text: str) -> None:
        # Not surfaced in API mode
        pass

    common_kwargs = dict(
        thread_id=session_id,
        max_steps=settings.max_steps,
        add_ai_message=_add_ai_message,
        add_system_message=_add_system_message,
        set_thinking=_set_thinking,
        update_token_usage=_update_token_usage,
    )
    if settings.epic_mode:
        from tokuye.agent.epic_manager_agent import EpicManagerAgent
        agent = EpicManagerAgent(**common_kwargs)
    else:
        agent = StrandsAgent(**common_kwargs)

    # Register approval callbacks so run_project_command can prompt via SSE.
    from tokuye.tools.strands_tools.project_command_tools import (
        set_command_approval_callbacks,
    )
    set_command_approval_callbacks(
        add_system_message=_add_system_message,
        set_thinking=_set_thinking,
    )

    session = ApiSession(session_id=session_id, agent=agent, queue=queue)
    _session_ref.append(session)

    async with _lock:
        _sessions[session_id] = session

    return session


async def get_session(session_id: str) -> Optional[ApiSession]:
    """Return the session for *session_id*, or None if not found."""
    async with _lock:
        return _sessions.get(session_id)


def _session_dir() -> str:
    """Return the absolute path to the sessions storage directory."""
    d = settings.strands_session_dir
    if not d:
        d = os.path.join(str(settings.project_root), ".tokuye", "sessions")
    # strands_session_dir may be a relative path; resolve against project_root
    if not os.path.isabs(d):
        d = os.path.join(str(settings.project_root), d)
    return d


def _session_persisted(session_id: str) -> bool:
    """Return True if FileSessionManager has persisted data for *session_id*.

    FileSessionManager stores data under:
      <storage_dir>/session_<session_id>/
    """
    path = os.path.join(_session_dir(), f"session_{session_id}")
    return os.path.isdir(path)


async def restore_session_if_exists(session_id: str) -> Optional[ApiSession]:
    """Restore a session from persisted storage if it exists.

    Called when get_session() returns None (e.g. after a process restart).
    If <storage_dir>/session_<session_id>/ exists, creates a new ApiSession
    with the same session_id so the agent loads the persisted history.
    Returns the restored ApiSession, or None if no persisted data is found.
    """
    if not _session_persisted(session_id):
        return None
    logger.info("Restoring session from persisted storage: %s", session_id)
    return await create_session(session_id=session_id)


async def delete_session(session_id: str) -> None:
    """Remove a session and clean up its agent."""
    async with _lock:
        session = _sessions.pop(session_id, None)
    if session is not None:
        await session.agent.cleanup()


# ---------------------------------------------------------------------------
# Async turn API helpers
# ---------------------------------------------------------------------------

async def start_turn(session: ApiSession, turn_id: str, message: str) -> None:
    """Register *turn_id* as the active turn and launch the agent as a background task.

    Raises RuntimeError if another turn is already running on this session.
    """
    if session._current_turn_id is not None:
        raise RuntimeError(
            f"Session {session.session_id} already has an active turn: "
            f"{session._current_turn_id}"
        )
    session._current_turn_id = turn_id
    asyncio.create_task(
        _run_agent_for_turn(session, turn_id, message),
        name=f"turn-{turn_id}",
    )


async def _run_agent_for_turn(
    session: ApiSession, turn_id: str, message: str
) -> None:
    """Run the agent for *turn_id* and record completion / failure events.

    This coroutine runs as a background task.  It is the sole writer of
    turn_completed / turn_failed events and the sole caller of mark_completed().
    """
    sid = session.session_id
    store = session.turn_store
    try:
        await session.agent(message)
        await store.append_event(sid, turn_id, {"type": "turn_completed"})
    except Exception as e:
        logger.error(
            "Agent error in session %s turn %s: %s", sid, turn_id, e, exc_info=True
        )
        await store.append_event(sid, turn_id, {"type": "turn_failed", "error": str(e)})
    finally:
        session._current_turn_id = None
        await store.mark_completed(sid, turn_id)
