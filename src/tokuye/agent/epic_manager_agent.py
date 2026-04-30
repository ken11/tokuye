"""
EpicManagerAgent for v3 Epic Mode.

Acts as the user-facing agent when epic_mode=True.
Replaces StrandsAgent in ChatInterface.

Responsibilities:
  - Receive Epic requests from the user
  - Manage Epic working directories via epic_dir_tools
  - Analyze repos via repo_ops (epic-safe variants)
  - Delegate implementation tasks to EpicWorkerAgent via run_epic_worker tool
  - Present results to the user and wait for approval at each checkpoint
  - Persist progress to the Epic working directory

Human Approval is handled entirely through the system prompt:
  the agent is instructed to always wait for explicit user confirmation
  before advancing to the next step.  No special approval-flag logic is
  needed in this class.
"""

from __future__ import annotations

import logging
import os

from strands import Agent
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.models import BedrockModel
from strands.session.file_session_manager import FileSessionManager

from tokuye.mcp_manager import MCPClientManager
from tokuye.prompts.prompt_loader import load_prompt, load_prompt_if_exists
from tokuye.tools.strands_tools.epic_tools import epic_manager_tools
from tokuye.utils.config import settings
from tokuye.utils.token_tracker import token_tracker

logger = logging.getLogger(__name__)


def _supports_prompt_cache(model_identifier: str) -> bool:
    return model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6", "nova-pro")


def _supports_tool_cache(model_identifier: str) -> bool:
    return model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6")


class EpicManagerAgent:
    """User-facing agent for Epic Mode (v3).

    Drop-in replacement for StrandsAgent when ``settings.epic_mode`` is True.
    Exposes the same async ``__call__`` interface and ``cleanup`` method so
    ChatInterface does not need to know which agent it is talking to.
    """

    def __init__(
        self,
        thread_id: str,
        max_steps: int,
        add_ai_message,
        add_system_message,
        set_thinking,
        update_token_usage,
    ) -> None:
        self.thread_id = thread_id
        self.max_steps = max_steps
        self.add_ai_message = add_ai_message
        self.add_system_message = add_system_message
        self.set_thinking = set_thinking
        self.update_token_usage = update_token_usage

        # System prompt (language-aware)
        if settings.language == "ja":
            self.system_prompt = load_prompt("system_prompt_epic_manager.md")
        else:
            self.system_prompt = load_prompt("system_prompt_epic_manager_en.md")

        # Summary prompt for conversation manager
        if settings.language == "ja":
            self.summary_prompt = load_prompt_if_exists("summary_prompt.md")
        else:
            self.summary_prompt = load_prompt_if_exists("summary_prompt_en.md")

        # Model — use bedrock_epic_manager_model_id if set, else fall back to bedrock_model_id
        manager_model_id = settings.bedrock_epic_manager_model_id or settings.bedrock_model_id
        _exec_cache = _supports_prompt_cache(settings.model_identifier)
        _exec_tool_cache = _supports_tool_cache(settings.model_identifier)
        self.model = BedrockModel(
            **({"cache_prompt": "default"} if _exec_cache else {}),
            **({"cache_tools": "default"} if _exec_tool_cache else {}),
            model_id=manager_model_id,
            temperature=settings.model_temperature,
        )

        # Session
        session_dir = settings.strands_session_dir
        if not session_dir:
            session_dir = os.path.join(
                settings.project_root, ".tokuye", "sessions"
            )
        os.makedirs(session_dir, exist_ok=True)
        self.session_manager = FileSessionManager(
            session_id=thread_id, storage_dir=session_dir
        )

        # MCP manager — actual start/get_tools is deferred to _init_mcp_and_build_agent()
        self.mcp_manager = MCPClientManager(settings.mcp_servers)

        # Agent is built lazily on first __call__
        self.agent = None
        self.step_count = 0
        self._mcp_initialized = False

        # current_task_branch kept for interface compatibility with ChatInterface
        self.current_task_branch: str = ""

    # ------------------------------------------------------------------
    # Lazy initialisation (MCP + Agent)
    # ------------------------------------------------------------------

    async def _init_mcp_and_build_agent(self) -> None:
        """Start MCP clients, fetch tools, and build the Strands Agent.

        Called once on the first __call__ invocation so that MCP I/O runs
        inside the event loop instead of blocking __init__.
        """
        if self._mcp_initialized:
            return

        await self.mcp_manager.start_async()
        mcp_tools = await self.mcp_manager.get_tools_async()
        if mcp_tools:
            logger.info("EpicManagerAgent: loaded %d MCP tools", len(mcp_tools))

        combined_tools = list(epic_manager_tools) + mcp_tools

        self.agent = Agent(
            model=self.model,
            tools=combined_tools,
            system_prompt=self.system_prompt,
            session_manager=self.session_manager,
            conversation_manager=SummarizingConversationManager(
                summarization_system_prompt=self.summary_prompt
            ),
            callback_handler=self._callback_handler,
        )

        self._mcp_initialized = True

    # ------------------------------------------------------------------
    # Public interface (same as StrandsAgent)
    # ------------------------------------------------------------------

    async def __call__(self, message: str | None = None, **kwargs):
        """Process a user message."""
        if not self._mcp_initialized:
            await self._init_mcp_and_build_agent()
        self.set_thinking(True)
        try:
            token_tracker.reset_turn()
            result = await self.agent.invoke_async(message, **kwargs)
            self._update_token_usage(result)
            return result
        finally:
            self.set_thinking(False)

    async def cleanup(self) -> None:
        """Stop MCP connections."""
        await self.mcp_manager.stop_async()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _callback_handler(self, **kwargs):
        """Forward streaming events to TUI callbacks."""
        if "event" in kwargs and kwargs["event"].get("messageStop") is not None:
            self.step_count += 1
            if self.step_count > self.max_steps:
                from tokuye.agent.strands_agent import MaxStepsException
                raise MaxStepsException("Maximum number of steps exceeded")
        if "message" in kwargs and kwargs["message"].get("role") == "assistant":
            content = kwargs["message"].get("content")
            if content:
                for c in content:
                    if isinstance(c, dict) and c.get("text", "").strip():
                        self.add_ai_message(c["text"])

    def _update_token_usage(self, result) -> None:
        try:
            from strands.agent import AgentResult
            if not isinstance(result, AgentResult):
                return
            latest = result.metrics.latest_agent_invocation
            if latest is None:
                return
            token_tracker.add_usage(latest.usage)
            self.update_token_usage(token_tracker.format_usage_summary())
        except Exception as e:
            logger.debug("Token usage update failed: %s", e)
