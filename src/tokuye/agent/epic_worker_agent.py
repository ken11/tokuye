"""
EpicWorkerAgent for v3 Epic Mode.

Handles one task at a time.  Each task gets its own session (FileSessionManager
with a task-scoped session_id).  The agent does NOT interact with the user
directly; it returns structured YAML results to EpicManagerAgent.

Usage
-----
    worker = EpicWorkerAgent(
        epic_id="auth-cognito-migration",
        task_id="T001",
        add_ai_message=...,
        add_system_message=...,
        set_thinking=...,
        update_token_usage=...,
    )
    result_yaml = await worker(task_instruction)
"""

from __future__ import annotations

import logging
import os

from strands import Agent
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.models import BedrockModel
from strands.session.file_session_manager import FileSessionManager

from tokuye.prompts.prompt_loader import load_prompt, load_prompt_if_exists
from tokuye.tools.strands_tools import developer_tools
from tokuye.utils.config import settings

logger = logging.getLogger(__name__)


def _supports_prompt_cache(model_identifier: str) -> bool:
    return model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6", "nova-pro")


def _supports_tool_cache(model_identifier: str) -> bool:
    return model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6")


class EpicWorkerAgent:
    """Single-task agent for Epic Mode.

    One instance = one task session.
    Create a new instance for each task.
    """

    def __init__(
        self,
        epic_id: str,
        task_id: str,
        add_ai_message,
        add_system_message,
        set_thinking,
        update_token_usage,
    ) -> None:
        self.epic_id = epic_id
        self.task_id = task_id
        self.add_ai_message = add_ai_message
        self.add_system_message = add_system_message
        self.set_thinking = set_thinking
        self.update_token_usage = update_token_usage

        # System prompt (language-aware)
        if settings.language == "ja":
            self.system_prompt = load_prompt("system_prompt_epic_worker.md")
        else:
            self.system_prompt = load_prompt("system_prompt_epic_worker_en.md")

        # Summary prompt for conversation manager
        if settings.language == "ja":
            self.summary_prompt = load_prompt_if_exists("summary_prompt.md")
        else:
            self.summary_prompt = load_prompt_if_exists("summary_prompt_en.md")

        # Model — use the primary execution model
        _exec_cache = _supports_prompt_cache(settings.model_identifier)
        _exec_tool_cache = _supports_tool_cache(settings.model_identifier)
        self.model = BedrockModel(
            **({"cache_prompt": "default"} if _exec_cache else {}),
            **({"cache_tools": "default"} if _exec_tool_cache else {}),
            model_id=settings.bedrock_model_id,
            temperature=settings.model_temperature,
        )

        # Session: scoped to epic_id + task_id so each task has isolated history
        session_dir = settings.strands_session_dir
        if not session_dir:
            session_dir = os.path.join(
                settings.project_root, ".tokuye", "sessions"
            )
        os.makedirs(session_dir, exist_ok=True)
        session_id = f"epic-{epic_id}-{task_id}"
        self.session_manager = FileSessionManager(
            session_id=session_id, storage_dir=session_dir
        )

        # Build agent immediately (no MCP for worker — keeps it lightweight)
        self.agent = Agent(
            model=self.model,
            tools=developer_tools,
            system_prompt=self.system_prompt,
            session_manager=self.session_manager,
            conversation_manager=SummarizingConversationManager(
                summarization_system_prompt=self.summary_prompt
            ),
            callback_handler=self._callback_handler,
        )

    def _callback_handler(self, **kwargs) -> None:
        """Forward streaming events to TUI callbacks."""
        event = kwargs.get("event")
        if event == "message":
            data = kwargs.get("data", {})
            content = data.get("content", "")
            if content:
                self.add_ai_message(content)
        elif event == "thinking":
            self.set_thinking(kwargs.get("data", False))
        elif event == "usage":
            data = kwargs.get("data", {})
            input_tokens = data.get("input_tokens", 0)
            output_tokens = data.get("output_tokens", 0)
            self.update_token_usage(
                f"Worker [{self.task_id}] — in: {input_tokens}, out: {output_tokens}"
            )

    async def __call__(self, instruction: str) -> str:
        """Run the worker with *instruction* and return the raw response text.

        Args:
            instruction: Full task instruction from EpicManagerAgent.

        Returns:
            Raw response string (expected to be YAML by the system prompt).
        """
        self.set_thinking(True)
        try:
            result = await self.agent.invoke_async(instruction)
            # Extract text content from AgentResult
            if hasattr(result, "message") and result.message:
                content = result.message.get("content", [])
                if isinstance(content, list):
                    texts = [
                        c.get("text", "") for c in content if isinstance(c, dict)
                    ]
                    return "\n".join(t for t in texts if t)
                if isinstance(content, str):
                    return content
            return str(result)
        finally:
            self.set_thinking(False)
