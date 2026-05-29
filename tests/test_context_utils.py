"""Tests for tokuye.agent.context_utils."""

import pytest
from tokuye.agent.context_utils import compact_tool_message, compact_tool_history, _has_tool_result


# ---------------------------------------------------------------------------
# compact_tool_message
# ---------------------------------------------------------------------------

class TestCompactToolMessage:
    def test_pure_text_assistant_unchanged(self):
        msg = {"role": "assistant", "content": [{"text": "Hello"}]}
        assert compact_tool_message(msg) == msg

    def test_tooluse_assistant_compacted(self):
        msg = {
            "role": "assistant",
            "content": [
                {"text": "まず状況を把握する。"},
                {"toolUse": {"toolUseId": "id1", "name": "read_file", "input": {}}},
            ],
        }
        result = compact_tool_message(msg)
        assert result is not None
        assert result["role"] == "assistant"
        assert len(result["content"]) == 1
        text = result["content"][0]["text"]
        assert "read_file" in text
        assert "[Past tool calls" in text
        # original text block must be gone
        assert "まず状況を把握する" not in text

    def test_multiple_tooluse_compacted(self):
        msg = {
            "role": "assistant",
            "content": [
                {"text": "準備完了。"},
                {"toolUse": {"toolUseId": "id1", "name": "file_search", "input": {}}},
                {"toolUse": {"toolUseId": "id2", "name": "list_directory", "input": {}}},
            ],
        }
        result = compact_tool_message(msg)
        assert result is not None
        text = result["content"][0]["text"]
        assert "file_search" in text
        assert "list_directory" in text

    def test_toolresult_user_dropped(self):
        msg = {
            "role": "user",
            "content": [
                {"toolResult": {"toolUseId": "id1", "status": "success", "content": [{"text": "ok"}]}},
            ],
        }
        assert compact_tool_message(msg) is None

    def test_multiple_toolresult_user_dropped(self):
        msg = {
            "role": "user",
            "content": [
                {"toolResult": {"toolUseId": "id1", "status": "success", "content": [{"text": "a"}]}},
                {"toolResult": {"toolUseId": "id2", "status": "success", "content": [{"text": "b"}]}},
            ],
        }
        assert compact_tool_message(msg) is None

    def test_plain_user_message_unchanged(self):
        msg = {"role": "user", "content": [{"text": "Please do X"}]}
        assert compact_tool_message(msg) == msg

    def test_non_list_content_unchanged(self):
        msg = {"role": "assistant", "content": "raw string"}
        assert compact_tool_message(msg) == msg


# ---------------------------------------------------------------------------
# compact_tool_history
# ---------------------------------------------------------------------------

class TestCompactToolHistory:
    def _make_messages(self):
        """Build a realistic message list: 3 tool round-trips + 1 user + 1 assistant text."""
        msgs = []
        for i in range(3):
            msgs.append({
                "role": "assistant",
                "content": [
                    {"text": f"step {i}"},
                    {"toolUse": {"toolUseId": f"id{i}", "name": f"tool_{i}", "input": {}}},
                ],
            })
            msgs.append({
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": f"id{i}", "status": "success", "content": [{"text": "result"}]}},
                ],
            })
        # plain user message
        msgs.append({"role": "user", "content": [{"text": "Next task"}]})
        # plain assistant text
        msgs.append({"role": "assistant", "content": [{"text": "Sure"}]})
        return msgs

    def test_recent_messages_preserved(self):
        msgs = self._make_messages()
        result = compact_tool_history(msgs, preserve_recent_messages=4)
        # last 4 messages must be identical
        assert result[-4:] == msgs[-4:]

    def test_old_toolresult_dropped(self):
        msgs = self._make_messages()
        result = compact_tool_history(msgs, preserve_recent_messages=4)
        # No toolResult blocks should survive in the old portion
        old_portion = result[:-4]
        for msg in old_portion:
            for block in msg.get("content", []):
                assert "toolResult" not in block

    def test_old_tooluse_compacted(self):
        msgs = self._make_messages()
        result = compact_tool_history(msgs, preserve_recent_messages=4)
        old_portion = result[:-4]
        # toolUse blocks must be gone; replaced by compacted text
        for msg in old_portion:
            for block in msg.get("content", []):
                assert "toolUse" not in block

    def test_short_history_unchanged(self):
        msgs = [
            {"role": "user", "content": [{"text": "hi"}]},
            {"role": "assistant", "content": [{"text": "hello"}]},
        ]
        result = compact_tool_history(msgs, preserve_recent_messages=8)
        assert result == msgs

    def test_exact_preserve_boundary(self):
        msgs = self._make_messages()
        # preserve all messages — nothing should be compacted
        result = compact_tool_history(msgs, preserve_recent_messages=len(msgs))
        assert result == msgs

    def test_tool_names_appear_in_compacted(self):
        msgs = self._make_messages()
        result = compact_tool_history(msgs, preserve_recent_messages=2)
        old_portion = result[:-2]
        all_text = " ".join(
            block.get("text", "")
            for msg in old_portion
            for block in msg.get("content", [])
        )
        assert "tool_0" in all_text
        assert "tool_1" in all_text
        assert "tool_2" in all_text

    def test_split_boundary_never_strands_toolresult(self):
        """recent window must not start with a toolResult message.

        If the split point lands between a toolUse and its toolResult,
        the boundary must be moved back so the pair stays together.
        """
        # Build: toolUse at index 0, toolResult at index 1, then plain messages
        msgs = [
            {
                "role": "assistant",
                "content": [
                    {"toolUse": {"toolUseId": "id0", "name": "grep", "input": {}}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": "id0", "status": "success", "content": [{"text": "found"}]}},
                ],
            },
            {"role": "user", "content": [{"text": "ok"}]},
            {"role": "assistant", "content": [{"text": "done"}]},
        ]
        # preserve_recent_messages=3 would normally put the split between
        # index 0 (toolUse) and index 1 (toolResult).
        result = compact_tool_history(msgs, preserve_recent_messages=3)
        # recent window must not start with a toolResult
        assert not _has_tool_result(result[0]) if result else True
        # No orphaned toolResult in any position
        for i, msg in enumerate(result):
            content = msg.get("content", [])
            has_tr = any("toolResult" in b for b in content)
            if has_tr:
                # There must be a preceding assistant message with toolUse
                preceding_roles = [m["role"] for m in result[:i]]
                assert "assistant" in preceding_roles

    def test_split_boundary_all_toolresult_messages(self):
        """Boundary adjustment must not infinite-loop when old becomes empty."""
        msgs = [
            {
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": "id0", "status": "success", "content": [{"text": "r"}]}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"toolResult": {"toolUseId": "id1", "status": "success", "content": [{"text": "r"}]}},
                ],
            },
        ]
        # Should not raise; returns messages as-is when old is exhausted
        result = compact_tool_history(msgs, preserve_recent_messages=1)
        assert isinstance(result, list)
