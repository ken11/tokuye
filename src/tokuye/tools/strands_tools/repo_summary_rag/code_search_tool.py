from __future__ import annotations

from strands import tool
from tokuye.tools.strands_tools.repo_summary_rag.data_loader import \
    parse_repository
from tokuye.tools.strands_tools.repo_summary_rag.embedder import get_embedding
from tokuye.tools.strands_tools.repo_summary_rag.vector_store import (
    build_index, load_index_if_fresh, search, try_load, update_index_diff)


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
    # Load if up-to-date, otherwise build
    chunks, generated_at = parse_repository()
    if not load_index_if_fresh(generated_at or ""):
        # Create new if doesn't exist, or update diff if exists
        if not try_load():
            build_index(chunks, generated_at or "")
        else:
            update_index_diff(chunks, generated_at or "")

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
