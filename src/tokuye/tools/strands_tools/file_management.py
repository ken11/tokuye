"""
File management tools for safe file operations within a sandboxed directory.

Based on langchain-community's FileManagementToolkit:
https://github.com/langchain-ai/langchain (MIT License)
"""

import os
import shutil
from pathlib import Path

from strands import tool
from tokuye.tools.strands_tools.utils import (FileValidationError,
                                              _is_ignored_by_git,
                                              get_validated_relative_path)
from tokuye.utils.config import settings


@tool(
    name="file_search",
    description="Recursively search for files in a subdirectory whose names match a shell wildcard pattern (e.g., `*.py`). Obeys `.gitignore` exclusions.",
)
def file_search(pattern: str, dir_path: str = ".") -> str:
    """
    Search for files in a directory that match a pattern.

    Args:
        pattern: Search pattern (shell-style wildcard, e.g. "*.py")
        dir_path: Directory to search (defaults to the current directory)

    Returns:
        A list of matched files.
    """
    import glob

    root_dir = settings.project_root

    try:
        search_dir = get_validated_relative_path(root_dir, dir_path)
    except FileValidationError:
        return f"Error: Access denied to dir_path: {dir_path}. Permission granted exclusively to the current working directory"

    try:
        original_dir = os.getcwd()
        os.chdir(search_dir)

        matches = glob.glob(pattern, recursive=True)

        os.chdir(original_dir)

        filtered_matches = []
        for match in matches:
            abs_path = search_dir / match
            if not _is_path_ignored(root_dir, abs_path):
                filtered_matches.append(match)

        if not filtered_matches:
            return f"No files matching '{pattern}' found in '{dir_path}'."

        return "\n".join(filtered_matches)
    except Exception as e:
        if "original_dir" in locals():
            os.chdir(original_dir)
        return f"Error: {str(e)}"


@tool(
    name="copy_file",
    description="Copy a file within the workspace. Access is restricted to the directory tree under `root_dir`; any path matched by `.gitignore` is denied.",
)
def copy_file(source_path: str, destination_path: str) -> str:
    """
    Copy a file

    Args:
        source_path: Relative path of source file
        destination_path: Relative path of destination

    Returns:
        Operation result message
    """
    root_dir = settings.project_root

    try:
        src_abs = get_validated_relative_path(root_dir, source_path)
    except FileValidationError:
        return f"Error: Access denied to source_path: {source_path}. Permission granted exclusively to the current working directory"

    try:
        dst_abs = get_validated_relative_path(root_dir, destination_path)
    except FileValidationError:
        return f"Error: Access denied to destination_path: {destination_path}. Permission granted exclusively to the current working directory"

    if _is_path_ignored(root_dir, src_abs):
        return f"Error: Access denied to source_path: {source_path}. File is matched by .gitignore patterns."

    if _is_path_ignored(root_dir, dst_abs):
        return f"Error: Access denied to destination_path: {destination_path}. File is matched by .gitignore patterns."

    try:
        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_abs, dst_abs, follow_symlinks=False)
        return f"File copied successfully from {source_path} to {destination_path}."
    except Exception as e:
        return f"Error: {str(e)}"


@tool(
    name="move_file",
    description="Move (or rename) a file within the workspace. Source and destination must lie under `root_dir`, and `.gitignore` patterns are enforced.",
)
def move_file(source_path: str, destination_path: str) -> str:
    """
    Move (or rename) a file

    Args:
        source_path: Relative path of source file
        destination_path: Relative path of destination

    Returns:
        Operation result message
    """
    root_dir = settings.project_root

    try:
        src_abs = get_validated_relative_path(root_dir, source_path)
    except FileValidationError:
        return f"Error: Access denied to source_path: {source_path}. Permission granted exclusively to the current working directory"

    try:
        dst_abs = get_validated_relative_path(root_dir, destination_path)
    except FileValidationError:
        return f"Error: Access denied to destination_path: {destination_path}. Permission granted exclusively to the current working directory"

    if _is_path_ignored(root_dir, src_abs):
        return f"Error: Access denied to source_path: {source_path}. File is matched by .gitignore patterns."

    if _is_path_ignored(root_dir, dst_abs):
        return f"Error: Access denied to destination_path: {destination_path}. File is matched by .gitignore patterns."

    try:
        dst_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src_abs, dst_abs)
        return f"File moved successfully from {source_path} to {destination_path}."
    except Exception as e:
        return f"Error: {str(e)}"


@tool(
    name="file_delete",
    description="Delete a file from disk. Access is limited to the directory tree under `root_dir`; files matched by `.gitignore` are denied.",
)
def file_delete(file_path: str) -> str:
    """
    Delete a file

    Args:
        file_path: Relative path of file to delete

    Returns:
        Operation result message
    """
    root_dir = settings.project_root

    try:
        abs_path = get_validated_relative_path(root_dir, file_path)
    except FileValidationError:
        return f"Error: Access denied to file_path: {file_path}. Permission granted exclusively to the current working directory"

    if _is_path_ignored(root_dir, abs_path):
        return f"Error: Access denied to file_path: {file_path}. File is matched by .gitignore patterns."

    try:
        if not abs_path.exists():
            return f"Error: File {file_path} does not exist."

        if abs_path.is_dir():
            return f"Error: {file_path} is a directory. Use a directory removal tool instead."

        abs_path.unlink()
        return f"File {file_path} deleted successfully."
    except Exception as e:
        return f"Error: {str(e)}"


