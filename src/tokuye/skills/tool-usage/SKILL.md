---
name: tool-usage
description: Detailed tool priority order and handling rules for all available tools. Load this skill when you need to decide which tool to use or how to use a specific tool correctly.
---

# Tool Usage

## Available tools

- `read_lines`, `write_file`
- `replace_exact`, `insert_after_exact`, `insert_before_exact`
- `file_search`
- `copy_file`, `move_file`, `file_delete`, `list_directory`
- `create_branch`, `commit_changes`
- `repo_summarize`, `generate_repo_description_tool`
- `search_code_repository`, `manage_code_index`

## Priority order (default)

1. `repo_summarize` — initial run, when state changes, and at the start of follow-ups
2. `generate_repo_description_tool` — initial run, when state changes, and at the start of follow-ups
3. `manage_code_index` — initial run, when state changes, at the start of follow-ups, and before searching
4. `search_code_repository` — always use this first to locate relevant files and lines
5. `read_lines` — read only the needed range; if unknown, page ~50 lines at a time
6. `replace_exact` / `insert_after_exact` / `insert_before_exact` — default for editing existing files
7. `write_file` — new files or full rewrites; when overwriting, read first to avoid accidental deletions
8. `create_branch` / `commit_changes`
9. `copy_file` / `move_file` / `file_delete` — only when necessary
10. `list_directory` / `file_search` — auxiliary

## Key rules per tool

### `replace_exact` / `insert_after_exact` / `insert_before_exact`
- Always call `read_lines` first to copy the target block verbatim
- These tools fail if the text matches zero or more than one location — be precise

### `write_file`
- This **overwrites the entire file**. Never use it for partial edits to existing files
- When rewriting an existing file, read the full file first and carry over all required content

### `search_code_repository`
- Use natural language or keywords; returns file paths and line numbers
- Always run `manage_code_index` before searching if code has changed since last index update

### `manage_code_index`
- Run after any code changes before performing a new search
- Use `action="update"` for incremental updates (default); `action="rebuild"` only when the index is corrupted

### `read_lines`
- Line numbers are 1-indexed and inclusive
- Read only what you need — avoid reading entire large files at once
