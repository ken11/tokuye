"""
Node agents for state machine mode (v2).

Each node is an independent Agent instance with a dedicated model and
a minimal tool set.  Keeping tool sets small reduces input token overhead
and prevents unintended tool calls.

Node layout
-----------
Planner     – Claude (bedrock_model_id)
              Investigates the project and produces an implementation plan.
Developer   – Devstral (bedrock_impl_model_id, falls back to bedrock_model_id)
              Implements the plan; no investigation tools.
PR Creator  – Nova Pro (bedrock_pr_model_id, falls back to bedrock_model_id)
              Creates PRs and performs self-review.
Reviewer    – Claude (bedrock_model_id)
              Reviews other people's PRs; posts comments only after approval.

Translation layer
-----------------
Between Planner→Developer and Developer→PR Creator, a lightweight Claude call
(no tools) translates/restructures the output so each node receives exactly
the information it needs in the right language.

  ① plan_to_developer   : Japanese plan → English structured instructions for Devstral
  ② feedback_to_developer: Japanese user feedback → English correction instructions for Devstral
  ③ developer_to_pr_creator: Developer report → PR context for PR Creator
"""

import logging
import os

from strands import Agent
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.models import BedrockModel
from strands.session.file_session_manager import FileSessionManager

from tokuye.mcp import MCPClientManager
from tokuye.prompts.prompt_loader import load_prompt, load_prompt_if_exists
from tokuye.tools.strands_tools import (
    developer_tools,
    planner_tools,
    pr_creator_tools,
    reviewer_tools,
)
from tokuye.utils.config import settings
from tokuye.utils.token_tracker import token_tracker

logger = logging.getLogger(__name__)


def _make_bedrock_model(model_id: str, model_identifier: str) -> BedrockModel:
    """Build a BedrockModel with appropriate cache settings."""
    cache_prompt = model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6", "nova-pro")
    cache_tools = model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6")
    return BedrockModel(
        **({"cache_prompt": "default"} if cache_prompt else {}),
        **({"cache_tools": "default"} if cache_tools else {}),
        model_id=model_id,
        temperature=settings.model_temperature,
    )


