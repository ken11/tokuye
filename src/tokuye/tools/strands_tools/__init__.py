from tokuye.tools.strands_tools.file_management import (copy_file, create_new_file,
                                                        file_delete, file_search,
                                                        list_directory,
                                                        move_file, read_lines,
                                                        write_file)
from tokuye.tools.strands_tools.git_tools import commit_changes, create_branch, git_push
from tokuye.tools.strands_tools.patch_tools import apply_patch
from tokuye.tools.strands_tools.phase_tool import report_phase
from tokuye.tools.strands_tools.pr_review_tools import (pr_diff, pr_list,
                                                        pr_review_comment,
                                                        pr_review_submit,
                                                        pr_view,
                                                        pr_get_comments)
from tokuye.tools.strands_tools.pr_create_tool import submit_pull_request
from tokuye.tools.strands_tools.issue_tools import (issue_list,
                                                    issue_view,
                                                    issue_get_comments)
from tokuye.tools.strands_tools.repo_description import \
    generate_repo_description_tool
from tokuye.tools.strands_tools.repo_summary import repo_summarize
from tokuye.tools.strands_tools.repo_summary_rag.code_index_admin_tool import \
    manage_code_index
from tokuye.tools.strands_tools.repo_summary_rag.code_search_tool import \
    search_code_repository
from tokuye.tools.strands_tools.text_edit_tools import (insert_after_exact,
                                                        insert_before_exact,
                                                        replace_exact)

# from strands_tools import editor, file_read, file_write

all_tools = [
    # file_read,
    # file_write,
    # editor,
    read_lines,
    write_file,
    file_search,
    copy_file,
    move_file,
    file_delete,
    list_directory,
    replace_exact,
    insert_after_exact,
    insert_before_exact,
    create_branch,
    commit_changes,
    git_push,
    repo_summarize,
    generate_repo_description_tool,
    search_code_repository,
    manage_code_index,
    pr_list,
    pr_view,
    pr_diff,
    pr_review_comment,
    pr_review_submit,
    pr_get_comments,
    submit_pull_request,
    issue_list,
    issue_view,
    issue_get_comments,
    report_phase,
]

# ---------------------------------------------------------------------------
# Node-specific tool sets for state machine mode (v2)
# Each node only receives the tools it actually needs, reducing input token
# overhead and preventing unintended tool calls.
# ---------------------------------------------------------------------------

planner_tools = [
    repo_summarize,
    generate_repo_description_tool,
    manage_code_index,
    search_code_repository,
    read_lines,
    file_search,
    list_directory,
    issue_list,
    issue_view,
    issue_get_comments,
]

developer_tools = [
    read_lines,
    replace_exact,
    insert_after_exact,
    insert_before_exact,
    create_new_file,
    create_branch,
    commit_changes,
    file_search,
    list_directory,
    copy_file,
    move_file,
    file_delete,
]

pr_creator_tools = [
    submit_pull_request,
    git_push,
    read_lines,
    file_search,
    search_code_repository,
    pr_list,
    pr_view,
    pr_diff,
]

reviewer_tools = [
    pr_list,
    pr_view,
    pr_diff,
    pr_get_comments,
    pr_review_comment,
    pr_review_submit,
]
