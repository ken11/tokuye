"""
GitHub Issue tools using the `gh` CLI.

Provides tools to list issues, view issue details, and read issue comments.
Requires `gh` CLI to be installed and authenticated.
"""

import json
import logging

from strands import tool

from tokuye.tools.strands_tools.gh_utils import run_gh as _run_gh

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Issue List
# ---------------------------------------------------------------------------


@tool(
    name="issue_list",
    description=(
        "List issues in the current repository. "
        "Returns issue number, title, author, labels, and creation date. "
        "Supports filtering by state and labels."
    ),
)
def issue_list(
    state: str = "open",
    limit: int = 30,
    labels: str = "",
) -> str:
    """
    List issues in the current repository.

    Args:
        state: Issue state filter — "open", "closed", or "all". Defaults to "open".
        limit: Maximum number of issues to return. Defaults to 30.
        labels: Comma-separated label names to filter by (e.g. "bug,help wanted").
                Leave empty to skip label filtering.

    Returns:
        Formatted list of issues.
    """
    try:
        args = [
            "issue", "list",
            "--state", state,
            "--limit", str(limit),
            "--json",
            "number,title,author,url,labels,assignees,createdAt,updatedAt,state",
        ]

        if labels.strip():
            args.extend(["--label", labels.strip()])

        raw = _run_gh(args)
        issues = json.loads(raw)

        if not issues:
            label_note = f" with label(s) '{labels}'" if labels.strip() else ""
            return f"No {state} issues found{label_note}."

        lines = [f"Found {len(issues)} {state} issue(s):\n"]
        for issue in issues:
            author = issue.get("author", {}).get("login", "unknown")
            label_names = [lb.get("name", "") for lb in issue.get("labels", [])]
            label_str = f"  Labels: {', '.join(label_names)}" if label_names else ""
            assignees = [a.get("login", "") for a in issue.get("assignees", [])]
            assignee_str = (
                f"  Assignees: {', '.join(assignees)}" if assignees else ""
            )
            lines.append(
                f"  #{issue['number']}  {issue['title']}\n"
                f"    Author: {author} | State: {issue.get('state', 'N/A')}\n"
                f"    Created: {issue.get('createdAt', 'N/A')}"
                f" | Updated: {issue.get('updatedAt', 'N/A')}\n"
                + (f"    {label_str}\n" if label_str else "")
                + (f"    {assignee_str}\n" if assignee_str else "")
                + f"    URL: {issue['url']}"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"Error listing issues: {e}"


# ---------------------------------------------------------------------------
# 2. Issue View
# ---------------------------------------------------------------------------


@tool(
    name="issue_view",
    description=(
        "Get detailed information about a specific issue by number. "
        "Returns title, body, author, labels, assignees, and state. "
        "Use this to understand the full context of an issue."
    ),
)
def issue_view(issue_number: int) -> str:
    """
    View detailed information about an issue.

    Args:
        issue_number: The issue number.

    Returns:
        Formatted issue details.
    """
    try:
        raw = _run_gh([
            "issue", "view", str(issue_number),
            "--json",
            "number,title,body,author,state,labels,assignees,"
            "milestone,createdAt,updatedAt,url,comments",
        ])

        issue = json.loads(raw)
        author = issue.get("author", {}).get("login", "unknown")

        lines = [
            f"Issue #{issue['number']}: {issue['title']}",
            f"State: {issue.get('state', 'N/A')}",
            f"Author: {author}",
            f"Created: {issue.get('createdAt', 'N/A')}"
            f" | Updated: {issue.get('updatedAt', 'N/A')}",
            f"URL: {issue['url']}",
        ]

        # Labels
        labels = issue.get("labels", [])
        if labels:
            label_names = [lb.get("name", "") for lb in labels]
            lines.append(f"Labels: {', '.join(label_names)}")

        # Assignees
        assignees = issue.get("assignees", [])
        if assignees:
            assignee_names = [a.get("login", "") for a in assignees]
            lines.append(f"Assignees: {', '.join(assignee_names)}")

        # Milestone
        milestone = issue.get("milestone")
        if milestone:
            lines.append(f"Milestone: {milestone.get('title', 'N/A')}")

        # Body
        body = issue.get("body", "").strip()
        if body:
            lines.append(f"\n--- Description ---\n{body}")
        else:
            lines.append("\n--- Description ---\n(no description)")

        # Comment count summary (full content via issue_get_comments)
        comments = issue.get("comments", [])
        if comments:
            lines.append(
                f"\n--- Comments ({len(comments)}) ---"
                "\n(Use issue_get_comments to read full comment content)"
            )
        else:
            lines.append("\n--- Comments ---\n(no comments)")

        return "\n".join(lines)

    except Exception as e:
        return f"Error viewing issue #{issue_number}: {e}"


# ---------------------------------------------------------------------------
# 3. Issue Get Comments
# ---------------------------------------------------------------------------


@tool(
    name="issue_get_comments",
    description=(
        "Get all comments on a specific issue by number. "
        "Returns each comment with author, timestamp, and full body text. "
        "Use this to read the full discussion history of an issue."
    ),
)
def issue_get_comments(issue_number: int) -> str:
    """
    Retrieve all comments on an issue.

    Args:
        issue_number: The issue number.

    Returns:
        Formatted string of all comments with author, timestamp, and body.
    """
    try:
        raw = _run_gh([
            "api",
            f"repos/{{owner}}/{{repo}}/issues/{issue_number}/comments",
            "--paginate",
        ])
        comments = json.loads(raw)

        if not comments:
            return f"Issue #{issue_number} has no comments."

        lines = [f"Comments on Issue #{issue_number} ({len(comments)} total):\n"]
        for i, c in enumerate(comments, start=1):
            author = c.get("user", {}).get("login", "unknown")
            created_at = c.get("created_at", "N/A")
            updated_at = c.get("updated_at", "N/A")
            body = c.get("body", "").strip()
            lines.append(
                f"[{i}] {author}  {created_at}"
                + (f" (updated: {updated_at})" if updated_at != created_at else "")
            )
            lines.append(body)
            lines.append("")  # blank line between comments

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting comments for issue #{issue_number}: {e}"
