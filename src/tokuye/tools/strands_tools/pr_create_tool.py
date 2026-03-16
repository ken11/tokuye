"""
GitHub Pull Request creation tool using the `gh` CLI.

Provides a single tool to open a pull request from the current branch.
Requires `gh` CLI to be installed and authenticated.
"""

import json
import logging

from strands import tool

from tokuye.tools.strands_tools.gh_utils import run_gh as _run_gh

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Submit Pull Request
# ---------------------------------------------------------------------------


@tool(
    name="submit_pull_request",
    description=(
        "Create a new pull request on GitHub from the current branch. "
        "Generates an appropriate title and description based on the changes, "
        "then opens the PR via the gh CLI. "
        "Defaults to draft mode to prevent accidental publication. "
        "IMPORTANT: Only call this when explicitly instructed by the user."
    ),
)
def submit_pull_request(
    title: str,
    body: str,
    base: str = "",
    draft: bool = True,
) -> str:
    """
    Create a pull request on GitHub.

    Args:
        title: The pull request title.
        body: The pull request description (markdown supported).
        base: Target branch to merge into. Defaults to the repository's default branch.
        draft: Whether to open as a draft PR. Defaults to True.

    Returns:
        Result message including the PR URL.
    """
    try:
        args = [
            "pr", "create",
            "--title", title,
            "--body", body,
        ]

        if base.strip():
            args.extend(["--base", base.strip()])

        if draft:
            args.append("--draft")

        raw = _run_gh(args)

        # gh pr create returns the PR URL as the last line of stdout
        url = raw.strip().splitlines()[-1] if raw.strip() else "(URL not available)"

        draft_label = " [DRAFT]" if draft else ""
        base_label = f" → {base}" if base.strip() else ""

        return (
            f"Pull request created successfully{draft_label}{base_label}.\n"
            f"  Title: {title}\n"
            f"  URL: {url}\n"
            f"\nDescription:\n{body}"
        )

    except Exception as e:
        return f"Error creating pull request: {e}"
