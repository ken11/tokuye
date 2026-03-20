import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

from git import Repo
from strands import tool
from tokuye.utils.config import settings
from tokuye.tools.strands_tools.utils import _is_ignored_by_git

logger = logging.getLogger(__name__)


def _extract_failed_hunks(diff: str) -> list[tuple[str, int]]:
    """Parse a unified diff string and return (file_path, hunk_start_line) for each hunk."""
    results = []
    current_file = None
    for line in diff.splitlines():
        file_match = re.match(r"^\+\+\+ b/(.+)$", line)
        if file_match:
            current_file = file_match.group(1)
        hunk_match = re.match(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@", line)
        if hunk_match and current_file is not None:
            results.append((current_file, int(hunk_match.group(1))))
    return results


def _build_context_hint(file_path: str, line: int, radius: int = 10) -> str:
    """Return a string showing lines around `line` (1-indexed) in `file_path`.
    Returns empty string if the file cannot be read."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        start = max(0, line - 1 - radius)
        end = min(len(lines), line - 1 + radius + 1)
        numbered = []
        for i, content in enumerate(lines[start:end], start=start + 1):
            numbered.append(f"  {i}: {content.rstrip()}")
        return f"Context around line {line} in {file_path}:\n" + "\n".join(numbered)
    except Exception:
        return ""


@tool(
    name="apply_patch",
    description="Apply a git diff patch to the repository. Accepts a string containing the diff in git format.",
)
def apply_patch(diff: str) -> str:
    """
    Apply a Git patch

    Args:
        diff: Diff string in Git format

    Returns:
        Patch application result message
    """
    try:
        return _apply_patch_with_fallbacks(diff)
    except Exception as e:
        return f"Error applying patch: {str(e)}"


def _validate_patch_format(diff: str) -> Tuple[bool, Optional[str]]:
    """
    Perform basic validation of patch format

    Args:
        diff: Patch string to validate

    Returns:
        (Validation result, Error message)
    """
    # Minimum patch format validation
    if not diff.strip():
        return False, "Empty patch content"

    # Check for diff --git line
    if not re.search(r"diff --git a/\S+ b/\S+", diff):
        return False, "Invalid patch format: missing 'diff --git' header"

    # Check for @@ line (hunk information)
    if not re.search(r"@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", diff):
        return False, "Invalid patch format: missing hunk header (@@ line)"

    return True, None


def _apply_patch_with_fallbacks(diff: str) -> str:
    """Apply patch using fallback logic"""
    # 1. Normalize line endings to LF
    diff_lf = diff.replace("\r\n", "\n")
    # 2. Add newline at end if missing
    if not diff_lf.endswith("\n"):
        diff_lf += "\n"

    tokuye_dir = settings.project_root / ".tokuye"
    tokuye_dir.mkdir(exist_ok=True)

    # Save patch file to .tokuye (LF normalized + newline at end)
    patch_file = tokuye_dir / "ai_patch.diff"
    patch_file.write_text(diff_lf, encoding="utf-8")

    # Validate patch format
    is_valid, error_msg = _validate_patch_format(diff_lf)
    if not is_valid:
        raise RuntimeError(f"Invalid patch format: {error_msg}")

    # Execute git apply with GitPython
    repo = Repo(settings.project_root)

    # Priority list of application methods
    # 1. Standard apply
    # 2. --recount option (recalculate line numbers)
    # 3. --ignore-whitespace option (ignore whitespace differences)
    # 4. Combination of --recount + --ignore-whitespace
    apply_strategies = [
        {"options": [], "description": "standard apply"},
        {"options": ["--recount"], "description": "with line recount"},
        {"options": ["--ignore-whitespace"], "description": "ignoring whitespace"},
        {
            "options": ["--recount", "--ignore-whitespace"],
            "description": "with line recount and ignoring whitespace",
        },
    ]

    errors: List[str] = []

    # Try each strategy in order
    for strategy in apply_strategies:
        options = strategy["options"]
        description = strategy["description"]

        try:
            logger.info(f"Attempting to apply patch {description}")
            if options:
                repo.git.apply(str(patch_file), *options)
            else:
                repo.git.apply(str(patch_file))

            return f"Patch applied successfully ({description})"

        except Exception as e:
            error_msg = f"git apply {' '.join(options)} failed: {str(e)}"
            logger.warning(error_msg)
            errors.append(error_msg)

    # If all strategies failed
    all_errors = "\n".join(errors)
    final_error = f"All patch application strategies failed:\n{all_errors}"
    logger.error(final_error)

    # Build context hints for failed hunks
    hints = []
    for file_path, hunk_line in _extract_failed_hunks(diff_lf):
        hint = _build_context_hint(file_path, hunk_line)
        if hint:
            hints.append(hint)

    if hints:
        final_error += "\n\nFile context at failed locations:\n" + "\n".join(hints)

    raise RuntimeError(final_error)