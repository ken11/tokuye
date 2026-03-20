"""
State machine for v2 (state_machine_mode) workflow.

Responsibilities:
- Define DevState enum
- StateClassifier: use a lightweight model (e.g. Nova Pro) to determine
  the next state from (current_state, user_message) without any tools or
  conversation history.
- StateMachine: hold the current state and delegate to StateClassifier.
"""

import json
import logging
from enum import Enum

from strands import Agent
from strands.models import BedrockModel

from tokuye.prompts.prompt_loader import load_prompt
from tokuye.utils.config import settings

logger = logging.getLogger(__name__)


class DevState(Enum):
    IDLE = "IDLE"
    PLANNING = "PLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    IMPLEMENTING = "IMPLEMENTING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    PR_CREATING = "PR_CREATING"
    SELF_REVIEWING = "SELF_REVIEWING"
    REVIEWING = "REVIEWING"
    AWAITING_REVIEW_APPROVAL = "AWAITING_REVIEW_APPROVAL"

    @classmethod
    def from_str(cls, value: str) -> "DevState":
        try:
            return cls(value.upper())
        except ValueError:
            logger.warning("Unknown state value %r, falling back to IDLE", value)
            return cls.IDLE


# States where the node agent drives the transition (not the user message).
# When the current state is one of these, the classifier is skipped and the
# state advances automatically after the node finishes.
_AUTO_ADVANCE: dict["DevState", "DevState"] = {
    DevState.PLANNING: DevState.AWAITING_APPROVAL,
    DevState.IMPLEMENTING: DevState.AWAITING_REVIEW,
    DevState.PR_CREATING: DevState.IDLE,
    DevState.SELF_REVIEWING: DevState.AWAITING_REVIEW,
    DevState.REVIEWING: DevState.AWAITING_REVIEW_APPROVAL,
}


class StateClassifier:
    """Classify (current_state, user_message) → next DevState.

    Uses a lightweight LLM with no tools and no conversation history.
    The prompt is loaded from ``state_classifier_prompt.md``.
    """

    def __init__(self, model: BedrockModel) -> None:
        if settings.language == "en":
            self._prompt = load_prompt("state_classifier_prompt_en.md")
        else:
            self._prompt = load_prompt("state_classifier_prompt.md")
        self._agent = Agent(
            model=model,
            system_prompt=self._prompt,
            tools=[],
            callback_handler=None,
        )

    async def classify(self, current_state: DevState, user_message: str) -> DevState:
        """Return the next state synchronously."""
        if settings.language == "en":
            user_content = (
                f"Current state: {current_state.value}\n"
                f"User message: {user_message}"
            )
        else:
            user_content = (
                f"現在のステート: {current_state.value}\n"
                f"ユーザーの発言: {user_message}"
            )
        try:
            # Reset history to keep each classification stateless
            self._agent.messages.clear()
            result = await self._agent.invoke_async(user_content)
            raw = str(result)

            # Parse JSON
            # Strip markdown code fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.splitlines()
                cleaned = "\n".join(
                    line for line in lines
                    if not line.startswith("```")
                ).strip()

            data = json.loads(cleaned)
            next_state = DevState.from_str(data["next_state"])
            logger.info(
                "StateClassifier: %s + %r → %s",
                current_state.value,
                user_message[:80],
                next_state.value,
            )
            return next_state
        except Exception as exc:
            logger.warning(
                "StateClassifier failed (%s); staying in %s",
                exc,
                current_state.value,
            )
            return current_state


class StateMachine:
    """Hold the current DevState and expose transition helpers."""

    def __init__(self, classifier: StateClassifier) -> None:
        self._classifier = classifier
        self.state: DevState = DevState.IDLE

    async def transition_by_user(self, user_message: str) -> DevState:
        """Classify user message and advance state. Returns the new state."""
        next_state = await self._classifier.classify(self.state, user_message)
        self.state = next_state
        return self.state

    def transition_after_node(self) -> DevState:
        """Advance state automatically after a node finishes (if applicable).

        Returns the new state (unchanged if no auto-advance is defined).
        """
        next_state = _AUTO_ADVANCE.get(self.state, self.state)
        if next_state != self.state:
            logger.info(
                "StateMachine auto-advance: %s → %s",
                self.state.value,
                next_state.value,
            )
        self.state = next_state
        return self.state

    def reset(self) -> None:
        self.state = DevState.IDLE
