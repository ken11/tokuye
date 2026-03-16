"""
GitHub Pull Request review tools using the `gh` CLI.

These tools enable listing, viewing, diffing, reviewing, and reading comments on pull requests
directly from the agent, without requiring GitHub MCP Server.
Requires `gh` CLI to be installed and authenticated.
"""

import json
import logging
from typing import Optional

from strands import tool
from tokuye.tools.strands_tools.gh_utils import run_gh as _run_gh

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. PR List
# ---------------------------------------------------------------------------


@tool(
    name="pr_list",
    description=(
        "List open pull requests in the current repository. "
        "Returns PR number, title, author, branch names, and creation date. "
        "Use this to discover which PRs are available for review."
    ),
)
def pr_list(state: str = "open", limit: int = 30) -> str:
    """
    List pull requests in the current repository.

    Args:
        state: PR state filter — "open", "closed", "merged", or "all". Defaults to "open".
        limit: Maximum number of PRs to return. Defaults to 30.

    Returns:
        Formatted list of pull requests.
    """
    try:
        raw = _run_gh([
            "pr", "list",
            "--state", state,
            "--limit", str(limit),
            "--json",
            "number,title,author,url,headRefName,baseRefName,createdAt,isDraft",
        ])

        prs = json.loads(raw)
        if not prs:
            return f"No {state} pull requests found."

        lines = [f"Found {len(prs)} {state} PR(s):\n"]
        for pr in prs:
            draft = " [DRAFT]" if pr.get("isDraft") else ""
            author = pr.get("author", {}).get("login", "unknown")
            lines.append(
                f"  #{pr['number']}{draft}  {pr['title']}\n"
                f"    Author: {author} | {pr['headRefName']} → {pr['baseRefName']}\n"
                f"    Created: {pr['createdAt']}\n"
                f"    URL: {pr['url']}"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"Error listing PRs: {e}"


# ---------------------------------------------------------------------------
# 2. PR View
# ---------------------------------------------------------------------------


@tool(
    name="pr_view",
    description=(
        "Get detailed information about a specific pull request by number. "
        "Returns title, body, author, changed files, review status, and comments. "
        "Use this to understand what a PR is about before reviewing."
    ),
)
def pr_view(pr_number: int) -> str:
    """
    View detailed information about a pull request.

    Args:
        pr_number: The pull request number.

    Returns:
        Formatted PR details.
    """
    try:
        raw = _run_gh([
            "pr", "view", str(pr_number),
            "--json",
            "number,title,body,author,state,baseRefName,headRefName,"
            "additions,deletions,changedFiles,files,reviews,comments,"
            "reviewRequests,labels,milestone,createdAt,updatedAt,url,isDraft",
        ])

        pr = json.loads(raw)
        author = pr.get("author", {}).get("login", "unknown")
        draft = " [DRAFT]" if pr.get("isDraft") else ""

        lines = [
            f"PR #{pr['number']}{draft}: {pr['title']}",
            f"State: {pr['state']}",
            f"Author: {author}",
            f"Branch: {pr['headRefName']} → {pr['baseRefName']}",
            f"Changes: +{pr.get('additions', 0)} / -{pr.get('deletions', 0)}"
            f" across {pr.get('changedFiles', 0)} file(s)",
            f"Created: {pr.get('createdAt', 'N/A')}"
            f" | Updated: {pr.get('updatedAt', 'N/A')}",
            f"URL: {pr['url']}",
        ]

        # Labels
        labels = pr.get("labels", [])
        if labels:
            label_names = [lb.get("name", "") for lb in labels]
            lines.append(f"Labels: {', '.join(label_names)}")

        # Body
        body = pr.get("body", "").strip()
        if body:
            lines.append(f"\n--- Description ---\n{body}")
        else:
            lines.append("\n--- Description ---\n(no description)")

        # Changed files
        files = pr.get("files", [])
        if files:
            lines.append(f"\n--- Changed Files ({len(files)}) ---")
            for f in files:
                lines.append(
                    f"  {f.get('path', 'unknown')}"
                    f"  (+{f.get('additions', 0)} / -{f.get('deletions', 0)})"
                )

        # Reviews
        reviews = pr.get("reviews", [])
        if reviews:
            lines.append(f"\n--- Reviews ({len(reviews)}) ---")
            for r in reviews:
                reviewer = r.get("author", {}).get("login", "unknown")
                lines.append(
                    f"  {reviewer}: {r.get('state', 'UNKNOWN')}"
                    f"  {r.get('body', '')[:200]}"
                )

        # Comments
        comments = pr.get("comments", [])
        if comments:
            lines.append(f"\n--- Comments ({len(comments)}) ---")
            for c in comments:
                commenter = c.get("author", {}).get("login", "unknown")
                lines.append(f"  {commenter}: {c.get('body', '')[:200]}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error viewing PR #{pr_number}: {e}"


# ---------------------------------------------------------------------------
# 3. PR Diff
# ---------------------------------------------------------------------------


@tool(
    name="pr_diff",
    description=(
        "Get the full diff of a pull request. "
        "Returns the unified diff output showing all code changes. "
        "Use this to review the actual code changes in a PR."
    ),
)
def pr_diff(pr_number: int) -> str:
    """
    Get the diff of a pull request.

    Args:
        pr_number: The pull request number.

    Returns:
        Unified diff string of the PR.
    """
    try:
        diff_output = _run_gh(["pr", "diff", str(pr_number)])

        if not diff_output.strip():
            return (
                f"PR #{pr_number} has no diff"
                " (possibly no changes or already merged)."
            )

        return f"Diff for PR #{pr_number}:\n\n{diff_output}"

    except Exception as e:
        return f"Error getting diff for PR #{pr_number}: {e}"


# ---------------------------------------------------------------------------
# 4. PR Review Comment (inline, line-level)
# ---------------------------------------------------------------------------


@tool(
    name="pr_review_comment",
    description=(
        "Submit a review with inline comments on specific lines of a pull request. "
        "Each comment targets a file path and line number in the diff. "
        "The review event can be COMMENT, APPROVE, or REQUEST_CHANGES. "
        "IMPORTANT: Only call this after the user has approved the review content."
    ),
)
def pr_review_comment(
    pr_number: int,
    body: str,
    event: str = "COMMENT",
    comments: Optional[str] = None,
) -> str:
    """
    Submit a review with optional inline comments on a pull request.

    This uses `gh api` to call the GitHub REST API directly, enabling
    line-level comments on the diff.

    Args:
        pr_number: The pull request number.
        body: Overall review body text.
        event: Review event type — "COMMENT", "APPROVE", or "REQUEST_CHANGES".
        comments: JSON string of inline comments array. Each element should have:
            - "path": file path relative to repo root
            - "line": line number in the diff (new file side)
            - "body": comment text
            Example: '[{"path":"src/main.py","line":42,"body":"Consider using a constant here."}]'
            If omitted, only the overall review body is submitted.

    Returns:
        Result message.
    """
    try:
        event = event.upper()
        if event not in ("COMMENT", "APPROVE", "REQUEST_CHANGES"):
            return (
                f"Error: Invalid event '{event}'. "
                "Must be COMMENT, APPROVE, or REQUEST_CHANGES."
            )

        # Build the API request body
        review_payload: dict = {
            "body": body,
            "event": event,
        }

        if comments:
            try:
                parsed_comments = json.loads(comments)
                if not isinstance(parsed_comments, list):
                    return "Error: 'comments' must be a JSON array."

                # Validate each comment has required fields
                for i, c in enumerate(parsed_comments):
                    if not isinstance(c, dict):
                        return f"Error: Comment at index {i} is not an object."
                    missing = [
                        k for k in ("path", "line", "body") if k not in c
                    ]
                    if missing:
                        return (
                            f"Error: Comment at index {i} is missing fields: "
                            f"{', '.join(missing)}"
                        )

                # Convert to GitHub API format
                api_comments = []
                for c in parsed_comments:
                    api_comment = {
                        "path": c["path"],
                        "line": c["line"],
                        "body": c["body"],
                    }
                    if "side" in c:
                        api_comment["side"] = c["side"]
                    api_comments.append(api_comment)

                review_payload["comments"] = api_comments

            except json.JSONDecodeError as e:
                return f"Error: Failed to parse 'comments' JSON: {e}"

        # Submit via gh api with stdin input for proper JSON support
        request_json = json.dumps(review_payload)
        logger.info(
            "Submitting review for PR #%d: event=%s, comments=%d",
            pr_number,
            event,
            len(review_payload.get("comments", [])),
        )

        raw_output = _run_gh(
            [
                "api",
                f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews",
                "--method", "POST",
                "--input", "-",
            ],
            stdin_input=request_json,
        )

        # Parse response
        try:
            response = json.loads(raw_output)
            review_id = response.get("id", "unknown")
            html_url = response.get("html_url", "")
            return (
                f"Review submitted successfully for PR #{pr_number}.\n"
                f"  Event: {event}\n"
                f"  Review ID: {review_id}\n"
                f"  Inline comments: "
                f"{len(review_payload.get('comments', []))}\n"
                f"  URL: {html_url}"
            )
        except json.JSONDecodeError:
            return (
                f"Review submitted for PR #{pr_number} (event: {event}). "
                f"Raw response:\n{raw_output[:500]}"
            )

    except Exception as e:
        return f"Error submitting review for PR #{pr_number}: {e}"


# ---------------------------------------------------------------------------
# 5. PR Review Submit (simple approve / request changes / comment)
# ---------------------------------------------------------------------------


@tool(
    name="pr_review_submit",
    description=(
        "Submit a simple review verdict on a pull request: approve, "
        "request-changes, or comment. "
        "Use this for a straightforward review without inline comments. "
        "For inline line-level comments, use pr_review_comment instead. "
        "IMPORTANT: Only call this after the user has approved the review content."
    ),
)
def pr_review_submit(
    pr_number: int,
    event: str,
    body: str = "",
) -> str:
    """
    Submit a simple review on a pull request.

    Args:
        pr_number: The pull request number.
        event: Review type — "approve", "request-changes", or "comment".
        body: Review comment body. Required for "request-changes" and "comment".

    Returns:
        Result message.
    """
    try:
        event = event.lower().replace("_", "-")
        valid_events = {"approve", "request-changes", "comment"}
        if event not in valid_events:
            return (
                f"Error: Invalid event '{event}'. "
                f"Must be one of: {', '.join(sorted(valid_events))}"
            )

        if event in ("request-changes", "comment") and not body.strip():
            return f"Error: 'body' is required for '{event}' reviews."

        args = ["pr", "review", str(pr_number), f"--{event}"]
        if body.strip():
            args.extend(["--body", body])

        output = _run_gh(args)

        return (
            f"Review submitted for PR #{pr_number}.\n"
            f"  Event: {event}\n"
            f"  Body: {body[:200]}{'...' if len(body) > 200 else ''}\n"
            f"{output}"
        )

    except Exception as e:
        return f"Error submitting review for PR #{pr_number}: {e}"


# ---------------------------------------------------------------------------
# 6. PR Get Comments (read all comments on a PR)
# ---------------------------------------------------------------------------


@tool(
    name="pr_get_comments",
    description=(
        "Get all comments on a specific pull request by number. "
        "Returns both general issue-level comments and inline review comments "
        "(diff-level comments with file path and line number). "
        "Use this to review the existing discussion history before adding a new review."
    ),
)
def pr_get_comments(pr_number: int) -> str:
    """
    Retrieve all comments on a pull request.

    Fetches two types of comments:
    - Issue comments: general conversation on the PR thread.
    - Review comments: inline diff comments tied to a specific file and line.

    Args:
        pr_number: The pull request number.

    Returns:
        Formatted string of all comments with author, timestamp, and body.
    """
    try:
        # --- Issue-level comments (general PR thread) ---
        raw_issue = _run_gh([
            "api",
            f"repos/{{owner}}/{{repo}}/issues/{pr_number}/comments",
            "--paginate",
        ])
        issue_comments = json.loads(raw_issue)

        # --- Review comments (inline diff comments) ---
        raw_review = _run_gh([
            "api",
            f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/comments",
            "--paginate",
        ])
        review_comments = json.loads(raw_review)

        if not issue_comments and not review_comments:
            return f"PR #{pr_number} has no comments."

        lines = [f"Comments on PR #{pr_number}:"]

        if issue_comments:
            lines.append(f"\n--- General Comments ({len(issue_comments)}) ---")
            for c in issue_comments:
                author = c.get("user", {}).get("login", "unknown")
                created_at = c.get("created_at", "N/A")
                updated_at = c.get("updated_at", "N/A")
                body = c.get("body", "").strip()
                lines.append(
                    f"\n[{author}] {created_at}"
                    + (f" (updated: {updated_at})" if updated_at != created_at else "")
                )
                lines.append(body)

        if review_comments:
            lines.append(f"\n--- Inline Review Comments ({len(review_comments)}) ---")
            for c in review_comments:
                author = c.get("user", {}).get("login", "unknown")
                created_at = c.get("created_at", "N/A")
                updated_at = c.get("updated_at", "N/A")
                path = c.get("path", "unknown")
                line = c.get("line") or c.get("original_line", "N/A")
                diff_hunk = c.get("diff_hunk", "")
                body = c.get("body", "").strip()
                lines.append(
                    f"\n[{author}] {created_at}"
                    + (f" (updated: {updated_at})" if updated_at != created_at else "")
                )
                lines.append(f"  File: {path}  Line: {line}")
                if diff_hunk:
                    # Show only the last few lines of the hunk for context
                    hunk_lines = diff_hunk.splitlines()
                    snippet = (
                        "\n".join(hunk_lines[-5:])
                        if len(hunk_lines) > 5
                        else diff_hunk
                    )
                    lines.append(f"  Diff context:\n{snippet}")
                lines.append(body)

        return "\n".join(lines)

    except Exception as e:
        return f"Error getting comments for PR #{pr_number}: {e}"
