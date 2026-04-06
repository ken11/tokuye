from strands import tool

from tokuye.tools.strands_tools.gh_utils import _run_gh


@tool(name="submit_issue", description="Create a new GitHub Issue in the current repository. IMPORTANT: Only call this when explicitly instructed by the user.")
def submit_issue(title: str, body: str, labels: str = "", assignees: str = "") -> str:
    """Create a new GitHub Issue in the current repository.

    Args:
        title: Title of the Issue
        body: Body/content of the Issue
        labels: Comma-separated list of labels (e.g. "bug,help wanted")
        assignees: Comma-separated list of assignees (e.g. "user1,user2")

    Returns:
        Issue URL on success, error message on failure
    """
    cmd = ["gh", "issue", "create", "--title", title, "--body", body]

    if labels:
        for label in labels.split(","):
            cmd.extend(["--label", label.strip()])

    if assignees:
        for assignee in assignees.split(","):
            cmd.extend(["--assignee", assignee.strip()])

    return _run_gh(cmd)