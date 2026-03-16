import logging
import os

from strands import Agent
from strands.agent import AgentResult
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.models import BedrockModel
from strands.session.file_session_manager import FileSessionManager
from strands.types.event_loop import Usage
from tokuye.prompts.prompt_loader import load_custom_system_prompt, load_prompt, load_prompt_if_exists
from tokuye.mcp import MCPClientManager
from tokuye.tools.strands_tools import all_tools
from tokuye.tools.strands_tools.phase_tool import configure_phase_models
from tokuye.utils.config import settings
from tokuye.utils.token_tracker import token_tracker

logger = logging.getLogger(__name__)


class MaxStepsException(Exception):

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class StrandsAgent:
    def __init__(
        self, thread_id, max_steps, add_ai_message, add_system_message, set_thinking, update_token_usage
    ):
        self.add_ai_message = add_ai_message
        self.add_system_message = add_system_message
        self.set_thinking = set_thinking
        self.update_token_usage = update_token_usage
        if settings.system_prompt_markdown_path:
            self.system_prompt = load_custom_system_prompt(
                settings.system_prompt_markdown_path
            )
            logger.info(
                "Using custom system prompt: %s",
                settings.system_prompt_markdown_path,
            )
        elif settings.language == "ja":
            self.system_prompt = load_prompt("system_prompt.md")
        elif settings.language == "en":
            self.system_prompt = load_prompt("system_prompt_en.md")
        if settings.language == "ja":
            self.summary_prompt = load_prompt_if_exists("summary_prompt.md")
        else:
            self.summary_prompt = load_prompt_if_exists("summary_prompt_en.md")

        # --- Model setup -------------------------------------------------
        # The "executing" model is always the primary bedrock_model_id.
        self.model = BedrockModel(
            cache_prompt="default",
            cache_tools="default",
            model_id=settings.bedrock_model_id,
            temperature=settings.model_temperature,
        )

        # When bedrock_plan_model_id is configured, create a separate
        # "thinking" model and wire up the phase-switching tool.
        if settings.bedrock_plan_model_id:
            thinking_model = BedrockModel(
                cache_prompt="default",
                cache_tools="default",
                model_id=settings.bedrock_plan_model_id,
                temperature=settings.model_temperature,
            )
            configure_phase_models(
                thinking=thinking_model,
                executing=self.model,
            )
            # Start the agent on the thinking model (first turn is usually
            # investigation / planning).
            initial_model = thinking_model
            logger.info(
                "Phase-based model switching enabled: thinking=%s, executing=%s",
                settings.bedrock_plan_model_id,
                settings.bedrock_model_id,
            )
        else:
            initial_model = self.model
            logger.info(
                "Phase-based model switching disabled (bedrock_plan_model_id not set)"
            )

        self.session_dir = settings.strands_session_dir
        if not self.session_dir:
            self.session_dir = os.path.join(settings.project_root, ".tokuye", "sessions")
        os.makedirs(self.session_dir, exist_ok=True)
        self.session_manager = FileSessionManager(
            session_id=thread_id, storage_dir=self.session_dir
        )

        # Initialize MCP clients
        self.mcp_manager = MCPClientManager(settings.mcp_servers)
        self.mcp_manager.start()
        mcp_tools = self.mcp_manager.get_tools()
        if mcp_tools:
            logger.info(f"Loaded {len(mcp_tools)} tools from MCP servers")
        combined_tools = list(all_tools) + mcp_tools

        self.agent = Agent(
            model=initial_model,
            tools=combined_tools,
            system_prompt=self.system_prompt,
            session_manager=self.session_manager,
            conversation_manager=SummarizingConversationManager(
                summarization_system_prompt=self.summary_prompt
            ),
            callback_handler=self._callback_handler,
        )
        self.max_steps = max_steps
        self.step_count = 0
        self._cleaned_up = False

    async def __call__(self, *args, **kwargs):
        token_tracker.reset_turn()
        self.set_thinking(True)
        try:
            result = await self.agent.invoke_async(*args, **kwargs)
            self._update_token_usage(result)
            return result
        finally:
            self.set_thinking(False)

    def _callback_handler(self, **kwargs):
        if "event" in kwargs and kwargs["event"].get("messageStop") is not None:
            self.step_count += 1
            if self.step_count > self.max_steps:
                raise MaxStepsException("Maximum number of steps exceeded")
        if "message" in kwargs and kwargs["message"].get("role") == "assistant":
            if kwargs["message"].get("content") is not None:
                for c in kwargs["message"]["content"]:
                    if c.get("text"):
                        self.add_ai_message(c["text"])

    def _update_token_usage(self, result: AgentResult):
        # Use latest_agent_invocation.usage (this invocation only) instead of
        # accumulated_usage (all invocations) to avoid double-counting across turns.
        latest = result.metrics.latest_agent_invocation
        if latest is None:
            return

        # Determine which model was active at the end of this invocation so we
        # can pick the correct cost table.  When bedrock_plan_model_id is set the
        # agent switches between thinking / executing models mid-invocation; we
        # use the model that was active when the invocation completed as the best
        # available approximation.
        current_model_id = self.agent.model.config.get("model_id", "") or ""
        model_identifier: str | None = None
        if settings.bedrock_plan_model_id and settings.plan_model_identifier:
            if settings.bedrock_plan_model_id in current_model_id:
                model_identifier = settings.plan_model_identifier

        token_tracker.add_usage(latest.usage, model_identifier=model_identifier)
        turn_usage_summary = token_tracker.format_usage_summary()
        self.update_token_usage(turn_usage_summary)

    def cleanup(self):
        """Clean up MCP client connections."""
        if self._cleaned_up:
            return
        self._cleaned_up = True
        if self.mcp_manager:
            self.mcp_manager.stop()
            logger.info("MCP clients cleaned up")
