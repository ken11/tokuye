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

Tool sandboxing
---------------
The Worker receives a tool set sandboxed to the repository resolved from
``repo_name`` via epic.yaml.  It cannot read, write, or execute git/GitHub
operations outside that directory.
"""

from __future__ import annotations

import logging

from strands import tool

from tokuye.agent.epic_worker_agent import EpicWorkerAgent
from tokuye.utils.epic_config import resolve_repo_path

logger = logging.getLogger(__name__)


@tool(
    name="run_epic_worker",
    description=(
        "Delegate an implementation task to EpicWorkerAgent. "
        "The worker runs with a tool set sandboxed to the target repository "
        "and returns a YAML result string. "
        "repo_name must be a key defined in .tokuye/epic.yaml. "
        "Calling with the same epic_id + task_id resumes the existing session; "
        "changing task_id starts a new isolated session."
    ),
)
def run_epic_worker(epic_id: str, task_id: str, repo_name: str, instruction: str) -> str:
    """Invoke EpicWorkerAgent for a specific task.

    Args:
        epic_id: Epic identifier (e.g. 'auth-cognito-migration').
        task_id: Task identifier within the epic (e.g. 'T001').
        repo_name: Repository key from epic.yaml (e.g. 'backend').
            Used to resolve the absolute path of the target repository and
            to sandbox all Worker tools to that directory.
        instruction: Full task instruction for the worker.

    Returns:
        Raw YAML result string from EpicWorkerAgent.
    """
    logger.info("run_epic_worker: epic=%s task=%s repo=%s", epic_id, task_id, repo_name)
    repo_root = resolve_repo_path(repo_name)
    worker = EpicWorkerAgent(epic_id=epic_id, task_id=task_id, repo_root=repo_root)
    return worker(instruction)
