import logging
import os

from git import Repo
from strands import Agent
from strands.agent import AgentResult
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.models import BedrockModel
from strands.session.file_session_manager import FileSessionManager
from tokuye.agent.node_agents import NodeAgents
from tokuye.agent.state_machine import DevState, StateClassifier, StateMachine
from tokuye.mcp import MCPClientManager
from tokuye.prompts.prompt_loader import (load_custom_system_prompt,
                                          load_prompt, load_prompt_if_exists)
from tokuye.tools.strands_tools import all_tools
from tokuye.tools.strands_tools.phase_tool import configure_phase_models
from tokuye.utils.config import settings
from tokuye.utils.token_tracker import token_tracker

logger = logging.getLogger(__name__)


def _supports_prompt_cache(model_identifier: str) -> bool:
    """Return True if the model supports Bedrock prompt caching.

    Determined by model_identifier (the normalised internal name), not the
    raw model_id / ARN.  Claude models and Amazon Nova Pro support prompt
    caching; Mistral Devstral does not.
    """
    return model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6", "nova-pro")


def _supports_tool_cache(model_identifier: str) -> bool:
    """Return True if the model supports caching tool definitions on Bedrock.

    Determined by model_identifier.  Nova models only support message-level
    caching; tool-level caching (cachePoint in toolConfig) causes a
    ValidationException.  Only Claude models support cache_tools.
    """
    return model_identifier in ("sonnet-4-6", "haiku-4-5", "opus-4-6")


