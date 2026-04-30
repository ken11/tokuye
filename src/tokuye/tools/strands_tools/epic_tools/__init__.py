"""
Epic Mode (v3) tool sets.

Exports:
  epic_manager_tools      – full tool list for EpicManagerAgent
  make_epic_worker_tools  – factory that returns a sandboxed tool list for EpicWorkerAgent
"""

from tokuye.tools.strands_tools.epic_tools.epic_dir_tools import (
    create_epic_dir,
    read_epic_file,
    save_epic_plan,
    save_epic_tasks,
    save_task_result,
    update_epic_progress,
    save_epic_decisions,
)
from tokuye.tools.strands_tools.epic_tools.repo_ops import (
    manage_code_index_epic,
    repo_description_epic,
    repo_summarize_epic,
    search_code_epic,
)

# Read-only / investigation tools shared from the standard tool set
from tokuye.tools.strands_tools.file_management import (
    file_search,
    list_directory,
    read_lines,
)
from tokuye.tools.strands_tools.issue_tools import (
    issue_get_comments,
    issue_list,
    issue_view,
)
from tokuye.tools.strands_tools.epic_tools.worker_tool import run_epic_worker
from tokuye.tools.strands_tools.phase_tool import report_phase
from tokuye.tools.strands_tools.epic_tools.worker_tools import make_epic_worker_tools

epic_manager_tools = [
    # Epic directory management
    create_epic_dir,
    save_epic_plan,
    save_epic_tasks,
    save_task_result,
    update_epic_progress,
    read_epic_file,
    save_epic_decisions,
    # Per-repo analysis (epic-safe versions)
    repo_summarize_epic,
    repo_description_epic,
    manage_code_index_epic,
    search_code_epic,
    # Worker delegation
    run_epic_worker,
    # Read-only file tools (for reading repo contents)
    read_lines,
    file_search,
    list_directory,
]
