from tokuye.tools.strands_tools.file_management import (copy_file, file_delete,
                                                        file_search,
                                                        list_directory,
                                                        move_file, read_lines,
                                                        write_file)
from tokuye.tools.strands_tools.git_tools import commit_changes, create_branch
from tokuye.tools.strands_tools.patch_tools import apply_patch
from tokuye.tools.strands_tools.phase_tool import report_phase
from tokuye.tools.strands_tools.pr_review_tools import (pr_diff, pr_list,
                                                        pr_review_comment,
                                                        pr_review_submit,
                                                        pr_view)
from tokuye.tools.strands_tools.repo_description import \
    generate_repo_description_tool
from tokuye.tools.strands_tools.repo_summary import repo_summarize
from tokuye.tools.strands_tools.repo_summary_rag.code_index_admin_tool import \
    manage_code_index
from tokuye.tools.strands_tools.repo_summary_rag.code_search_tool import \
    search_code_repository

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
    create_branch,
    commit_changes,
    repo_summarize,
    generate_repo_description_tool,
    search_code_repository,
    manage_code_index,
    apply_patch,
    pr_list,
    pr_view,
    pr_diff,
    pr_review_comment,
    pr_review_submit,
    report_phase,
]