class MaxStepsException(Exception):

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class StrandsAgent:
    def __init__(
        self,
        thread_id,
        max_steps,
        add_ai_message,
        add_system_message,
        set_thinking,
        update_token_usage,
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
        elif settings.model_identifier == "devstral-2":
            self.system_prompt = load_prompt("system_prompt_devstral.md")
            logger.info(
                "Using Devstral-specific system prompt: system_prompt_devstral.md"
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
        _exec_cache = _supports_prompt_cache(settings.model_identifier)
        _exec_tool_cache = _supports_tool_cache(settings.model_identifier)
        self.model = BedrockModel(
            **({"cache_prompt": "default"} if _exec_cache else {}),
            **({"cache_tools": "default"} if _exec_tool_cache else {}),
            model_id=settings.bedrock_model_id,
            temperature=settings.model_temperature,
        )

        # When bedrock_plan_model_id is configured, create a separate
        # "thinking" model and wire up the phase-switching tool.
        if settings.bedrock_plan_model_id:
            _plan_cache = _supports_prompt_cache(settings.plan_model_identifier)
            _plan_tool_cache = _supports_tool_cache(settings.plan_model_identifier)
            thinking_model = BedrockModel(
                **({"cache_prompt": "default"} if _plan_cache else {}),
                **({"cache_tools": "default"} if _plan_tool_cache else {}),
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
            self.session_dir = os.path.join(
                settings.project_root, ".tokuye", "sessions"
            )
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

        # --- v2: state machine mode --------------------------------------
        if settings.state_machine_mode:
            classifier_model_id = (
                settings.bedrock_classifier_model_id or settings.bedrock_model_id
            )
            classifier_identifier = (
                settings.classifier_model_identifier or settings.model_identifier
            )
            _cls_cache = _supports_prompt_cache(classifier_identifier)
            classifier_model = BedrockModel(
                **({"cache_prompt": "default"} if _cls_cache else {}),
                model_id=classifier_model_id,
                temperature=0.0,  # deterministic classification
            )
            self._state_classifier = StateClassifier(classifier_model)
            self._state_machine = StateMachine(self._state_classifier)
            self._node_agents = NodeAgents(
                thread_id=thread_id,
                add_ai_message=add_ai_message,
                add_system_message=add_system_message,
                set_thinking=set_thinking,
                update_token_usage=update_token_usage,
                mcp_manager=self.mcp_manager,
            )
            logger.info(
                "State machine mode enabled: classifier=%s, impl=%s",
                classifier_model_id,
                settings.bedrock_impl_model_id or settings.bedrock_model_id,
            )
        else:
            self._state_machine = None
            self._node_agents = None

        # Buffers to carry outputs between nodes (v2 only)
        self._last_planner_output: str = ""
        self._last_developer_output: str = ""
        self.current_task_branch: str = ""  # ← add this line

    async def __call__(self, *args, **kwargs):
        self.set_thinking(True)
        try:
            if settings.state_machine_mode:
                return await self._call_v2(*args, **kwargs)
            else:
                return await self._call_v1(*args, **kwargs)
        finally:
            self.set_thinking(False)

    async def _call_v1(self, *args, **kwargs):
        """Original single-agent flow (v1)."""
        token_tracker.reset_turn()
        result = await self.agent.invoke_async(*args, **kwargs)
        self._update_token_usage(result)
        return result

    async def _call_v2(self, message: str = None, **kwargs):
        """State machine flow (v2).

        1. Classify user message → determine next state
        2. Invoke the appropriate node agent
        3. Auto-advance state after node completes (if applicable)
        """
        sm = self._state_machine
        nodes = self._node_agents

        # --- Determine next state ----------------------------------------
        if message is not None:
            next_state = await sm.transition_by_user(message)
        else:
            next_state = sm.state

        self.add_system_message(f"[State: {next_state.value}]")
        logger.info("v2 dispatch: state=%s", next_state.value)

        # --- Dispatch to node --------------------------------------------
        if next_state == DevState.IDLE:
            return None

        elif next_state == DevState.PLANNING:
            result = await nodes.invoke_planner(message)
            # Capture Planner output for downstream nodes
            self._last_planner_output = str(result)
            sm.transition_after_node()  # PLANNING → AWAITING_APPROVAL
            self.add_system_message(f"[State: {sm.state.value}]")

        elif next_state == DevState.AWAITING_APPROVAL:
            # Planner has already presented the plan; just wait for user approval.
            # No node invocation needed.
            result = None

        elif next_state == DevState.IMPLEMENTING:
            # Prefer Planner output as the source of truth.
            # Fall back to user message when re-implementing from AWAITING_REVIEW.
            source = self._last_planner_output if self._last_planner_output else message
            # If already on a work branch (re-implementation case), instruct Developer not to create a new branch
            if self.current_task_branch:
                source = (
                    f"{source}\n\n---\n"
                    f"**Branch instruction**: You are already on the work branch "
                    f"`{self.current_task_branch}`. Do NOT call create_branch. "
                    f"Just implement the changes and commit."
                )
            result = await nodes.invoke_developer(source)
            self._last_developer_output = str(result)
            self._last_planner_output = ""  # consumed
            # After IMPLEMENTING completes, capture the active branch name
            try:
                self.current_task_branch = Repo(
                    settings.project_root
                ).active_branch.name
            except Exception:
                pass
            sm.transition_after_node()
            self.add_system_message(f"[State: {sm.state.value}]")

        elif next_state in (DevState.PR_CREATING, DevState.SELF_REVIEWING):
            # PR Creator receives Developer output (structured by translation layer).
            # For SELF_REVIEWING triggered directly by user, use user message.
            source = (
                self._last_developer_output
                if next_state == DevState.PR_CREATING and self._last_developer_output
                else message
            )
            result = await nodes.invoke_pr_creator(source)
            if next_state == DevState.PR_CREATING:
                self._last_developer_output = ""  # consumed
                sm.transition_after_node()
                self.add_system_message(f"[State: {sm.state.value}]")
            elif next_state == DevState.SELF_REVIEWING:
                # Auto-advance to AWAITING_REVIEW so user can decide next step
                sm.transition_after_node()
                self.add_system_message(f"[State: {sm.state.value}]")

        elif next_state in (DevState.REVIEWING, DevState.AWAITING_REVIEW_APPROVAL):
            result = await nodes.invoke_reviewer(message)
            if next_state == DevState.REVIEWING:
                sm.transition_after_node()
                self.add_system_message(f"[State: {sm.state.value}]")

        elif next_state == DevState.AWAITING_REVIEW:
            result = None

        else:
            logger.warning(
                "v2: unhandled state %s, falling back to planner", next_state.value
            )
            result = await nodes.invoke_planner(message)

        return result

    def _callback_handler(self, **kwargs):
        if "event" in kwargs and kwargs["event"].get("messageStop") is not None:
            self.step_count += 1
            if self.step_count > self.max_steps:
                raise MaxStepsException("Maximum number of steps exceeded")
        if "message" in kwargs and kwargs["message"].get("role") == "assistant":
            if kwargs["message"].get("content") is not None:
                for c in kwargs["message"]["content"]:
                    if c.get("text", "").strip():
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
