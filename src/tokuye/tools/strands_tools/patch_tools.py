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


def _sanitize_patch(diff: str) -> str:
    """Repair common structural defects in AI-generated unified diffs.

    Two classes of defects are fixed:

    1. **Invalid ``index`` lines** – Git requires both object IDs in an
       ``index <old>..<new>`` line to be valid hex strings.  Devstral
       sometimes emits placeholder values that contain non-hex characters
       (e.g. ``abcdefg``).  Such lines are removed entirely; ``git apply``
       does not require them.

       Only lines in the per-file header region (between ``diff --git``
       and the first ``@@`` of each file) are examined.  This prevents
       false-positive removal of hunk-body lines that happen to match the
       ``index X..Y`` pattern (e.g. content in Markdown or config files).

    2. **Incorrect hunk-header line counts** – The ``@@ -a,b +c,d @@``
       header must declare the exact number of old-side (``b``) and
       new-side (``d``) lines present in the hunk body.  Devstral
       frequently miscounts these values.  This function recomputes both
       counts from the actual hunk body and rewrites the header in-place.

    The function is intentionally conservative: it only touches lines that
    are structurally wrong and leaves everything else unchanged.
    """
    lines = diff.splitlines(keepends=True)

    # ------------------------------------------------------------------ #
    # Pass 1: strip invalid ``index`` lines                               #
    # ------------------------------------------------------------------ #
    # ``index`` metadata lines only appear in the per-file header region,
    # i.e. after a ``diff --git`` line and before the first ``@@`` hunk
    # header of that file.  We track this region with ``in_file_header``
    # so that hunk-body content is never inspected.
    #
    # _INDEX_RE uses \S+ (not [0-9a-fA-F.]+) so that OIDs containing
    # non-hex characters (e.g. "abcdefg") are still captured and then
    # rejected by _valid_oid().
    _VALID_OID = re.compile(r"^[0-9a-f]+$")
    _INDEX_RE = re.compile(r"^index (\S+)\.\.(\S+)(?:\s+\d+)?$")

    def _valid_oid(oid: str) -> bool:
        # Allow all-zeros placeholder used for new/deleted files.
        # Reject anything containing non-hex characters.
        return bool(_VALID_OID.match(oid.lower()))

    filtered: list[str] = []
    in_file_header = False  # True between "diff --git" and first "@@" of a file

    for line in lines:
        stripped = line.rstrip("\n")

        if stripped.startswith("diff --git "):
            in_file_header = True
            filtered.append(line)
            continue

        if stripped.startswith("@@"):
            in_file_header = False
            filtered.append(line)
            continue

        if in_file_header:
            m = _INDEX_RE.match(stripped)
            if m:
                old_oid, new_oid = m.group(1), m.group(2)
                if _valid_oid(old_oid) and _valid_oid(new_oid):
                    filtered.append(line)
                else:
                    logger.debug(
                        "_sanitize_patch: removed invalid index line: %r", stripped
                    )
                continue  # handled (kept or dropped)

        filtered.append(line)

    # ------------------------------------------------------------------ #
    # Pass 2: recompute hunk-header line counts                           #
    # ------------------------------------------------------------------ #
    _HUNK_RE = re.compile(
        r"^(@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@)([ \t].*)?\n?$"
    )

    def _hunk_part(start: str, count: int) -> str:
        """Format one side of a hunk header (e.g. ``10,3`` or ``10``).

        Rules (matching git's own output):
        - count == 0  → ``<start>,0``  (must keep the explicit ,0)
        - count == 1  → ``<start>``    (,1 is omitted by convention)
        - count >= 2  → ``<start>,<count>``
        """
        if count == 0:
            return f"{start},0"
        if count == 1:
            return start
        return f"{start},{count}"

    out: list[str] = []
    i = 0
    while i < len(filtered):
        line = filtered[i]
        m = _HUNK_RE.match(line)
        if not m:
            out.append(line)
            i += 1
            continue

        old_start = m.group(2)
        new_start = m.group(3)
        suffix = m.group(4) or ""  # text after the closing @@

        # Collect hunk body lines (everything until the next hunk/file header)
        i += 1
        body: list[str] = []
        while i < len(filtered):
            bl = filtered[i]
            if (
                bl.startswith("@@")
                or bl.startswith("diff ")
                or bl.startswith("--- ")
                or bl.startswith("+++ ")
            ):
                break
            body.append(bl)
            i += 1

        # Count old-side (context + removal) and new-side (context + addition) lines
        old_count = sum(1 for bl in body if bl.startswith(" ") or bl.startswith("-"))
        new_count = sum(1 for bl in body if bl.startswith(" ") or bl.startswith("+"))

        # Rebuild header with corrected counts
        new_header = (
            f"@@ -{_hunk_part(old_start, old_count)}"
            f" +{_hunk_part(new_start, new_count)}"
            f" @@{suffix}\n"
        )

        if new_header != line:
            logger.debug(
                "_sanitize_patch: rewrote hunk header %r → %r",
                line.rstrip(),
                new_header.rstrip(),
            )

        out.append(new_header)
        out.extend(body)

    return "".join(out)


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
    # 3. Sanitize AI-generated patch defects (invalid index lines, wrong hunk counts)
    diff_lf = _sanitize_patch(diff_lf)

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


# ---------------------------------------------------------------------------
# Internal _for(root) helper — used by make_epic_worker_tools
# ---------------------------------------------------------------------------

def apply_patch_for(root: Path, diff: str) -> str:
    """Apply a git diff patch to a specific repository root.

    Identical to apply_patch but uses *root* instead of settings.project_root.

    Args:
        root: Absolute path to the target repository root.
        diff: Diff string in Git format.

    Returns:
        Patch application result message.
    """
    try:
        # Normalize line endings
        diff_lf = diff.replace("\r\n", "\n")
        if not diff_lf.endswith("\n"):
            diff_lf += "\n"
        diff_lf = _sanitize_patch(diff_lf)

        tokuye_dir = root / ".tokuye"
        tokuye_dir.mkdir(exist_ok=True)

        patch_file = tokuye_dir / "ai_patch.diff"
        patch_file.write_text(diff_lf, encoding="utf-8")

        is_valid, error_msg = _validate_patch_format(diff_lf)
        if not is_valid:
            raise RuntimeError(f"Invalid patch format: {error_msg}")

        repo = Repo(root)

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
        for strategy in apply_strategies:
            options = strategy["options"]
            description = strategy["description"]
            try:
                if options:
                    repo.git.apply(str(patch_file), *options)
                else:
                    repo.git.apply(str(patch_file))
                return f"Patch applied successfully ({description})"
            except Exception as e:
                errors.append(f"git apply {' '.join(options)} failed: {str(e)}")

        all_errors = "\n".join(errors)
        final_error = f"All patch application strategies failed:\n{all_errors}"

        hints = []
        for file_path, hunk_line in _extract_failed_hunks(diff_lf):
            hint = _build_context_hint(file_path, hunk_line)
            if hint:
                hints.append(hint)
        if hints:
            final_error += "\n\nFile context at failed locations:\n" + "\n".join(hints)

        raise RuntimeError(final_error)
    except Exception as e:
        return f"Error applying patch: {str(e)}"
