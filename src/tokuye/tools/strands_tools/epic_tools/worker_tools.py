"""
Epic Worker tool set factory for EpicWorkerAgent (v3 Epic Mode).

Exports:
  make_epic_worker_tools(repo_root: Path) -> list
      Returns a list of Strands @tool functions sandboxed to *repo_root*.
      All file, git, and GitHub operations are restricted to that directory.

Design
------
Each tool is a closure that captures *repo_root* at factory-call time.
Tool names are identical to the standard tool set so that the Worker's
system prompt (written for v1/v2) works without modification.

The factory delegates to the ``_for(root, ...)`` internal helpers that were
added to each standard tool module:
  - file_management._for  → read_lines, write_file, copy_file, …
  - text_edit_tools._for  → replace_exact, insert_after_exact, insert_before_exact
  - patch_tools._for      → apply_patch
  - git_tools._for        → create_branch, commit_changes, git_push
  - gh_utils.run_gh_for   → PR / Issue tools

Repo-analysis tools (repo_summarize, manage_code_index, search_code_repository,
generate_repo_description) already have ``_for(root)`` variants used by
EpicManagerAgent's repo_ops.py; the same helpers are reused here.

phase_tool (report_phase) is stateless and is included as-is.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from strands import tool

from tokuye.tools.strands_tools.file_management import (
    copy_file_for,
    create_new_file_for,
    file_delete_for,
    file_search_for,
    list_directory_for,
    move_file_for,
    read_lines_for,
    write_file_for,
)
from tokuye.tools.strands_tools.git_tools import (
    commit_changes_for,
    create_branch_for,
    git_push_for,
)
from tokuye.tools.strands_tools.gh_utils import run_gh_for
from tokuye.tools.strands_tools.patch_tools import apply_patch_for
from tokuye.tools.strands_tools.phase_tool import report_phase
from tokuye.tools.strands_tools.repo_description import (
    generate_repo_description_with_detail_control,
)
from tokuye.tools.strands_tools.repo_summary import render_xml, summarize_repo
from tokuye.tools.strands_tools.repo_summary_rag.code_index_admin_tool import (
    manage_code_index_for,
)
from tokuye.tools.strands_tools.repo_summary_rag.code_search_tool import (
    search_code_for,
)
from tokuye.tools.strands_tools.text_edit_tools import (
    insert_after_exact_for,
    insert_before_exact_for,
    replace_exact_for,
)
from tokuye.utils.config import settings

logger = logging.getLogger(__name__)


def make_epic_worker_tools(repo_root: Path) -> list:
    """Return a list of Strands tools sandboxed to *repo_root*.

    All file I/O, git operations, and GitHub CLI calls are restricted to
    *repo_root*.  The returned tools have the same names as the standard
    ``all_tools`` set so the Worker's system prompt needs no changes.

    Args:
        repo_root: Absolute path to the target repository root.

    Returns:
        List of Strands tool callables.
    """
    repo_root = repo_root.resolve()
    logger.info("make_epic_worker_tools: sandboxed to %s", repo_root)

    # ------------------------------------------------------------------
    # File management
    # ------------------------------------------------------------------

    @tool(
        name="read_lines",
        description=(
            "Read specific lines from a UTF-8 text file. "
            "Access is limited to the directory tree under `root_dir`; "
            "files matched by `.gitignore` are denied. "
            "Line numbers are 1-indexed and inclusive."
        ),
    )
    def _read_lines(file_path: str, start_line: int, end_line: int) -> str:
        return read_lines_for(repo_root, file_path, start_line, end_line)

    @tool(
        name="write_file",
        description=(
            "Write UTF-8 text to a file. "
            "Access is restricted to the directory tree under `root_dir`; "
            "files matched by `.gitignore` are denied. "
            "Use append=true to append; otherwise it OVERWRITES THE ENTIRE FILE — "
            "all existing content is lost. "
            "You MUST read the complete file with read_lines first, "
            "then pass the full updated content."
        ),
    )
    def _write_file(file_path: str, text: str, append: bool = False) -> str:
        return write_file_for(repo_root, file_path, text, append)

    @tool(
        name="file_search",
        description=(
            "Recursively search for files in a subdirectory whose names match "
            "a shell wildcard pattern (e.g., `*.py`). "
            "Obeys `.gitignore` exclusions."
        ),
    )
    def _file_search(pattern: str, dir_path: str = ".") -> str:
        return file_search_for(repo_root, pattern, dir_path)

    @tool(
        name="copy_file",
        description=(
            "Copy a file within the workspace. "
            "Access is restricted to the directory tree under `root_dir`; "
            "any path matched by `.gitignore` is denied."
        ),
    )
    def _copy_file(source_path: str, destination_path: str) -> str:
        return copy_file_for(repo_root, source_path, destination_path)

    @tool(
        name="move_file",
        description=(
            "Move (or rename) a file within the workspace. "
            "Source and destination must lie under `root_dir`, "
            "and `.gitignore` patterns are enforced."
        ),
    )
    def _move_file(source_path: str, destination_path: str) -> str:
        return move_file_for(repo_root, source_path, destination_path)

    @tool(
        name="file_delete",
        description=(
            "Delete a file from disk. "
            "Access is limited to the directory tree under `root_dir`; "
            "files matched by `.gitignore` are denied."
        ),
    )
    def _file_delete(file_path: str) -> str:
        return file_delete_for(repo_root, file_path)

    @tool(
        name="list_directory",
        description=(
            "List files and directories in the given folder, "
            "ignoring those that match `.gitignore`. "
            "Access is confined to the `root_dir` sandbox."
        ),
    )
    def _list_directory(dir_path: str = ".") -> str:
        return list_directory_for(repo_root, dir_path)

    @tool(
        name="create_new_file",
        description=(
            "Create a new file with the given content. "
            "Fails with 'Error: file already exists' if the file already exists — "
            "use this tool only for brand-new files. "
            "Access is restricted to the directory tree under `root_dir`; "
            "files matched by `.gitignore` are denied."
        ),
    )
    def _create_new_file(file_path: str, content: str) -> str:
        return create_new_file_for(repo_root, file_path, content)

    # ------------------------------------------------------------------
    # Text edit tools
    # ------------------------------------------------------------------

    @tool(
        name="replace_exact",
        description=(
            "Replace an exact block of text in a file with new text. "
            "`old_text` must match exactly one location in the file — "
            "fails with 'old_text not found' (0 matches) or "
            "'old_text matched multiple locations (N)' (N > 1 matches). "
            "Use read_lines to copy the target block verbatim before calling this tool. "
            "Only UTF-8 encoded files are supported."
        ),
    )
    def _replace_exact(file_path: str, old_text: str, new_text: str) -> str:
        return replace_exact_for(repo_root, file_path, old_text, new_text)

    @tool(
        name="insert_after_exact",
        description=(
            "Insert new text immediately after an exact anchor block in a file. "
            "`anchor_text` must match exactly one location — "
            "fails with 'anchor_text not found' (0 matches) or "
            "'anchor_text matched multiple locations (N)' (N > 1 matches). "
            "Use read_lines to copy the anchor verbatim before calling this tool. "
            "Only UTF-8 encoded files are supported."
        ),
    )
    def _insert_after_exact(file_path: str, anchor_text: str, new_text: str) -> str:
        return insert_after_exact_for(repo_root, file_path, anchor_text, new_text)

    @tool(
        name="insert_before_exact",
        description=(
            "Insert new text immediately before an exact anchor block in a file. "
            "`anchor_text` must match exactly one location — "
            "fails with 'anchor_text not found' (0 matches) or "
            "'anchor_text matched multiple locations (N)' (N > 1 matches). "
            "Use read_lines to copy the anchor verbatim before calling this tool. "
            "Only UTF-8 encoded files are supported."
        ),
    )
    def _insert_before_exact(file_path: str, anchor_text: str, new_text: str) -> str:
        return insert_before_exact_for(repo_root, file_path, anchor_text, new_text)

    # ------------------------------------------------------------------
    # Patch tool
    # ------------------------------------------------------------------

    @tool(
        name="apply_patch",
        description=(
            "Apply a git diff patch to the repository. "
            "Accepts a string containing the diff in git format."
        ),
    )
    def _apply_patch(diff: str) -> str:
        return apply_patch_for(repo_root, diff)

    # ------------------------------------------------------------------
    # Git tools
    # ------------------------------------------------------------------

    @tool(
        name="create_branch",
        description=(
            "Create a new branch if it doesn't exist, "
            "or create a new branch with suffix if it exists"
        ),
    )
    def _create_branch(name: str) -> str:
        return create_branch_for(repo_root, name, settings.pr_branch_prefix)

    @tool(
        name="commit_changes",
        description="Stage all changes and commit; returns list of committed files",
    )
    def _commit_changes(message: str) -> str:
        return commit_changes_for(repo_root, message)

    @tool(
        name="git_push",
        description=(
            "Push the current branch to the remote repository (always origin). "
            "Sets the upstream tracking branch automatically so new branches are "
            "handled correctly. "
            "Use this before submit_pull_request to ensure the branch exists on "
            "the remote. "
            "IMPORTANT: Only call this when explicitly instructed by the user."
        ),
    )
    def _git_push() -> str:
        return git_push_for(repo_root)

    # ------------------------------------------------------------------
    # Repo analysis tools (reuse _for helpers from repo_ops)
    # ------------------------------------------------------------------

    @tool(
        name="repo_summarize",
        description=(
            "Scan repository and return summary in XML"
        ),
    )
    def _repo_summarize(force_full_update: bool = False) -> str:
        summary = summarize_repo(repo_root, force_full_update)
        content = render_xml(summary)
        out_dir = repo_root / ".tokuye"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "repo-summary.xml"
        out_file.write_text(content, encoding="utf-8")
        return f"Written summary to {out_file}"

    @tool(
        name="generate_repo_description_tool",
        description=(
            "Generate project purpose and description using LLM based on "
            "repository summary and save to .tokuye/repo-description.md"
        ),
    )
    def _generate_repo_description() -> str:
        return generate_repo_description_with_detail_control(repo_root)

    @tool(
        name="manage_code_index",
        description=(
            "Manage FAISS index for code search. "
            "Supports build, update (differential), and rebuild operations."
        ),
    )
    def _manage_code_index(action: str = "update") -> str:
        return manage_code_index_for(repo_root, action)

    @tool(
        name="search_code_repository",
        description=(
            "Search for related code snippets in the repository using natural "
            "language or keywords. "
            "Returns matching code with file paths and line numbers."
        ),
    )
    def _search_code_repository(query: str, top_k: int = 3) -> str:
        return search_code_for(repo_root, query, top_k)

    # ------------------------------------------------------------------
    # GitHub CLI tools (PR / Issue) — cwd bound to repo_root
    # ------------------------------------------------------------------

    def _gh(args: list[str], *, stdin_input: Optional[str] = None) -> str:
        return run_gh_for(repo_root, args, stdin_input=stdin_input)

    @tool(
        name="pr_list",
        description=(
            "List open pull requests in the current repository. "
            "Returns PR number, title, author, branch names, and creation date. "
            "Use this to discover which PRs are available for review."
        ),
    )
    def _pr_list(state: str = "open", limit: int = 30) -> str:
        try:
            raw = _gh([
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

    @tool(
        name="pr_view",
        description=(
            "Get detailed information about a specific pull request by number. "
            "Returns title, body, author, changed files, review status, and comments. "
            "Use this to understand what a PR is about before reviewing."
        ),
    )
    def _pr_view(pr_number: int) -> str:
        try:
            raw = _gh([
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
            labels = pr.get("labels", [])
            if labels:
                lines.append(f"Labels: {', '.join(lb.get('name', '') for lb in labels)}")
            body = pr.get("body", "").strip()
            lines.append(f"\n--- Description ---\n{body}" if body else "\n--- Description ---\n(no description)")
            files = pr.get("files", [])
            if files:
                lines.append(f"\n--- Changed Files ({len(files)}) ---")
                for f in files:
                    lines.append(f"  {f.get('path', 'unknown')}  (+{f.get('additions', 0)} / -{f.get('deletions', 0)})")
            reviews = pr.get("reviews", [])
            if reviews:
                lines.append(f"\n--- Reviews ({len(reviews)}) ---")
                for r in reviews:
                    reviewer = r.get("author", {}).get("login", "unknown")
                    lines.append(f"  {reviewer}: {r.get('state', 'UNKNOWN')}  {r.get('body', '')[:200]}")
            comments = pr.get("comments", [])
            if comments:
                lines.append(f"\n--- Comments ({len(comments)}) ---")
                for c in comments:
                    commenter = c.get("author", {}).get("login", "unknown")
                    lines.append(f"  {commenter}: {c.get('body', '')[:200]}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error viewing PR #{pr_number}: {e}"

    @tool(
        name="pr_diff",
        description=(
            "Get the full diff of a pull request. "
            "Returns the unified diff output showing all code changes. "
            "Always fetches the latest diff from the GitHub API, "
            "independent of local git state. "
            "Use this to review the actual code changes in a PR."
        ),
    )
    def _pr_diff(pr_number: int) -> str:
        try:
            diff_output = _gh([
                "api",
                f"repos/{{owner}}/{{repo}}/pulls/{pr_number}",
                "--header", "Accept: application/vnd.github.v3.diff",
            ])
            if not diff_output.strip():
                return f"PR #{pr_number} has no diff (possibly no changes or already merged)."
            return f"Diff for PR #{pr_number}:\n\n{diff_output}"
        except Exception as e:
            return f"Error getting diff for PR #{pr_number}: {e}"

    @tool(
        name="pr_review_comment",
        description=(
            "Submit a review with inline comments on specific lines of a pull request. "
            "Each comment targets a file path and line number in the diff. "
            "The review event can be COMMENT, APPROVE, or REQUEST_CHANGES. "
            "IMPORTANT: Only call this after the user has approved the review content."
        ),
    )
    def _pr_review_comment(
        pr_number: int,
        body: str,
        event: str = "COMMENT",
        comments: Optional[str] = None,
    ) -> str:
        try:
            event = event.upper()
            if event not in ("COMMENT", "APPROVE", "REQUEST_CHANGES"):
                return f"Error: Invalid event '{event}'. Must be COMMENT, APPROVE, or REQUEST_CHANGES."
            review_payload: dict = {"body": body, "event": event}
            if comments:
                try:
                    parsed_comments = json.loads(comments)
                    if not isinstance(parsed_comments, list):
                        return "Error: 'comments' must be a JSON array."
                    for i, c in enumerate(parsed_comments):
                        if not isinstance(c, dict):
                            return f"Error: Comment at index {i} is not an object."
                        missing = [k for k in ("path", "line", "body") if k not in c]
                        if missing:
                            return f"Error: Comment at index {i} is missing fields: {', '.join(missing)}"
                    api_comments = []
                    for c in parsed_comments:
                        api_comment = {"path": c["path"], "line": c["line"], "body": c["body"]}
                        if "side" in c:
                            api_comment["side"] = c["side"]
                        api_comments.append(api_comment)
                    review_payload["comments"] = api_comments
                except json.JSONDecodeError as e:
                    return f"Error: Failed to parse 'comments' JSON: {e}"
            request_json = json.dumps(review_payload)
            raw_output = _gh(
                ["api", f"repos/{{owner}}/{{repo}}/pulls/{pr_number}/reviews",
                 "--method", "POST", "--input", "-"],
                stdin_input=request_json,
            )
            try:
                response = json.loads(raw_output)
                review_id = response.get("id", "unknown")
                html_url = response.get("html_url", "")
                return (
                    f"Review submitted successfully for PR #{pr_number}.\n"
                    f"  Event: {event}\n"
                    f"  Review ID: {review_id}\n"
                    f"  Inline comments: {len(review_payload.get('comments', []))}\n"
                    f"  URL: {html_url}"
                )
            except json.JSONDecodeError:
                return f"Review submitted for PR #{pr_number} (event: {event}). Raw response:\n{raw_output[:500]}"
        except Exception as e:
            return f"Error submitting review for PR #{pr_number}: {e}"

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
    def _pr_review_submit(pr_number: int, event: str, body: str = "") -> str:
        try:
            event = event.lower().replace("_", "-")
            valid_events = {"approve", "request-changes", "comment"}
            if event not in valid_events:
                return f"Error: Invalid event '{event}'. Must be one of: {', '.join(sorted(valid_events))}"
            if event in ("request-changes", "comment") and not body.strip():
                return f"Error: 'body' is required for '{event}' reviews."
            args = ["pr", "review", str(pr_number), f"--{event}"]
            if body.strip():
                args.extend(["--body", body])
            output = _gh(args)
            return (
                f"Review submitted for PR #{pr_number}.\n"
                f"  Event: {event}\n"
                f"  Body: {body[:200]}{'...' if len(body) > 200 else ''}\n"
                f"{output}"
            )
        except Exception as e:
            return f"Error submitting review for PR #{pr_number}: {e}"

    @tool(
        name="pr_get_comments",
        description=(
            "Get all comments on a specific pull request by number. "
            "Returns both general issue-level comments and inline review comments "
            "(diff-level comments with file path and line number). "
            "Use this to review the existing discussion history before adding a new review."
        ),
    )
    def _pr_get_comments(pr_number: int) -> str:
        try:
            raw = _gh([
                "pr", "view", str(pr_number),
                "--json", "comments,reviews",
            ])
            data = json.loads(raw)
            lines = []
            comments = data.get("comments", [])
            if comments:
                lines.append(f"=== Issue-level Comments ({len(comments)}) ===")
                for c in comments:
                    author = c.get("author", {}).get("login", "unknown")
                    lines.append(f"\n[{author}] {c.get('createdAt', '')}\n{c.get('body', '')}")
            reviews = data.get("reviews", [])
            if reviews:
                lines.append(f"\n=== Reviews ({len(reviews)}) ===")
                for r in reviews:
                    author = r.get("author", {}).get("login", "unknown")
                    lines.append(f"\n[{author}] {r.get('state', '')} {r.get('createdAt', '')}\n{r.get('body', '')}")
            if not lines:
                return f"No comments or reviews found for PR #{pr_number}."
            return "\n".join(lines)
        except Exception as e:
            return f"Error getting comments for PR #{pr_number}: {e}"

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
    def _submit_pull_request(
        title: str,
        body: str,
        base: str = "",
        draft: bool = True,
    ) -> str:
        try:
            args = ["pr", "create", "--title", title, "--body", body]
            if base.strip():
                args.extend(["--base", base.strip()])
            if draft:
                args.append("--draft")
            return _gh(args)
        except Exception as e:
            return f"Error creating pull request: {e}"

    @tool(
        name="issue_list",
        description=(
            "List issues in the current repository. "
            "Returns issue number, title, author, labels, and creation date. "
            "Supports filtering by state and labels."
        ),
    )
    def _issue_list(state: str = "open", limit: int = 30, labels: str = "") -> str:
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
            raw = _gh(args)
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
                assignee_str = f"  Assignees: {', '.join(assignees)}" if assignees else ""
                lines.append(
                    f"  #{issue['number']}  {issue['title']}\n"
                    f"    Author: {author} | State: {issue.get('state', 'N/A')}\n"
                    f"    Created: {issue.get('createdAt', 'N/A')}"
                    f" | Updated: {issue.get('updatedAt', 'N/A')}\n"
                    + (f"    {label_str}\n" if label_str else "")
                    + (f"    {assignee_str}\n" if assignee_str else "")
                    + f"    URL: {issue.get('url', 'N/A')}"
                )
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing issues: {e}"

    @tool(
        name="issue_view",
        description=(
            "Get detailed information about a specific issue by number. "
            "Returns title, body, author, labels, assignees, and state. "
            "Use this to understand the full context of an issue."
        ),
    )
    def _issue_view(issue_number: int) -> str:
        try:
            raw = _gh([
                "issue", "view", str(issue_number),
                "--json",
                "number,title,body,author,state,labels,assignees,"
                "comments,createdAt,updatedAt,url,milestone",
            ])
            issue = json.loads(raw)
            author = issue.get("author", {}).get("login", "unknown")
            lines = [
                f"Issue #{issue['number']}: {issue['title']}",
                f"State: {issue['state']}",
                f"Author: {author}",
                f"Created: {issue.get('createdAt', 'N/A')}"
                f" | Updated: {issue.get('updatedAt', 'N/A')}",
                f"URL: {issue['url']}",
            ]
            labels = issue.get("labels", [])
            if labels:
                lines.append(f"Labels: {', '.join(lb.get('name', '') for lb in labels)}")
            assignees = issue.get("assignees", [])
            if assignees:
                lines.append(f"Assignees: {', '.join(a.get('login', '') for a in assignees)}")
            body = issue.get("body", "").strip()
            lines.append(f"\n--- Description ---\n{body}" if body else "\n--- Description ---\n(no description)")
            comments = issue.get("comments", [])
            if comments:
                lines.append(f"\n--- Comments ({len(comments)}) ---")
                for c in comments:
                    commenter = c.get("author", {}).get("login", "unknown")
                    lines.append(f"\n[{commenter}] {c.get('createdAt', '')}\n{c.get('body', '')[:500]}")
            return "\n".join(lines)
        except Exception as e:
            return f"Error viewing issue #{issue_number}: {e}"

    @tool(
        name="issue_get_comments",
        description=(
            "Get all comments on a specific issue by number. "
            "Returns each comment with author, timestamp, and full body text. "
            "Use this to read the full discussion history of an issue."
        ),
    )
    def _issue_get_comments(issue_number: int) -> str:
        try:
            raw = _gh([
                "issue", "view", str(issue_number),
                "--json", "comments",
            ])
            data = json.loads(raw)
            comments = data.get("comments", [])
            if not comments:
                return f"No comments found for Issue #{issue_number}."
            lines = [f"Comments for Issue #{issue_number} ({len(comments)} total):\n"]
            for c in comments:
                author = c.get("author", {}).get("login", "unknown")
                lines.append(f"[{author}] {c.get('createdAt', '')}\n{c.get('body', '')}\n")
            return "\n".join(lines)
        except Exception as e:
            return f"Error getting comments for Issue #{issue_number}: {e}"

    @tool(
        name="submit_issue",
        description=(
            "Create a new GitHub Issue in the current repository. "
            "IMPORTANT: Only call this when explicitly instructed by the user."
        ),
    )
    def _submit_issue(
        title: str,
        body: str,
        labels: str = "",
        assignees: str = "",
    ) -> str:
        try:
            cmd = ["issue", "create", "--title", title, "--body", body]
            if labels:
                for label in labels.split(","):
                    cmd.extend(["--label", label.strip()])
            if assignees:
                for assignee in assignees.split(","):
                    cmd.extend(["--assignee", assignee.strip()])
            return _gh(cmd)
        except Exception as e:
            return f"Error creating issue: {e}"

    @tool(
        name="issue_add_comment",
        description=(
            "Add a comment to an existing GitHub Issue. "
            "IMPORTANT: Only call this when explicitly instructed by the user."
        ),
    )
    def _issue_add_comment(issue_number: int, body: str) -> str:
        try:
            result = _gh(["issue", "comment", str(issue_number), "--body", body])
            return f"Comment added to Issue #{issue_number}.\n{result}".strip()
        except Exception as e:
            return f"Error adding comment to Issue #{issue_number}: {e}"

    # ------------------------------------------------------------------
    # Assemble and return
    # ------------------------------------------------------------------

    return [
        # File management
        _read_lines,
        _write_file,
        _file_search,
        _copy_file,
        _move_file,
        _file_delete,
        _list_directory,
        _create_new_file,
        # Text edit
        _replace_exact,
        _insert_after_exact,
        _insert_before_exact,
        # Patch
        _apply_patch,
        # Git
        _create_branch,
        _commit_changes,
        _git_push,
        # Repo analysis
        _repo_summarize,
        _generate_repo_description,
        _manage_code_index,
        _search_code_repository,
        # GitHub CLI
        _pr_list,
        _pr_view,
        _pr_diff,
        _pr_review_comment,
        _pr_review_submit,
        _pr_get_comments,
        _submit_pull_request,
        _issue_list,
        _issue_view,
        _issue_get_comments,
        _submit_issue,
        _issue_add_comment,
        # Phase (stateless)
        report_phase,
    ]
