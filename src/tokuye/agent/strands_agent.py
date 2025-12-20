import logging
import os

from strands import Agent
from strands.agent import AgentResult
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.models import BedrockModel
from strands.session.file_session_manager import FileSessionManager
from strands.types.event_loop import Usage
from tokuye.prompts.prompt_loader import load_prompt, load_prompt_if_exists
from tokuye.tools.strands_tools import all_tools
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
        if settings.language == "ja":
            self.system_prompt = load_prompt("system_prompt.md")
            self.summary_prompt = load_prompt_if_exists("summary_prompt.md")
        elif settings.language == "en":
            self.system_prompt = load_prompt("system_prompt_en.md")
            self.summary_prompt = load_prompt_if_exists("summary_prompt_en.md")
        self.model = BedrockModel(
            cache_prompt="default",
            cache_tools="default",
            model_id=settings.bedrock_model_id,
            temperature=settings.model_temperature,
        )
        self.session_dir = settings.strands_session_dir
        if not self.session_dir:
            self.session_dir = os.path.join(settings.project_root, ".tokuye", "sessions")
        os.makedirs(self.session_dir, exist_ok=True)
        self.session_manager = FileSessionManager(
            session_id=thread_id, storage_dir=self.session_dir
        )
        self.agent = Agent(
            model=self.model,
            tools=all_tools,
            system_prompt=self.system_prompt,
            session_manager=self.session_manager,
            conversation_manager=SummarizingConversationManager(
                summarization_system_prompt=self.summary_prompt
            ),
            callback_handler=self._callback_handler,
        )
        self.max_steps = max_steps
        self.step_count = 0

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
        usage: Usage = result.metrics.accumulated_usage
        token_tracker.add_usage(usage)
        turn_usage_summary = token_tracker.format_usage_summary()
        self.update_token_usage(turn_usage_summary)
