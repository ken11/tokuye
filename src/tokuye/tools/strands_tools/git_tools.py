from git import Repo
from strands import tool
from tokuye.utils.config import settings


@tool(
    name="create_branch",
    description="Create a new branch if it doesn't exist, or create a new branch with suffix if it exists",
)
def create_branch(name: str) -> str:
    """
    Create a new branch. If it already exists, create with a suffix.

    Args:
        name: Branch name

    Returns:
        Creation result message
    """
    try:
        repo = Repo(settings.project_root)

        name = settings.pr_branch_prefix + name.replace(" ", "-")

        # Check existing branch names
        existing_branches = [b.name for b in repo.branches]

        # Add suffix if branch with same name exists
        branch_name = name
        counter = 1
        while branch_name in existing_branches:
            branch_name = f"{name}-{counter}"
            counter += 1

        # Create and checkout new branch
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()

        return f"Created and checked out new branch '{branch_name}'"
    except Exception as e:
        return f"Error creating branch: {str(e)}"


@tool(
    name="commit_changes",
    description="Stage all changes and commit; returns list of committed files",
)
def commit_changes(message: str) -> str:
    """
    Stage all changes and commit

    Args:
        message: Commit message

    Returns:
        List of committed files
    """
    try:
        repo = Repo(settings.project_root)

        # Get changed files
        changed_files = [item.a_path for item in repo.index.diff(None)]
        untracked_files = repo.untracked_files

        # No changes to commit
        if not changed_files and not untracked_files:
            return "No changes to commit."

        # Stage all changes
        repo.git.add(".")

        # Commit
        commit = repo.index.commit(message)

        # Create list of committed files
        all_files = changed_files + untracked_files
        all_files.sort()

        files_str = "\n- " + "\n- ".join(all_files) if all_files else ""
        return f"Committed to branch '{repo.active_branch.name}' (SHA: {commit.hexsha}):{files_str}"
    except Exception as e:
        return f"Error committing changes: {str(e)}"
