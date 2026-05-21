"""
server.py
~~~~~~~~~
FastAPI server for tokuye API mode.

Endpoints
---------
  POST /new
      Start a new conversation session.
      Returns: {"session_id": "<api-uuid>"}

  POST /sse  (legacy — kept for backward compatibility)
      Send one user turn and stream the agent's response as SSE.
      Body: {"session_id": "<api-uuid>", "message": "<user text>"}
      Stream: text/event-stream
        data: {"type": "ai_message",     "content": "..."}
        data: {"type": "system_message", "content": "..."}
        data: [DONE]

  POST /turn
      Submit a user turn and start agent execution asynchronously.
      Body: {"session_id": "<api-uuid>", "message": "<user text>"}
      Returns: {"session_id": "...", "turn_id": "...", "status": "running"}

  GET /events?session_id=<api-uuid>&turn_id=<turn-uuid>[&after_event_id=<n>]
      Stream SSE events for the given turn.
      Supports resumption via Last-Event-ID header or after_event_id query param.
      Events:
        id: <n>
        data: {"type": "turn_started",      "turn_id": "..."}
        data: {"type": "ai_delta",          "content": "..."}
        data: {"type": "system_message",    "content": "..."}
        data: {"type": "approval_required"}
        data: {"type": "turn_completed"}
        data: {"type": "turn_failed",       "error": "..."}

  GET /messages?session_id=<api-uuid>
      Return the persisted conversation history from FileSessionManager.
      Returns: {"session_id": "...", "messages": [...]}

  POST /turn/{turn_id}/approve
      Resolve a pending command-approval prompt.
      Body: {"session_id": "<api-uuid>", "approved": true|false}
      Returns: {"status": "ok"}

Approval flow (async turn API)
------------------------------
When the agent calls run_project_command it pauses at _approval_event.wait().
GET /events emits an {"type": "approval_required"} event.
The client calls POST /turn/{turn_id}/approve with approved=true/false.
The server calls resolve_command_approval() and the paused agent resumes.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from tokuye.api.session import create_session, get_session, start_turn
from tokuye.tools.strands_tools.project_command_tools import (
    is_waiting_for_command_approval,
    resolve_command_approval,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="tokuye API", version="1.0.0")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class NewSessionResponse(BaseModel):
    session_id: str


class SseRequest(BaseModel):
    session_id: str
    message: str


class TurnRequest(BaseModel):
    session_id: str
    message: str


class TurnResponse(BaseModel):
    session_id: str
    turn_id: str
    status: str


class ApproveRequest(BaseModel):
    session_id: str
    approved: bool


# ---------------------------------------------------------------------------
# Endpoints — session
# ---------------------------------------------------------------------------

@app.post("/new", response_model=NewSessionResponse)
async def new_session() -> NewSessionResponse:
    """Create a new conversation session and return its session_id."""
    session = await create_session()
    logger.info("New session created: %s", session.session_id)
    return NewSessionResponse(session_id=session.session_id)


# ---------------------------------------------------------------------------
# Endpoints — legacy SSE (POST /sse)
# ---------------------------------------------------------------------------

@app.post("/sse")
async def sse_turn(body: SseRequest) -> StreamingResponse:
    """Run one agent turn and stream the response as SSE."""
    session = await get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    return StreamingResponse(
        _stream_turn(session, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_turn(session, message: str) -> AsyncGenerator[str, None]:
    """Drive one agent turn and yield SSE-formatted lines.

    If the session is currently waiting for command approval, resolve it
    with the incoming message instead of invoking the agent again.
    """
    queue = session.queue

    if is_waiting_for_command_approval():
        # Resolve approval; the paused agent coroutine will resume and
        # continue writing to the queue on its own task.
        approved = message.strip().lower().startswith("y")
        resolve_command_approval(approved)
        # Fall through to drain the queue — the resumed agent task is
        # already running and will put events + sentinel into the queue.
    else:
        # Normal turn: run the agent as a background task so we can drain
        # the queue concurrently.
        asyncio.create_task(_run_agent(session, message))

    async for line in _drain_queue(queue):
        yield line


async def _run_agent(session, message: str) -> None:
    """Invoke the agent and put a None sentinel into the queue when done."""
    try:
        await session.agent(message)
    except Exception as e:
        logger.error("Agent error in session %s: %s", session.session_id, e)
        session.queue.put_nowait(
            {"type": "system_message", "content": f"Error: {e}"}
        )
    finally:
        session.queue.put_nowait(None)  # sentinel


_HEARTBEAT_INTERVAL = 15  # seconds


async def _drain_queue(queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    """Yield SSE lines from *queue* until the None sentinel is received.

    Sends an SSE comment (`: keep-alive`) every *_HEARTBEAT_INTERVAL* seconds
    while the queue is idle, preventing proxies and clients from closing the
    connection due to inactivity.
    """
    while True:
        try:
            event = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT_INTERVAL)
        except asyncio.TimeoutError:
            yield ": keep-alive\n\n"
            continue
        if event is None:
            yield "data: [DONE]\n\n"
            break
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Endpoints — async turn API
# ---------------------------------------------------------------------------

def _make_turn_id() -> str:
    import uuid
    return f"turn-{uuid.uuid4()}"


@app.post("/turn", response_model=TurnResponse)
async def post_turn(body: TurnRequest) -> TurnResponse:
    """Submit a user message and start agent execution asynchronously.

    Returns immediately with a turn_id.  Use GET /events to stream the
    agent's response.
    """
    session = await get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if session._current_turn_id is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Session already has an active turn: {session._current_turn_id}",
        )

    turn_id = _make_turn_id()
    store = session.turn_store

    await store.create_turn(body.session_id, turn_id)
    await store.append_event(
        body.session_id, turn_id, {"type": "turn_started", "turn_id": turn_id}
    )

    try:
        await start_turn(session, turn_id, body.message)
    except RuntimeError as e:
        # Race condition guard (start_turn also checks _current_turn_id)
        raise HTTPException(status_code=409, detail=str(e))

    logger.info(
        "Turn started: session=%s turn=%s", body.session_id, turn_id
    )
    return TurnResponse(
        session_id=body.session_id, turn_id=turn_id, status="running"
    )


@app.get("/events")
async def get_events(
    session_id: str = Query(...),
    turn_id: str = Query(...),
    after_event_id: int = Query(default=0),
    last_event_id: Optional[str] = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """Stream SSE events for the given session / turn.

    Supports resumption: pass Last-Event-ID header or after_event_id query
    param to receive only events that arrived after that id.
    """
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    store = session.turn_store
    if store.get_turn(session_id, turn_id) is None:
        raise HTTPException(status_code=404, detail="Turn not found")

    # Last-Event-ID header takes precedence over query param
    after_id: int = int(last_event_id) if last_event_id is not None else after_event_id

    return StreamingResponse(
        _stream_events(store, session_id, turn_id, after_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_events(
    store, session_id: str, turn_id: str, after_id: int
) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted lines for all events after *after_id*.

    Loops until the turn is completed (turn_completed or turn_failed).
    Sends a keep-alive comment every _HEARTBEAT_INTERVAL seconds while idle.
    """
    _TERMINAL_TYPES = {"turn_completed", "turn_failed"}

    while True:
        # Flush any already-recorded events first (handles reconnect case)
        events = store.get_events_after(session_id, turn_id, after_id)
        for e in events:
            yield f"id: {e.event_id}\ndata: {json.dumps(e.data, ensure_ascii=False)}\n\n"
            after_id = e.event_id
            if e.data.get("type") in _TERMINAL_TYPES:
                return

        # Check if turn is already completed with no more events to send
        record = store.get_turn(session_id, turn_id)
        if record is not None and record.completed:
            return

        # Wait for new events (with keep-alive heartbeat)
        try:
            new_events = await asyncio.wait_for(
                store.wait_and_get_new_events(session_id, turn_id, after_id),
                timeout=_HEARTBEAT_INTERVAL,
            )
        except asyncio.TimeoutError:
            yield ": keep-alive\n\n"
            continue

        for e in new_events:
            yield f"id: {e.event_id}\ndata: {json.dumps(e.data, ensure_ascii=False)}\n\n"
            after_id = e.event_id
            if e.data.get("type") in _TERMINAL_TYPES:
                return


