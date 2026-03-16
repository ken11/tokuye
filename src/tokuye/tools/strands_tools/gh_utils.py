"""
Shared utility for running `gh` CLI commands.

Imported by pr_review_tools, pr_create_tool, and issue_tools to avoid
duplicating the subprocess wrapper.
"""

import logging
import subprocess
from typing import Optional

from tokuye.utils.config import settings

logger = logging.getLogger(__name__)


def run_gh(
    args: list[str],
    *,
    stdin_input: Optional[str] = None,
    max_output_chars: int = 80_000,
) -> str:
    """
    Run a `gh` CLI command and return stdout.

    Args:
        args: Arguments to pass to `gh` (e.g. ["pr", "list"]).
        stdin_input: Optional string to feed to stdin.
        max_output_chars: Truncate stdout beyond this limit to avoid token explosion.

    Returns:
        stdout string from the command.

    Raises:
        RuntimeError: If `gh` is not found or the command fails.
    """
    cmd = ["gh"] + args
    logger.info("Running: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            cwd=settings.project_root,
            input=stdin_input,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "gh CLI is not installed. "
            "Install it from https://cli.github.com/ and run `gh auth login`."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh command timed out after 60 seconds.")

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"gh command failed (exit {result.returncode}): {stderr}")

    output = result.stdout
    if len(output) > max_output_chars:
        output = (
            output[:max_output_chars]
            + f"\n\n... (truncated at {max_output_chars} chars)"
        )
    return output