@tool(
    name="list_directory",
    description="List files and directories in the given folder, ignoring those that match `.gitignore`. Access is confined to the `root_dir` sandbox.",
)
def list_directory(dir_path: str = ".") -> str:
    """
    List files and subdirectories in a directory

    Args:
        dir_path: Relative path of directory to list (default is current directory)

    Returns:
        List of files and directories
    """
    root_dir = settings.project_root

    try:
        abs_path = get_validated_relative_path(root_dir, dir_path)
    except FileValidationError:
        return f"Error: Access denied to dir_path: {dir_path}. Permission granted exclusively to the current working directory"

    if not abs_path.exists():
        return f"Error: Directory {dir_path} does not exist."

    if not abs_path.is_dir():
        return f"Error: {dir_path} is not a directory."

    try:
        entries = list(abs_path.iterdir())

        filtered_entries = []
        for entry in entries:
            if not _is_path_ignored(root_dir, entry):
                entry_name = entry.name
                if entry.is_dir():
                    entry_name += "/"
                filtered_entries.append(entry_name)

        filtered_entries.sort(key=lambda x: (0 if x.endswith("/") else 1, x))

        if not filtered_entries:
            return f"Directory {dir_path} is empty or all entries are ignored by .gitignore."

        return "\n".join(filtered_entries)
    except Exception as e:
        return f"Error: {str(e)}"


@tool(
    name="read_lines",
    description="Read specific lines from a UTF-8 text file. Access is limited to the directory tree under `root_dir`; files matched by `.gitignore` are denied. Line numbers are 1-indexed and inclusive.",
)
def read_lines(file_path: str, start_line: int, end_line: int) -> str:
    """
    Read specific lines from a file (1-indexed, inclusive).

    Args:
        file_path: Relative path of the file to read
        start_line: Start line number (1-indexed)
        end_line: End line number (1-indexed, inclusive)

    Returns:
        The joined text of the specified line range.
    """
    root_dir = settings.project_root

    # 1) Validate that the path stays within root_dir
    try:
        abs_path = get_validated_relative_path(root_dir, file_path)
    except FileValidationError:
        return f"Error: Access denied to file_path: {file_path}. Permission granted exclusively to the current working directory"

    # 2) Apply .gitignore filtering
    if _is_path_ignored(root_dir, abs_path):
        return f"Error: Access denied to file_path: {file_path}. File is matched by .gitignore patterns."

    # 3) Validate line range
    if start_line < 1:
        return f"Error: start_line must be at least 1, got {start_line}"
    if end_line < start_line:
        return f"Error: end_line ({end_line}) must be greater than or equal to start_line ({start_line})"

    # 4) Validate file
    if not abs_path.exists():
        return f"Error: no such file or directory: {file_path}"
    if abs_path.is_dir():
        return f"Error: {file_path} is a directory."

    # 5) Stream and collect only the requested lines
    try:
        lines: list[str] = []
        with abs_path.open("r", encoding="utf-8") as handle:
            for i, line in enumerate(handle, 1):  # 1-indexed
                if i < start_line:
                    continue
                if i > end_line:
                    break
                lines.append(line)

        if not lines:
            return (
                f"No lines found in range {start_line}-{end_line} in file {file_path}"
            )

        return "".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"


@tool(
    name="write_file",
    description="Write UTF-8 text to a file. Access is restricted to the directory tree under `root_dir`; files matched by `.gitignore` are denied. Use append=true to append; otherwise it OVERWRITES THE ENTIRE FILE — all existing content is lost. You MUST read the complete file with read_lines first, then pass the full updated content.",
)
def write_file(file_path: str, text: str, append: bool = False) -> str:
    """
    Write text to a file (UTF-8). Optionally append.

    Args:
        file_path: Relative path of the file to write
        text: Text to write
        append: Append (True) or overwrite (False)

    Returns:
        Operation result message
    """
    root_dir = settings.project_root

    # 1) Validate that the path stays within root_dir
    try:
        abs_path = get_validated_relative_path(root_dir, file_path)
    except FileValidationError:
        return f"Error: Access denied to file_path: {file_path}. Permission granted exclusively to the current working directory"

    # 2) Apply .gitignore filtering
    if _is_path_ignored(root_dir, abs_path):
        return f"Error: Access denied to file_path: {file_path}. File is matched by .gitignore patterns."

    # 3) Write
    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with abs_path.open(mode, encoding="utf-8") as handle:
            handle.write(text)
        return f"File written successfully to {file_path}."
    except Exception as e:
        return f"Error: {str(e)}"


def _is_path_ignored(root: Path, abs_path: Path) -> bool:
    """
    Check if path is ignored by git (wrapper for _is_ignored_by_git).
    """
    return _is_ignored_by_git(root, abs_path)


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
def create_new_file(file_path: str, content: str) -> str:
    """
    Create a new file. Fails if the file already exists.

    Args:
        file_path: Relative path of the file to create
        content: Text content to write

    Returns:
        Operation result message
    """
    root_dir = settings.project_root

    try:
        abs_path = get_validated_relative_path(root_dir, file_path)
    except FileValidationError:
        return f"Error: Access denied to file_path: {file_path}. Permission granted exclusively to the current working directory"

    if _is_path_ignored(root_dir, abs_path):
        return f"Error: Access denied to file_path: {file_path}. File is matched by .gitignore patterns."

    if abs_path.exists():
        return f"Error: file already exists: {file_path}"

    try:
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_text(content, encoding="utf-8")
        return f"File created successfully: {file_path}"
    except Exception as e:
        return f"Error: {str(e)}"
