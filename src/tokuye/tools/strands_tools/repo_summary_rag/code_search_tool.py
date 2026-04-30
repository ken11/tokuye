from __future__ import annotations

from pathlib import Path

from strands import tool
from tokuye.tools.strands_tools.repo_summary_rag.data_loader import \
    parse_repository
from tokuye.tools.strands_tools.repo_summary_rag.embedder import get_embedding
from tokuye.tools.strands_tools.repo_summary_rag.vector_store import (
    build_index, load_index_if_fresh, search, try_load, update_index_diff)


def search_code_for(project_root: Path, query: str, top_k: int = 3) -> str:
    """Search code in a specific project root (internal helper).

    Used by epic-safe tool variants to search a target repo without
    mutating settings.project_root.

    Args:
        project_root: Absolute path to the target repository root.
        query: Search query (natural language or keywords).
        top_k: Number of results to return (default 3).

    Returns:
        Formatted search results with file paths and line numbers.
    """
    override = str(project_root)
    xml_path = str(project_root / ".tokuye" / "repo-summary.xml")

    chunks, generated_at = parse_repository(xml_path=xml_path)
    if not load_index_if_fresh(generated_at or "", project_root_override=override):
        if not try_load(project_root_override=override):
            build_index(chunks, generated_at or "", project_root_override=override)
        else:
            update_index_diff(chunks, generated_at or "", project_root_override=override)

    qvec = get_embedding(query)
    results = search(qvec, top_k)

    if not results:
        return "No matching code found."

    lines = []
    for c in results:
        lines.append(f"File: {c['path']} (lines {c['start_line']}-{c['end_line']})")
        lines.append("```")
        lines.append(c["content"])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


@tool(
    name="search_code_repository",
    description="Search for related code snippets in the repository using natural language or keywords. Returns matching code with file paths and line numbers.",
)
def search_code_repository(query: str, top_k: int = 3) -> str:
    """Search for related code snippets in the repository

    Args:
        query: Search query (natural language or keywords)
        top_k: Number of results to retrieve (default 3)
    """
    from tokuye.utils.config import settings
    return search_code_for(settings.project_root, query, top_k)
