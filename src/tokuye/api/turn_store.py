"""
turn_store.py
~~~~~~~~~~~~~
In-memory event log for the async turn / event API.

Each (session_id, turn_id) pair owns a TurnRecord that holds an append-only
list of TurnEvents.  Consumers waiting for new events block on an
asyncio.Condition so they are woken up immediately when new events arrive.

Lifecycle
---------
  POST /turn  → TurnStore.create_turn()
              → TurnStore.append_event()  (turn_started, then ai_delta / system_message …)
  GET /events → TurnStore.get_events_after() + wait_and_get_new_events()
  turn done   → TurnStore.mark_completed()

Notes
-----
- TurnStore lives in process memory only.  It is intentionally NOT persisted;
  FileSessionManager is the source of truth for conversation history.
- event_id is 1-based and monotonically increasing within a turn.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TurnEvent:
    """A single SSE event recorded for a turn."""

    event_id: int   # 1-based, monotonically increasing within the turn
    data: dict      # arbitrary JSON-serialisable payload


class TurnRecord:
    """Mutable state for one (session_id, turn_id) pair."""

    def __init__(self, turn_id: str) -> None:
        self.turn_id = turn_id
        self.events: List[TurnEvent] = []
        self.completed: bool = False
        # Condition is used both as a lock (for append) and as a notifier
        # (to wake up GET /events consumers waiting for new events).
        self._condition: asyncio.Condition = asyncio.Condition()

    async def append(self, data: dict) -> int:
        """Append *data* as a new TurnEvent and notify all waiters.

        Returns the assigned event_id.
        """
        async with self._condition:
            event_id = len(self.events) + 1
            self.events.append(TurnEvent(event_id=event_id, data=data))
            self._condition.notify_all()
            return event_id

    async def mark_completed(self) -> None:
        """Mark the turn as completed and wake up all waiters."""
        async with self._condition:
            self.completed = True
            self._condition.notify_all()

    def get_events_after(self, after_id: int) -> List[TurnEvent]:
        """Return all events whose event_id > *after_id* (no locking needed for reads)."""
        return [e for e in self.events if e.event_id > after_id]

    async def wait_and_get_new_events(self, after_id: int) -> List[TurnEvent]:
        """Block until at least one new event with event_id > *after_id* exists,
        then return all such events.

        Returns immediately (possibly with an empty list) if the turn is
        already completed, so callers can detect end-of-stream.
        """
        async with self._condition:
            await self._condition.wait_for(
                lambda: self.completed or any(e.event_id > after_id for e in self.events)
            )
            return [e for e in self.events if e.event_id > after_id]


# ---------------------------------------------------------------------------
# TurnStore — top-level registry
# ---------------------------------------------------------------------------

_Key = Tuple[str, str]  # (session_id, turn_id)


class TurnStore:
    """Registry of TurnRecords keyed by (session_id, turn_id)."""

    def __init__(self) -> None:
        self._turns: Dict[_Key, TurnRecord] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def create_turn(self, session_id: str, turn_id: str) -> None:
        """Register a new turn.  Raises ValueError if already exists."""
        key = (session_id, turn_id)
        if key in self._turns:
            raise ValueError(f"Turn already exists: {turn_id}")
        self._turns[key] = TurnRecord(turn_id=turn_id)
        logger.debug("TurnStore: created turn %s / %s", session_id, turn_id)

    async def mark_completed(self, session_id: str, turn_id: str) -> None:
        """Mark the turn as completed and wake up all GET /events consumers."""
        record = self._get(session_id, turn_id)
        if record is not None:
            await record.mark_completed()
            logger.debug("TurnStore: completed turn %s / %s", session_id, turn_id)

    # ------------------------------------------------------------------
    # Event append
    # ------------------------------------------------------------------

    async def append_event(self, session_id: str, turn_id: str, data: dict) -> int:
        """Append *data* to the turn's event log.

        Returns the assigned event_id, or 0 if the turn is not found
        (e.g. called after the turn was cleaned up).
        """
        record = self._get(session_id, turn_id)
        if record is None:
            logger.warning(
                "TurnStore.append_event: turn not found %s / %s", session_id, turn_id
            )
            return 0
        return await record.append(data)

    # ------------------------------------------------------------------
    # Event read
    # ------------------------------------------------------------------

    def get_turn(self, session_id: str, turn_id: str) -> Optional[TurnRecord]:
        """Return the TurnRecord, or None if not found."""
        return self._get(session_id, turn_id)

    def get_events_after(
        self, session_id: str, turn_id: str, after_id: int
    ) -> List[TurnEvent]:
        """Return all events with event_id > *after_id* (synchronous)."""
        record = self._get(session_id, turn_id)
        if record is None:
            return []
        return record.get_events_after(after_id)

    async def wait_and_get_new_events(
        self, session_id: str, turn_id: str, after_id: int
    ) -> List[TurnEvent]:
        """Block until new events arrive, then return them."""
        record = self._get(session_id, turn_id)
        if record is None:
            return []
        return await record.wait_and_get_new_events(after_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get(self, session_id: str, turn_id: str) -> Optional[TurnRecord]:
        return self._turns.get((session_id, turn_id))
