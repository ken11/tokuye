"""
Per-repository analysis tools for EpicManagerAgent (v3 Epic Mode).

These are "epic-safe" variants of the standard repo_summarize / repo_description /
manage_code_index / search_code_repository tools.

Key differences from the standard tools:
  1. Accept ``repo_name`` (a key in epic.yaml) instead of using settings.project_root.
  2. Validate that the name exists in epic.yaml; raise ValueError otherwise.
  3. Never mutate settings.project_root.
  4. Store all artifacts (.tokuye/ sub-files) inside the *target repo's* own
     .tokuye/ directory, not the Epic management directory.

Implementation delegates to the internal helpers in the standard tool modules
(manage_code_index_for, search_code_for) so that all FAISS logic lives in one place.
"""

from __future__ import annotations

import logging

from strands import tool

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
from tokuye.utils.epic_config import resolve_repo_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strands tools
# ---------------------------------------------------------------------------


@tool(
    name="repo_summarize_epic",
    description=(
        "Scan a repository defined in epic.yaml and generate a repo-summary.xml "
        "inside that repository's .tokuye/ directory. "
        "repo_name must be a key defined in .tokuye/epic.yaml."
    ),
)
def repo_summarize_epic(repo_name: str, force_full_update: bool = False) -> str:
    """Summarize a repository listed in epic.yaml.

    Args:
        repo_name: Key from epic.yaml repos (e.g. 'backend').
        force_full_update: If True, ignore existing summary and rescan all files.

    Returns:
        Path of the written repo-summary.xml.
    """
    repo_root = resolve_repo_path(repo_name)
    summary = summarize_repo(repo_root, force_full_update)
    content = render_xml(summary)

    out_dir = repo_root / ".tokuye"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "repo-summary.xml"
    out_file.write_text(content, encoding="utf-8")

    logger.info("repo_summarize_epic: wrote %s", out_file)
    return f"Written summary to {out_file}"


@tool(
    name="repo_description_epic",
    description=(
        "Generate a project description for a repository defined in epic.yaml "
        "and save it to that repository's .tokuye/repo-description.md. "
        "repo_name must be a key defined in .tokuye/epic.yaml."
    ),
)
def repo_description_epic(repo_name: str) -> str:
    """Generate repo description for a repo listed in epic.yaml.

    Args:
        repo_name: Key from epic.yaml repos (e.g. 'backend').

    Returns:
        Confirmation message with output path.
    """
    repo_root = resolve_repo_path(repo_name)
    return generate_repo_description_with_detail_control(repo_root)


@tool(
    name="manage_code_index_epic",
    description=(
        "Build or update the FAISS code-search index for a repository defined in epic.yaml. "
        "Stores the index inside that repository's .tokuye/ directory. "
        "repo_name must be a key defined in .tokuye/epic.yaml. "
        "action: 'build' | 'update' | 'rebuild'."
    ),
)
def manage_code_index_epic(repo_name: str, action: str = "update") -> str:
    """Manage FAISS index for a repo listed in epic.yaml.

    Args:
        repo_name: Key from epic.yaml repos (e.g. 'backend').
        action: Action to perform
            - "update": Differential update (detect and apply additions/updates/deletions).
                        Use this by default in almost all cases.
            - "build": Build new if doesn't exist (do nothing if existing and fresh).
                       Use only when the index is missing or suspected to be corrupted.
            - "rebuild": Force full rebuild (discard existing and recreate).
                         Use only when explicitly instructed or the index is clearly broken.

    Returns:
        Summary string of execution result.
    """
    repo_root = resolve_repo_path(repo_name)
    return manage_code_index_for(repo_root, action)


@tool(
    name="search_code_epic",
    description=(
        "Search for code snippets in a repository defined in epic.yaml "
        "using natural language or keywords. "
        "repo_name must be a key defined in .tokuye/epic.yaml."
    ),
)
def search_code_epic(repo_name: str, query: str, top_k: int = 3) -> str:
    """Search code in a repo listed in epic.yaml.

    Args:
        repo_name: Key from epic.yaml repos (e.g. 'backend').
        query: Search query (natural language or keywords).
        top_k: Number of results to return (default 3).

    Returns:
        Formatted search results with file paths and line numbers.
    """
    repo_root = resolve_repo_path(repo_name)
    results = search_code_for(repo_root, query, top_k)

    # Prefix each file path with the repo_name for clarity
    if results == "No matching code found.":
        return f"No matching code found in '{repo_name}'."

    prefixed = []
    for line in results.splitlines():
        if line.startswith("File: "):
            prefixed.append(f"[{repo_name}] {line}")
        else:
            prefixed.append(line)
    return "\n".join(prefixed)
