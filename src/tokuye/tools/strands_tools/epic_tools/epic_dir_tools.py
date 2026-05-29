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
        docs/
          <filename>     – supplementary documents (user-instructed)
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
    """Return the absolute path of the epic working directory.

    Raises ValueError if *epic_id* would escape the epics base directory
    (e.g. via path traversal like '../../etc').
    """
    if settings.project_root is None:
        raise ValueError("settings.project_root is not set")
    base = (settings.project_root / "epics").resolve()
    target = (base / epic_id).resolve()
    if not target.is_relative_to(base):
        raise ValueError(
            f"epic_id '{epic_id}' escapes the epics directory. "
            "Use a simple identifier (e.g. 'auth-migration')."
        )
    return target


def _ensure_epic_dir(epic_id: str) -> Path:
    d = _epic_dir(epic_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / "results").mkdir(exist_ok=True)
    (d / "docs").mkdir(exist_ok=True)
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
        "Use this ONLY when creating plan.md for the first time, or when a full "
        "overwrite is explicitly required (e.g. the user asks to rewrite the entire plan). "
        "For partial edits to an existing plan.md (e.g. updating a section), "
        "use replace_exact_epic / insert_after_exact_epic / insert_before_exact_epic "
        "instead — they are safer and avoid accidental data loss. "
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
        "Use this ONLY when creating tasks.yaml for the first time, or when a full "
        "overwrite is explicitly required (e.g. the user asks to rewrite the entire task list). "
        "For partial edits to an existing tasks.yaml (e.g. updating a single task's status), "
        "use replace_exact_epic / insert_after_exact_epic / insert_before_exact_epic "
        "instead — they are safer and avoid accidental data loss."
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
        "results/<task_id>.yaml, or docs/<filename> for supplementary documents."
    ),
)
def read_epic_file(epic_id: str, filename: str) -> str:
    """Read a file from the Epic working directory.

    Args:
        epic_id: Epic identifier.
        filename: File name relative to the epic directory.
                  Examples: 'plan.md', 'tasks.yaml', 'results/T001.yaml',
                  'docs/api-spec.md'

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


# ---------------------------------------------------------------------------
# Supplementary document tools (docs/ subdirectory)
# ---------------------------------------------------------------------------


@tool(
    name="write_epic_doc",
    description=(
        "Write a supplementary document to the docs/ subdirectory of an Epic. "
        "Creates or overwrites docs/<filename>. "
        "Use this ONLY when creating a new file or when a full overwrite is "
        "explicitly required. "
        "For partial edits to an existing document (e.g. updating a section), "
        "use replace_exact_epic / insert_after_exact_epic / insert_before_exact_epic "
        "instead — they are safer and avoid accidental data loss. "
        "filename must be a simple name (e.g. 'api-spec.md'); "
        "subdirectories inside docs/ are not allowed."
    ),
)
def write_epic_doc(epic_id: str, filename: str, content: str) -> str:
    """Write a supplementary document to docs/<filename>.

    Args:
        epic_id: Epic identifier.
        filename: File name inside the docs/ directory (e.g. 'api-spec.md').
                  Must not contain path separators.
        content: Full document content (Markdown or plain text).

    Returns:
        Confirmation message with file path, or an error message.
    """
    if "/" in filename or "\\" in filename:
        return (
            f"Error: filename must not contain path separators. "
            f"Got: '{filename}'. Use a simple name like 'api-spec.md'."
        )

    d = _ensure_epic_dir(epic_id)
    docs_dir = d / "docs"
    target = docs_dir / filename

    target.write_text(content, encoding="utf-8")
    logger.info("Wrote epic doc: %s", target)
    return f"Document saved to: {target}"


@tool(
    name="list_epic_docs",
    description=(
        "List supplementary documents in the docs/ subdirectory of an Epic. "
        "Returns the file names inside docs/, or a message if the directory is empty."
    ),
)
def list_epic_docs(epic_id: str) -> str:
    """List files in the docs/ subdirectory of an Epic.

    Args:
        epic_id: Epic identifier.

    Returns:
        Newline-separated list of file names, or an informational message.
    """
    d = _epic_dir(epic_id)
    docs_dir = d / "docs"

    if not docs_dir.exists():
        return "docs/ directory does not exist yet. Use write_epic_doc to create documents."

    entries = sorted(f.name for f in docs_dir.iterdir() if f.is_file())
    if not entries:
        return "docs/ directory is empty."
    return "\n".join(entries)


# ---------------------------------------------------------------------------
# Epic management directory — scoped read-only tools for EpicManagerAgent
# ---------------------------------------------------------------------------
# These tools are intentionally restricted to <project_root> (the Epic
# management directory).  EpicManagerAgent must NOT use the standard
# read_lines / list_directory tools, which are bound to settings.project_root
# and could be pointed at arbitrary target repositories.
# ---------------------------------------------------------------------------


def _epic_mgmt_root() -> Path:
    """Return the resolved Epic management project_root."""
    if settings.project_root is None:
        raise ValueError("settings.project_root is not set")
    return settings.project_root.resolve()


@tool(
    name="read_lines_epic",
    description=(
        "Read specific lines from a UTF-8 text file inside the Epic management "
        "directory (project_root). "
        "Access is strictly limited to the Epic management directory — "
        "individual target repositories are NOT accessible via this tool. "
        "Line numbers are 1-indexed and inclusive."
    ),
)
def read_lines_epic(file_path: str, start_line: int, end_line: int) -> str:
    """Read lines from a file inside the Epic management directory.

    Args:
        file_path: Path relative to the Epic management project_root.
        start_line: Start line number (1-indexed).
        end_line: End line number (1-indexed, inclusive).

    Returns:
        The joined text of the specified line range, or an error message.
    """
    from tokuye.tools.strands_tools.utils import (
        FileValidationError,
        get_validated_relative_path,
    )

    root = _epic_mgmt_root()

    try:
        abs_path = get_validated_relative_path(root, file_path)
    except FileValidationError:
        return (
            f"Error: Access denied to '{file_path}'. "
            "Access is limited to the Epic management directory."
        )

    if start_line < 1:
        return f"Error: start_line must be at least 1, got {start_line}"
    if end_line < start_line:
        return f"Error: end_line ({end_line}) must be >= start_line ({start_line})"
    if not abs_path.exists():
        return f"Error: no such file or directory: {file_path}"
    if abs_path.is_dir():
        return f"Error: {file_path} is a directory."

    try:
        lines: list[str] = []
        with abs_path.open("r", encoding="utf-8") as handle:
            for i, line in enumerate(handle, 1):
                if i < start_line:
                    continue
                if i > end_line:
                    break
                lines.append(line)
        if not lines:
            return f"No lines found in range {start_line}-{end_line} in {file_path}"
        return "".join(lines)
    except Exception as e:
        return f"Error: {e}"


@tool(
    name="list_directory_epic",
    description=(
        "List files and directories inside the Epic management directory "
        "(project_root). "
        "Access is strictly limited to the Epic management directory — "
        "individual target repositories are NOT accessible via this tool."
    ),
)
def list_directory_epic(dir_path: str = ".") -> str:
    """List entries inside the Epic management directory.

    Args:
        dir_path: Path relative to the Epic management project_root
                  (default: project_root itself).

    Returns:
        Newline-separated list of entries, or an error message.
    """
    from tokuye.tools.strands_tools.utils import (
        FileValidationError,
        get_validated_relative_path,
    )

    root = _epic_mgmt_root()

    try:
        abs_path = get_validated_relative_path(root, dir_path)
    except FileValidationError:
        return (
            f"Error: Access denied to '{dir_path}'. "
            "Access is limited to the Epic management directory."
        )

    if not abs_path.exists():
        return f"Error: Directory '{dir_path}' does not exist."
    if not abs_path.is_dir():
        return f"Error: '{dir_path}' is not a directory."

    try:
        entries = sorted(
            abs_path.iterdir(),
            key=lambda e: (0 if e.is_dir() else 1, e.name),
        )
        names = [
            (e.name + "/" if e.is_dir() else e.name)
            for e in entries
        ]
        if not names:
            return f"Directory '{dir_path}' is empty."
        return "\n".join(names)
    except Exception as e:
        return f"Error: {e}"

# ---------------------------------------------------------------------------
# Project-level shared docs — tools for EpicManagerAgent
# ---------------------------------------------------------------------------
# These tools expose <project_root>/docs/ — a directory for project-wide
# reference documents (architecture notes, API specs, conventions, etc.)
# that are shared across all Epics.
# ---------------------------------------------------------------------------


@tool(
    name="list_project_docs",
    description=(
        "List files in the project-level shared docs directory "
        "(<project_root>/docs/). "
        "Returns file names, or a message if the directory does not exist or "
        "is empty."
    ),
)
def list_project_docs() -> str:
    """List files in <project_root>/docs/.

    Returns:
        Newline-separated list of file names, or an informational message.
    """
    root = _epic_mgmt_root()
    docs_dir = root / "docs"

    if not docs_dir.exists():
        return (
            "docs/ directory does not exist yet. "
            "Use write_project_doc to create the first document "
            "(the directory will be created automatically)."
        )
    if not docs_dir.is_dir():
        return "Error: <project_root>/docs exists but is not a directory."

    entries = sorted(f.name for f in docs_dir.iterdir() if f.is_file())
    if not entries:
        return "docs/ directory is empty."
    return "\n".join(entries)


@tool(
    name="read_project_doc",
    description=(
        "Read a file from the project-level shared docs directory "
        "(<project_root>/docs/<filename>). "
        "Use this to load project-wide reference documents such as "
        "architecture notes, API specs, or coding conventions. "
        "filename must be a simple name (e.g. 'architecture.md'); "
        "subdirectories are not allowed."
    ),
)
def read_project_doc(filename: str) -> str:
    """Read <project_root>/docs/<filename>.

    Args:
        filename: File name inside the docs/ directory (e.g. 'architecture.md').
                  Must not contain path separators.

    Returns:
        File contents as a string, or an error message.
    """
    if "/" in filename or "\\" in filename:
        return (
            f"Error: filename must not contain path separators. "
            f"Got: '{filename}'. Use a simple name like 'architecture.md'."
        )

    root = _epic_mgmt_root()
    docs_dir = root / "docs"
    target = (docs_dir / filename).resolve()

    # Safety: must stay inside docs/
    try:
        target.relative_to(docs_dir.resolve())
    except ValueError:
        return f"Error: '{filename}' is outside the docs directory."

    if not target.exists():
        return f"File not found: {target}"
    if target.is_dir():
        return f"Error: '{filename}' is a directory, not a file."

    return target.read_text(encoding="utf-8")


@tool(
    name="write_project_doc",
    description=(
        "Write a document to the project-level shared docs directory "
        "(<project_root>/docs/<filename>). "
        "Creates or overwrites docs/<filename>. "
        "Use this ONLY when creating a new file or when a full overwrite is "
        "explicitly required. "
        "For partial edits to an existing document (e.g. updating a section), "
        "use replace_exact_epic / insert_after_exact_epic / insert_before_exact_epic "
        "instead — they are safer and avoid accidental data loss. "
        "filename must be a simple name (e.g. 'architecture.md'); "
        "subdirectories are not allowed."
    ),
)
def write_project_doc(filename: str, content: str) -> str:
    """Write <project_root>/docs/<filename>.

    Args:
        filename: File name inside the docs/ directory (e.g. 'architecture.md').
                  Must not contain path separators.
        content: Full document content (Markdown or plain text).

    Returns:
        Confirmation message with file path, or an error message.
    """
    if "/" in filename or "\\" in filename:
        return (
            f"Error: filename must not contain path separators. "
            f"Got: '{filename}'. Use a simple name like 'architecture.md'."
        )

    root = _epic_mgmt_root()
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    target = (docs_dir / filename).resolve()

    # Safety: must stay inside docs/
    try:
        target.relative_to(docs_dir.resolve())
    except ValueError:
        return f"Error: '{filename}' is outside the docs directory."

    target.write_text(content, encoding="utf-8")
    logger.info("Wrote project doc: %s", target)
    return f"Document saved to: {target}"


# ---------------------------------------------------------------------------
# Partial-edit tools for Epic management directory (EpicManagerAgent)
# ---------------------------------------------------------------------------
# These tools allow safe, surgical edits to any file inside the Epic
# management directory (project_root) without overwriting the whole file.
#
# Typical workflow:
#   1. read_lines_epic  — copy the target block verbatim
#   2. replace_exact_epic / insert_after_exact_epic / insert_before_exact_epic
#
# Use write_epic_doc / write_project_doc only when creating a new file or
# when a full overwrite is explicitly required.
# ---------------------------------------------------------------------------


@tool(
    name="replace_exact_epic",
    description=(
        "Replace an exact block of text in a file inside the Epic management "
        "directory (project_root). "
        "`old_text` must match exactly one location in the file — "
        "fails with 'old_text not found' (0 matches) or "
        "'old_text matched multiple locations (N)' (N > 1 matches). "
        "Always use read_lines_epic to copy the target block verbatim before "
        "calling this tool. "
        "Prefer this over write_epic_doc / write_project_doc for partial edits "
        "to existing documents. "
        "Only UTF-8 encoded files are supported."
    ),
)
def replace_exact_epic(file_path: str, old_text: str, new_text: str) -> str:
    """Replace an exact block of text in a file inside the Epic management directory.

    Args:
        file_path: Path relative to the Epic management project_root.
        old_text: Exact text to find (must match exactly one location).
        new_text: Replacement text.

    Returns:
        Success message, or an error message.
    """
    from tokuye.tools.strands_tools.text_edit_tools import replace_exact_for

    return replace_exact_for(_epic_mgmt_root(), file_path, old_text, new_text)


@tool(
    name="insert_after_exact_epic",
    description=(
        "Insert new text immediately after an exact anchor block in a file "
        "inside the Epic management directory (project_root). "
        "`anchor_text` must match exactly one location — "
        "fails with 'anchor_text not found' (0 matches) or "
        "'anchor_text matched multiple locations (N)' (N > 1 matches). "
        "Always use read_lines_epic to copy the anchor verbatim before "
        "calling this tool. "
        "Prefer this over write_epic_doc / write_project_doc for partial edits "
        "to existing documents. "
        "Only UTF-8 encoded files are supported."
    ),
)
def insert_after_exact_epic(file_path: str, anchor_text: str, new_text: str) -> str:
    """Insert text immediately after an exact anchor block.

    Args:
        file_path: Path relative to the Epic management project_root.
        anchor_text: Exact text to locate (must match exactly one location).
        new_text: Text to insert after the anchor.

    Returns:
        Success message, or an error message.
    """
    from tokuye.tools.strands_tools.text_edit_tools import insert_after_exact_for

    return insert_after_exact_for(_epic_mgmt_root(), file_path, anchor_text, new_text)


@tool(
    name="insert_before_exact_epic",
    description=(
        "Insert new text immediately before an exact anchor block in a file "
        "inside the Epic management directory (project_root). "
        "`anchor_text` must match exactly one location — "
        "fails with 'anchor_text not found' (0 matches) or "
        "'anchor_text matched multiple locations (N)' (N > 1 matches). "
        "Always use read_lines_epic to copy the anchor verbatim before "
        "calling this tool. "
        "Prefer this over write_epic_doc / write_project_doc for partial edits "
        "to existing documents. "
        "Only UTF-8 encoded files are supported."
    ),
)
def insert_before_exact_epic(file_path: str, anchor_text: str, new_text: str) -> str:
    """Insert text immediately before an exact anchor block.

    Args:
        file_path: Path relative to the Epic management project_root.
        anchor_text: Exact text to locate (must match exactly one location).
        new_text: Text to insert before the anchor.

    Returns:
        Success message, or an error message.
    """
    from tokuye.tools.strands_tools.text_edit_tools import insert_before_exact_for

    return insert_before_exact_for(_epic_mgmt_root(), file_path, anchor_text, new_text)

