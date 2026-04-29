"""
EpicWorker tool for EpicManagerAgent (v3 Epic Mode).

Wraps EpicWorkerAgent as a Strands @tool so that EpicManagerAgent can
delegate implementation tasks to a Worker Agent via the standard tool-call
mechanism.

Session isolation
-----------------
session_id is derived from ``epic_id`` and ``task_id``.  Calling this tool
with the same (epic_id, task_id) pair resumes the existing session; changing
either value starts a fresh session automatically.
"""

from __future__ import annotations

import logging

from strands import tool

from tokuye.agent.epic_worker_agent import EpicWorkerAgent

logger = logging.getLogger(__name__)


@tool(
    name="run_epic_worker",
    description=(
        "Delegate an implementation task to EpicWorkerAgent. "
        "The worker runs with the standard developer tool set and returns "
        "a YAML result string. "
        "Calling with the same epic_id + task_id resumes the existing session; "
        "changing task_id starts a new isolated session."
    ),
)
def run_epic_worker(epic_id: str, task_id: str, instruction: str) -> str:
    """Invoke EpicWorkerAgent for a specific task.

    Args:
        epic_id: Epic identifier (e.g. 'auth-cognito-migration').
        task_id: Task identifier within the epic (e.g. 'T001').
        instruction: Full task instruction for the worker.

    Returns:
        Raw YAML result string from EpicWorkerAgent.
    """
    logger.info("run_epic_worker: epic=%s task=%s", epic_id, task_id)
    worker = EpicWorkerAgent(epic_id=epic_id, task_id=task_id)
    return worker(instruction)