@app.get("/messages")
async def get_messages(session_id: str = Query(...)) -> dict:
    """Return the persisted conversation history for *session_id*.

    Uses FileSessionManager as the source of truth.  This endpoint is
    intended for screen-restore on mobile clients after a background/foreground
    transition.
    """
    session = await get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    # list_messages is synchronous; run it in a thread pool to avoid blocking
    # the event loop.
    try:
        messages = await asyncio.to_thread(
            session.agent.session_manager.list_messages,
            session_id,
            "default",
        )
    except Exception as e:
        logger.error(
            "Failed to list messages for session %s: %s", session_id, e
        )
        raise HTTPException(status_code=500, detail=f"Failed to load messages: {e}")

    return {
        "session_id": session_id,
        "messages": [m.to_dict() for m in messages],
    }


@app.post("/turn/{turn_id}/approve")
async def approve_turn(turn_id: str, body: ApproveRequest) -> dict:
    """Resolve a pending command-approval prompt for the given turn.

    The agent is currently blocked at _approval_event.wait().  Calling this
    endpoint unblocks it and lets execution continue.
    """
    session = await get_session(body.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if not is_waiting_for_command_approval():
        raise HTTPException(status_code=400, detail="No approval pending")

    resolve_command_approval(body.approved)
    logger.info(
        "Approval resolved: session=%s turn=%s approved=%s",
        body.session_id,
        turn_id,
        body.approved,
    )
    return {"status": "ok"}