class NodeAgents:
    """Container for all node agents used in state machine mode.

    Each agent is created once and reused across turns within the same
    conversation session.  Conversation history is intentionally NOT shared
    between nodes – each node receives only the information it needs via the
    message passed to it.
    """

    def __init__(
        self,
        thread_id: str,
        add_ai_message,
        add_system_message,
        set_thinking,
        update_token_usage,
        mcp_manager: MCPClientManager,
    ) -> None:
        self.add_ai_message = add_ai_message
        self.add_system_message = add_system_message
        self.set_thinking = set_thinking
        self.update_token_usage = update_token_usage

        # Session storage (shared directory, separate session IDs per node)
        session_dir = settings.strands_session_dir
        if not session_dir:
            session_dir = os.path.join(settings.project_root, ".tokuye", "sessions")
        os.makedirs(session_dir, exist_ok=True)

        # Summary prompt (language-aware)
        summary_prompt = (
            load_prompt_if_exists("summary_prompt.md")
            if settings.language == "ja"
            else load_prompt_if_exists("summary_prompt_en.md")
        )

        # MCP tools (appended to each node's tool list)
        mcp_tools = mcp_manager.get_tools()
        if mcp_tools:
            logger.info("NodeAgents: loaded %d MCP tools", len(mcp_tools))

        # --- Primary model (Claude) ---------------------------------------
        primary_model = _make_bedrock_model(
            settings.bedrock_model_id, settings.model_identifier
        )

        # --- Implementation model (Devstral or fallback) ------------------
        impl_model_id = settings.bedrock_impl_model_id or settings.bedrock_model_id
        impl_identifier = settings.impl_model_identifier or settings.model_identifier
        impl_model = _make_bedrock_model(impl_model_id, impl_identifier)

        # --- PR Creator model (Nova Pro or fallback) ----------------------
        pr_model_id = settings.bedrock_pr_model_id or settings.bedrock_model_id
        pr_identifier = settings.pr_model_identifier or settings.model_identifier
        pr_model = _make_bedrock_model(pr_model_id, pr_identifier)

        # --- Translation agents: Strands Agent (no tools, stateless per call) ---
        plan_to_dev_prompt = load_prompt("plan_to_developer_prompt.md")
        if settings.language == "ja":
            dev_to_pr_prompt = load_prompt("developer_to_pr_creator_prompt_ja.md")
        else:
            dev_to_pr_prompt = load_prompt("developer_to_pr_creator_prompt.md")

        self._plan_to_dev_agent = Agent(
            model=_make_bedrock_model(settings.bedrock_model_id, settings.model_identifier),
            system_prompt=plan_to_dev_prompt,
            tools=[],
            callback_handler=None,
        )
        self._dev_to_pr_agent = Agent(
            model=_make_bedrock_model(settings.bedrock_model_id, settings.model_identifier),
            system_prompt=dev_to_pr_prompt,
            tools=[],
            callback_handler=None,
        )

        # --- Planner ------------------------------------------------------
        if settings.language == "en":
            planner_prompt = load_prompt("system_prompt_planner_en.md")
        else:
            planner_prompt = load_prompt("system_prompt_planner.md")
        self.planner = Agent(
            model=primary_model,
            tools=list(planner_tools) + mcp_tools,
            system_prompt=planner_prompt,
            session_manager=FileSessionManager(
                session_id=f"{thread_id}_planner", storage_dir=session_dir
            ),
            conversation_manager=SummarizingConversationManager(
                summarization_system_prompt=summary_prompt
            ),
            callback_handler=self._make_callback("planner"),
        )

        # --- Developer ----------------------------------------------------
        developer_prompt = load_prompt("system_prompt_developer.md")
        self.developer = Agent(
            model=impl_model,
            tools=list(developer_tools),
            system_prompt=developer_prompt,
            session_manager=FileSessionManager(
                session_id=f"{thread_id}_developer", storage_dir=session_dir
            ),
            conversation_manager=SummarizingConversationManager(
                summarization_system_prompt=summary_prompt
            ),
            callback_handler=self._make_callback("developer"),
        )

        # --- PR Creator ---------------------------------------------------
        if settings.language == "en":
            pr_creator_prompt = load_prompt("system_prompt_pr_creator_en.md")
        else:
            pr_creator_prompt = load_prompt("system_prompt_pr_creator.md")
        self.pr_creator = Agent(
            model=pr_model,
            tools=list(pr_creator_tools) + mcp_tools,
            system_prompt=pr_creator_prompt,
            session_manager=FileSessionManager(
                session_id=f"{thread_id}_pr_creator", storage_dir=session_dir
            ),
            conversation_manager=SummarizingConversationManager(
                summarization_system_prompt=summary_prompt
            ),
            callback_handler=self._make_callback("pr_creator"),
        )

        # --- Reviewer -----------------------------------------------------
        if settings.language == "en":
            reviewer_prompt = load_prompt("system_prompt_reviewer_en.md")
        else:
            reviewer_prompt = load_prompt("system_prompt_reviewer.md")
        self.reviewer = Agent(
            model=primary_model,
            tools=list(reviewer_tools) + mcp_tools,
            system_prompt=reviewer_prompt,
            session_manager=FileSessionManager(
                session_id=f"{thread_id}_reviewer", storage_dir=session_dir
            ),
            conversation_manager=SummarizingConversationManager(
                summarization_system_prompt=summary_prompt
            ),
            callback_handler=self._make_callback("reviewer"),
        )

        logger.info(
            "NodeAgents initialised: primary=%s, impl=%s, pr=%s",
            settings.bedrock_model_id,
            impl_model_id,
            pr_model_id,
        )

    # ------------------------------------------------------------------
    # Translation layer
    # ------------------------------------------------------------------

    def _translate(self, agent: Agent, content: str) -> str:
        """Single-shot Agent call for translation/restructuring. Stateless (history cleared)."""
        try:
            agent.messages.clear()
            result = agent(content)
            return str(result).strip()
        except Exception as exc:
            logger.warning("Translation failed (%s); returning original content", exc)
            return content

    def translate_plan_for_developer(self, plan_text: str) -> str:
        """Convert Planner output (possibly Japanese) to English instructions for Devstral.

        Used for both:
          ① Initial plan → Developer (AWAITING_APPROVAL → IMPLEMENTING)
          ② User feedback → Developer (AWAITING_REVIEW → IMPLEMENTING)
        """
        logger.info("Translating plan/feedback for Developer")
        return self._translate(self._plan_to_dev_agent, plan_text)

    def translate_developer_output_for_pr_creator(self, dev_output: str) -> str:
        """Restructure Developer output into PR context for PR Creator."""
        logger.info("Translating Developer output for PR Creator")
        return self._translate(self._dev_to_pr_agent, dev_output)

    # ------------------------------------------------------------------
    # Callbacks and token tracking
    # ------------------------------------------------------------------

    def _make_callback(self, node_name: str):
        """Return a callback_handler closure for the given node."""

        def _handler(**kwargs):
            if "message" in kwargs and kwargs["message"].get("role") == "assistant":
                for c in kwargs["message"].get("content", []):
                    if c.get("text"):
                        self.add_ai_message(c["text"])

        return _handler

    def _update_token_usage(self, result, model_identifier: str | None = None):
        latest = result.metrics.latest_agent_invocation
        if latest is None:
            return
        token_tracker.add_usage(latest.usage, model_identifier=model_identifier)
        self.update_token_usage(token_tracker.format_usage_summary())

    # ------------------------------------------------------------------
    # Node invocations
    # ------------------------------------------------------------------

    async def invoke_planner(self, message: str):
        token_tracker.reset_turn()
        result = await self.planner.invoke_async(message)
        self._update_token_usage(result, model_identifier=settings.model_identifier)
        return result

    async def invoke_developer(self, message: str):
        """Translate message first, then invoke Developer."""
        translated = self.translate_plan_for_developer(message)
        self.add_system_message("[Translated instructions sent to Developer]")
        token_tracker.reset_turn()
        impl_identifier = settings.impl_model_identifier or settings.model_identifier
        result = await self.developer.invoke_async(translated)
        self._update_token_usage(result, model_identifier=impl_identifier)
        return result

    async def invoke_pr_creator(self, message: str):
        """Translate Developer output first, then invoke PR Creator."""
        translated = self.translate_developer_output_for_pr_creator(message)
        self.add_system_message("[Developer output structured for PR Creator]")
        token_tracker.reset_turn()
        pr_identifier = settings.pr_model_identifier or settings.model_identifier
        result = await self.pr_creator.invoke_async(translated)
        self._update_token_usage(result, model_identifier=pr_identifier)
        return result

    async def invoke_reviewer(self, message: str):
        token_tracker.reset_turn()
        result = await self.reviewer.invoke_async(message)
        self._update_token_usage(result, model_identifier=settings.model_identifier)
        return result
