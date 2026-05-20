"""
server.py
~~~~~~~~~
FastAPI server for tokuye API mode.

Endpoints
---------
  POST /new
      Start a new conversation session.
      Returns: {"session_id": "<api-uuid>"}

  POST /sse
      Send one user turn and stream the agent's response as SSE.
      Body: {"session_id": "<api-uuid>", "message": "<user text>"}
      Stream: text/event-stream
        data: {"type": "ai_message",     "content": "..."}
        data: {"type": "system_message", "content": "..."}
        data: [DONE]

Approval flow
-------------
When the agent calls run_project_command it pauses at _approval_event.wait().
The SSE stream emits a system_message "Execute? y/n" and then closes with
[DONE].  The client sends a second POST /sse with "y" or "n"; the server
detects is_waiting_for_command_approval() and calls resolve_command_approval()
before starting a new SSE stream for the resumed agent turn.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from tokuye.api.session import create_session, get_session
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/new", response_model=NewSessionResponse)
async def new_session() -> NewSessionResponse:
    """Create a new conversation session and return its session_id."""
    session = await create_session()
    logger.info("New session created: %s", session.session_id)
    return NewSessionResponse(session_id=session.session_id)


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


# ---------------------------------------------------------------------------
# SSE streaming logic
# ---------------------------------------------------------------------------

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


async def _drain_queue(queue: asyncio.Queue) -> AsyncGenerator[str, None]:
    """Yield SSE lines from *queue* until the None sentinel is received."""
    while True:
        event = await queue.get()
        if event is None:
            yield "data: [DONE]\n\n"
            break
        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
