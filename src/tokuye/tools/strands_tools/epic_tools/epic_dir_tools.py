"""
Epic directory management tools for EpicManagerAgent.

All operations are scoped to ``<project_root>/epics/<epic_id>/``.
The project_root is always taken from ``settings.project_root`` (the Epic
management directory), never from individual repo paths.

Directory layout created by these tools:

  <project_root>/
    epics/
      <epic_id>/
        epic.md          – original Epic request text
        plan.md          – implementation plan
        tasks.yaml       – task list with status
        progress.md      – running progress log
        decisions.md     – design decisions / notes
        results/
          <task_id>.yaml – per-task execution result
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml
from strands import tool

from tokuye.utils.config import settings

logger = logging.getLogger(__name__)


def _epic_dir(epic_id: str) -> Path:
    """Return the absolute path of the epic working directory."""
    if settings.project_root is None:
        raise ValueError("settings.project_root is not set")
    return settings.project_root / "epics" / epic_id


def _ensure_epic_dir(epic_id: str) -> Path:
    d = _epic_dir(epic_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "results").mkdir(exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool(
    name="create_epic_dir",
    description=(
        "Create the working directory for a new Epic and write the original "
        "Epic request text to epic.md. "
        "Returns the path of the created directory."
    ),
)
def create_epic_dir(epic_id: str, epic_request: str) -> str:
    """Create epic working directory and save the original request.

    Args:
        epic_id: Unique identifier for the Epic (e.g. 'auth-cognito-migration').
                 Use kebab-case, ASCII only.
        epic_request: The original Epic request text from the user.

    Returns:
        Path string of the created directory.
    """
    d = _ensure_epic_dir(epic_id)
    epic_md = d / "epic.md"
    epic_md.write_text(epic_request, encoding="utf-8")
    logger.info("Created epic dir: %s", d)
    return f"Created epic directory: {d}\nSaved epic request to: {epic_md}"


@tool(
    name="save_epic_plan",
    description=(
        "Save the implementation plan for an Epic to plan.md. "
        "Overwrites any existing plan. "
        "Call this after the user has approved the plan."
    ),
)
def save_epic_plan(epic_id: str, plan: str) -> str:
    """Save implementation plan to plan.md.

    Args:
        epic_id: Epic identifier.
        plan: Full plan text (Markdown).

    Returns:
        Confirmation message with file path.
    """
    d = _ensure_epic_dir(epic_id)
    plan_md = d / "plan.md"
    plan_md.write_text(plan, encoding="utf-8")
    logger.info("Saved plan for epic %s", epic_id)
    return f"Plan saved to: {plan_md}"


@tool(
    name="save_epic_tasks",
    description=(
        "Save the task list for an Epic to tasks.yaml. "
        "Each task must have: id, title, repo, status (pending/in_progress/completed/skipped), "
        "and optionally description and depends_on. "
        "Overwrites any existing tasks.yaml."
    ),
)
def save_epic_tasks(epic_id: str, tasks_yaml: str) -> str:
    """Save task list to tasks.yaml.

    Args:
        epic_id: Epic identifier.
        tasks_yaml: YAML string representing the task list.
                    Expected structure:
                      tasks:
                        - id: T001
                          title: "..."
                          repo: backend
                          status: pending
                          description: "..."

    Returns:
        Confirmation message with file path.
    """
    # Validate YAML before writing
    try:
        parsed = yaml.safe_load(tasks_yaml)
        if not isinstance(parsed, dict) or "tasks" not in parsed:
            return "Error: tasks_yaml must be a YAML mapping with a 'tasks' key."
    except yaml.YAMLError as e:
        return f"Error: invalid YAML: {e}"

    d = _ensure_epic_dir(epic_id)
    tasks_file = d / "tasks.yaml"
    tasks_file.write_text(tasks_yaml, encoding="utf-8")
    logger.info("Saved tasks for epic %s", epic_id)
    return f"Tasks saved to: {tasks_file}"


@tool(
    name="save_task_result",
    description=(
        "Save the execution result of a single task to results/<task_id>.yaml. "
        "Call this after the user has confirmed the task result is acceptable."
    ),
)
def save_task_result(epic_id: str, task_id: str, result_yaml: str) -> str:
    """Save task execution result.

    Args:
        epic_id: Epic identifier.
        task_id: Task identifier (e.g. 'T001').
        result_yaml: YAML string of the task result.
                     Recommended fields:
                       status: completed | approval_required | failed
                       summary: "..."
                       changed_files: [...]
                       commit: "abc123"
                       needs_user_review: true
                       notes: "..."

    Returns:
        Confirmation message with file path.
    """
    try:
        yaml.safe_load(result_yaml)
    except yaml.YAMLError as e:
        return f"Error: invalid YAML: {e}"

    d = _ensure_epic_dir(epic_id)
    result_file = d / "results" / f"{task_id}.yaml"
    result_file.write_text(result_yaml, encoding="utf-8")
    logger.info("Saved result for task %s in epic %s", task_id, epic_id)
    return f"Task result saved to: {result_file}"


@tool(
    name="update_epic_progress",
    description=(
        "Append a progress entry to progress.md. "
        "Use this to record milestones, approvals, and status changes."
    ),
)
def update_epic_progress(epic_id: str, entry: str) -> str:
    """Append a progress entry to progress.md.

    Args:
        epic_id: Epic identifier.
        entry: Progress entry text (plain text or Markdown).
               A timestamp will be prepended automatically.

    Returns:
        Confirmation message.
    """
    import datetime

    d = _ensure_epic_dir(epic_id)
    progress_md = d / "progress.md"

    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"\n## {timestamp}\n\n{entry}\n"

    with open(progress_md, "a", encoding="utf-8") as f:
        f.write(line)

    logger.info("Updated progress for epic %s", epic_id)
    return f"Progress updated in: {progress_md}"


@tool(
    name="save_epic_decisions",
    description=(
        "Append a design decision or important note to decisions.md. "
        "Use this to record architectural choices, constraints, or handoff notes "
        "that future tasks should be aware of."
    ),
)
def save_epic_decisions(epic_id: str, decision: str) -> str:
    """Append a decision entry to decisions.md.

    Args:
        epic_id: Epic identifier.
        decision: Decision text (Markdown).

    Returns:
        Confirmation message.
    """
    import datetime

    d = _ensure_epic_dir(epic_id)
    decisions_md = d / "decisions.md"

    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"\n## {timestamp}\n\n{decision}\n"

    with open(decisions_md, "a", encoding="utf-8") as f:
        f.write(line)

    logger.info("Saved decision for epic %s", epic_id)
    return f"Decision saved to: {decisions_md}"


@tool(
    name="read_epic_file",
    description=(
        "Read a file from the Epic working directory. "
        "Supported file names: epic.md, plan.md, tasks.yaml, progress.md, decisions.md, "
        "or results/<task_id>.yaml."
    ),
)
def read_epic_file(epic_id: str, filename: str) -> str:
    """Read a file from the Epic working directory.

    Args:
        epic_id: Epic identifier.
        filename: File name relative to the epic directory.
                  Examples: 'plan.md', 'tasks.yaml', 'results/T001.yaml'

    Returns:
        File contents as a string, or an error message if not found.
    """
    d = _epic_dir(epic_id)
    target = (d / filename).resolve()

    # Safety: must stay inside the epic directory
    try:
        target.relative_to(d.resolve())
    except ValueError:
        return f"Error: '{filename}' is outside the epic directory."

    if not target.exists():
        return f"File not found: {target}"

    return target.read_text(encoding="utf-8")
