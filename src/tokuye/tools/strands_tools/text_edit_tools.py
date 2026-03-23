"""
Structured text edit tools for safe, LLM-friendly file editing.

These tools are designed for the Developer node in state_machine_mode,
where weaker models (e.g. Devstral) are used and unified-diff generation
is error-prone.

Each tool operates on exact string matching rather than line-number offsets,
so the model only needs to copy a verbatim block from the file — no patch
format, no hunk headers, no line counting.

Failure messages are intentionally specific to aid retry:
  - "old_text not found"
  - "multiple matches (N)"
  - "anchor not found"
  - "anchor matched multiple locations (N)"
"""

import logging
from pathlib import Path
from typing import Tuple

from strands import tool
from tokuye.tools.strands_tools.utils import (
    FileValidationError,
    _is_ignored_by_git,
    get_validated_relative_path,
)
from tokuye.utils.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_path(file_path: str) -> Path:
    """Validate path is within root and not gitignored. Returns abs_path or raises."""
    root_dir = settings.project_root
    try:
        abs_path = get_validated_relative_path(root_dir, file_path)
    except FileValidationError:
        raise FileValidationError(
            f"Access denied to file_path: {file_path}. "
            "Permission granted exclusively to the current working directory"
        )
    if _is_ignored_by_git(root_dir, abs_path):
        raise FileValidationError(
            f"Access denied to file_path: {file_path}. "
            "File is matched by .gitignore patterns."
        )
    return abs_path


def _read_validated_file(file_path: str) -> Tuple[Path, str]:
    """Validate path and read file content. Returns (abs_path, content) or raises."""
    abs_path = _validate_path(file_path)
    if not abs_path.exists():
        raise FileNotFoundError(f"file not found: {file_path}")
    if abs_path.is_dir():
        raise IsADirectoryError(f"{file_path} is a directory")
    content = abs_path.read_text(encoding="utf-8")
    return abs_path, content


def _locate_exact(content: str, search_text: str, label: str) -> Tuple[int, str]:
    """
    Find search_text in content, enforcing exactly one match.

    Returns (start_index, "") on success.
    Returns (-1, error_message) on failure.

    label is used in error messages ("old_text" or "anchor_text").
    """
    if not search_text:
        return -1, (
            f"Error: {label} must not be empty"
        )

    count = content.count(search_text)
    if count == 0:
        return -1, (
            f"Error: {label} not found. "
            "Re-read the target block with read_lines and copy it verbatim. "
            "Whitespace or line ending differences may be the cause."
        )
    if count > 1:
        return -1, (
            f"Error: {label} matched multiple locations ({count}). "
            "Extend the text to include more surrounding lines to make it unambiguous."
        )

    return content.index(search_text), ""


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool(
    name="replace_exact",
    description=(
        "Replace an exact block of text in a file with new text. "
        "`old_text` must match exactly one location in the file — "
        "fails with 'old_text not found' if zero matches, "
        "'multiple matches (N)' if more than one. "
        "Use read_lines to copy the target block verbatim before calling this tool."
    ),
)
def replace_exact(file_path: str, old_text: str, new_text: str) -> str:
    """
    Replace an exact block of text in a file.

    Args:
        file_path: Relative path of the file to edit
        old_text: Exact text to find (must match exactly one location)
        new_text: Replacement text

    Returns:
        Success or failure message
    """
    try:
        abs_path, content = _read_validated_file(file_path)
    except FileValidationError as e:
        return f"Error: {e}"
    except (FileNotFoundError, IsADirectoryError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"

    idx, err = _locate_exact(content, old_text, "old_text")
    if err:
        return err

    new_content = content[:idx] + new_text + content[idx + len(old_text):]
    try:
        abs_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"

    return f"replace_exact applied successfully to {file_path}"


@tool(
    name="insert_after_exact",
    description=(
        "Insert new text immediately after an exact anchor block in a file. "
        "`anchor_text` must match exactly one location — "
        "fails with 'anchor not found' or 'anchor matched multiple locations (N)'. "
        "Use read_lines to copy the anchor verbatim before calling this tool."
    ),
)
def insert_after_exact(file_path: str, anchor_text: str, new_text: str) -> str:
    """
    Insert text immediately after an exact anchor block.

    Args:
        file_path: Relative path of the file to edit
        anchor_text: Exact text to locate (must match exactly one location)
        new_text: Text to insert after the anchor

    Returns:
        Success or failure message
    """
    try:
        abs_path, content = _read_validated_file(file_path)
    except FileValidationError as e:
        return f"Error: {e}"
    except (FileNotFoundError, IsADirectoryError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"

    idx, err = _locate_exact(content, anchor_text, "anchor_text")
    if err:
        return err

    insert_pos = idx + len(anchor_text)
    new_content = content[:insert_pos] + new_text + content[insert_pos:]
    try:
        abs_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"

    return f"insert_after_exact applied successfully to {file_path}"


@tool(
    name="insert_before_exact",
    description=(
        "Insert new text immediately before an exact anchor block in a file. "
        "`anchor_text` must match exactly one location — "
        "fails with 'anchor not found' or 'anchor matched multiple locations (N)'. "
        "Use read_lines to copy the anchor verbatim before calling this tool."
    ),
)
def insert_before_exact(file_path: str, anchor_text: str, new_text: str) -> str:
    """
    Insert text immediately before an exact anchor block.

    Args:
        file_path: Relative path of the file to edit
        anchor_text: Exact text to locate (must match exactly one location)
        new_text: Text to insert before the anchor

    Returns:
        Success or failure message
    """
    try:
        abs_path, content = _read_validated_file(file_path)
    except FileValidationError as e:
        return f"Error: {e}"
    except (FileNotFoundError, IsADirectoryError) as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"

    idx, err = _locate_exact(content, anchor_text, "anchor_text")
    if err:
        return err

    new_content = content[:idx] + new_text + content[idx:]
    try:
        abs_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return f"Error writing file: {e}"

    return f"insert_before_exact applied successfully to {file_path}"
