"""Utilities for compressing agent conversation context.

Reduces token usage by replacing old toolUse/toolResult messages with
compact summaries before passing history to the model.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def compact_tool_message(message: dict) -> dict | None:
    """Compact a single message that contains tool-related content.

    Rules:
    - assistant message with toolUse blocks:
        Replace the entire content with a single text block listing tool names.
        (Any text blocks mixed in are discarded — they are not needed.)
    - user message whose content consists entirely of toolResult blocks:
        Discard the message entirely (return None).
    - All other messages (pure assistant text, plain user messages):
        Return as-is.

    Args:
        message: A single message dict with "role" and "content" keys.

    Returns:
        Compacted message dict, or None if the message should be dropped.
    """
    role = message.get("role")
    content = message.get("content", [])

    if not isinstance(content, list):
        return message

    if role == "assistant":
        tool_names = [b["toolUse"]["name"] for b in content if "toolUse" in b]
        if tool_names:
            summary = "[Compacted tool history]\n" + "\n".join(f"- {n}" for n in tool_names)
            return {"role": "assistant", "content": [{"text": summary}]}
        # No toolUse — pure text message, keep as-is
        return message

    if role == "user":
        has_tool_result = any("toolResult" in b for b in content)
        if has_tool_result:
            # Drop toolResult-only user messages entirely
            return None
        return message

    return message


def _has_tool_result(message: dict) -> bool:
    """Return True if the message contains any toolResult block."""
    content = message.get("content", [])
    if not isinstance(content, list):
        return False
    return any("toolResult" in b for b in content)


def compact_tool_history(
    messages: list[dict],
    preserve_recent_messages: int = 8,
) -> list[dict]:
    """Compact old toolUse/toolResult messages in the conversation history.

    Keeps the most recent ``preserve_recent_messages`` messages untouched.
    Older messages are passed through ``compact_tool_message``:
    - toolUse assistant messages → single summary text message
    - toolResult user messages → dropped

    The split point is adjusted so that a toolResult message is never left
    in the recent window without its paired toolUse message.  If the first
    message of the recent window contains toolResult blocks, the boundary is
    moved backward until the recent window starts with a non-toolResult
    message.  This prevents Bedrock from rejecting the request with a
    "toolResult count exceeds toolUse count" validation error.

    Args:
        messages: Full conversation history (agent.messages).
        preserve_recent_messages: Number of tail messages to leave untouched.

    Returns:
        New list with compacted history prepended to the preserved tail.
    """
    if len(messages) <= preserve_recent_messages:
        return messages

    old = list(messages[:-preserve_recent_messages])
    recent = list(messages[-preserve_recent_messages:])

    # Adjust split point: if recent starts with a toolResult message, move
    # it (and any preceding toolUse partner) back into old so the pair is
    # compacted together.
    while old and _has_tool_result(recent[0]):
        recent.insert(0, old.pop())

    compacted: list[dict] = []
    for msg in old:
        try:
            result = compact_tool_message(msg)
        except Exception as exc:
            # Never break the agent loop — fall back to keeping the original
            logger.debug("compact_tool_message failed, keeping original: %s", exc)
            result = msg
        if result is not None:
            compacted.append(result)

    return compacted + recent
