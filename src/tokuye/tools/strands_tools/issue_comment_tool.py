"""
GitHub Issue comment tool using the `gh` CLI.

Provides a tool to add a comment to an existing Issue.
Requires `gh` CLI to be installed and authenticated.
"""

import logging

from strands import tool

from tokuye.tools.strands_tools.gh_utils import run_gh as _run_gh

logger = logging.getLogger(__name__)


@tool(
    name="issue_add_comment",
    description=(
        "Add a comment to an existing GitHub Issue. "
        "IMPORTANT: Only call this when explicitly instructed by the user."
    ),
)
def issue_add_comment(issue_number: int, body: str) -> str:
    """Add a comment to an existing GitHub Issue.

    Args:
        issue_number: The issue number to comment on.
        body: The comment body text (markdown supported).

    Returns:
        Result message including the comment URL on success, or an error message.
    """
    try:
        result = _run_gh(["issue", "comment", str(issue_number), "--body", body])
        return f"Comment added to Issue #{issue_number}.\n{result}".strip()
    except Exception as e:
        return f"Error adding comment to Issue #{issue_number}: {e}"
