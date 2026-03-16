"""Phase reporting tool for automatic model switching.

When ``bedrock_plan_model_id`` is configured, the agent can call
``report_phase`` to declare whether it is in a *thinking* phase (investigation,
analysis, planning) or an *executing* phase (file writes, patches, commits).
The tool swaps ``agent.model`` accordingly so that a stronger model handles
reasoning while a lighter model handles implementation.

If ``bedrock_plan_model_id`` is **not** set, the tool is still callable but
becomes a no-op — the model stays unchanged.
"""

import logging
from typing import Optional

from strands import ToolContext, tool
from strands.models import BedrockModel

logger = logging.getLogger(__name__)

# Module-level references set by StrandsAgent at init time.
# When plan-mode is disabled these stay ``None`` and the tool is a no-op.
_thinking_model: Optional[BedrockModel] = None
_executing_model: Optional[BedrockModel] = None


def configure_phase_models(
    thinking: BedrockModel,
    executing: BedrockModel,
) -> None:
    """Called once from ``StrandsAgent.__init__`` to wire up the two models."""
    global _thinking_model, _executing_model
    _thinking_model = thinking
    _executing_model = executing


@tool(
    name="report_phase",
    description=(
        "Report the current work phase. "
        "Call this whenever the phase changes. "
        "phase must be 'thinking' (investigation, analysis, planning, review) "
        "or 'executing' (file writes, patches, commits, branch creation). "
        "The underlying model is automatically optimised for each phase."
    ),
    context=True,
)
def report_phase(phase: str, tool_context: ToolContext) -> str:
    """Report the current work phase so the system can optimise the model.

    Args:
        phase: Either ``"thinking"`` or ``"executing"``.
        tool_context: Injected execution context (provides access to the agent).

    Returns:
        Confirmation message.
    """
    if phase not in ("thinking", "executing"):
        return (
            f"Invalid phase: {phase!r}. "
            "Must be 'thinking' or 'executing'."
        )

    # No-op when plan-mode is not configured.
    if _thinking_model is None or _executing_model is None:
        logger.debug("report_phase called but plan-mode is not configured — no-op")
        return f"Phase noted: {phase} (model switching is not active)"

    target_model = _thinking_model if phase == "thinking" else _executing_model
    current_model = tool_context.agent.model

    if current_model is target_model:
        logger.info("Phase: %s (model unchanged — already on the right model)", phase)
        return f"Phase: {phase} (already on the right model)"

    tool_context.agent.model = target_model
    logger.info(
        "Phase changed → %s (model switched)",
        phase,
    )
    return f"Phase switched to: {phase}"
