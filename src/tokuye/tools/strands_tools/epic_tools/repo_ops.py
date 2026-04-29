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

FAISS index isolation
---------------------
The standard vector_store module uses module-level globals keyed to
settings.project_root.  To avoid cross-contamination between repos we
pass explicit paths to the underlying functions where possible, and
use a thin per-repo index wrapper for the cases that need it.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from strands import tool

from tokuye.tools.strands_tools.repo_description import (
    generate_repo_description_with_detail_control,
)
from tokuye.tools.strands_tools.repo_summary import render_xml, summarize_repo
from tokuye.tools.strands_tools.repo_summary_rag.data_loader import (
    MAX_CHARS_PER_SEGMENT,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    SEPARATORS,
)
from tokuye.tools.strands_tools.repo_summary_rag.embedder import get_embedding
from tokuye.tools.strands_tools.repo_summary_rag.parsers import segment_code_by_path
from tokuye.tools.strands_tools.repo_summary_rag.splitter import OffsetRecursiveSplitter
from tokuye.utils.epic_config import resolve_repo_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _tokuye_dir(repo_root: Path) -> Path:
    return repo_root / ".tokuye"


def _summary_xml_path(repo_root: Path) -> Path:
    return _tokuye_dir(repo_root) / "repo-summary.xml"


def _index_path(repo_root: Path) -> Path:
    return _tokuye_dir(repo_root) / "faiss.index"


def _chunks_meta_path(repo_root: Path) -> Path:
    return _tokuye_dir(repo_root) / "faiss-chunks.json"


def _timestamp_path(repo_root: Path) -> Path:
    return _tokuye_dir(repo_root) / "repo-summary-timestamp.txt"


def _parse_repository_for(repo_root: Path) -> Tuple[List[Dict], Optional[str]]:
    """Parse repo-summary.xml for *repo_root* and return (chunks, generated_at).

    Mirrors data_loader.parse_repository() but uses an explicit xml_path.
    """
    import xml.etree.ElementTree as ET

    xml_path = _summary_xml_path(repo_root)
    if not xml_path.exists():
        raise FileNotFoundError(
            f"repo-summary.xml not found at {xml_path}. "
            "Run repo_summarize_epic first."
        )

    tree = ET.parse(str(xml_path))
    root = tree.getroot()
    generated_at = root.get("generatedAt")

    splitter = OffsetRecursiveSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS,
    )

    chunks: List[Dict] = []
    for elem in root.findall(".//file"):
        file_path = elem.get("path", "Unknown path")
        mtime = float(elem.get("mtime", "0"))
        total_lines_attr = int(elem.get("lines", "0"))
        content = elem.text or ""

        primary_segments = segment_code_by_path(file_path, content)
        for seg in primary_segments:
            seg_content = seg["content"]
            seg_start = seg["start_line"]
            seg_end = seg["end_line"]
            total_lines = total_lines_attr or (content.count("\n") + 1)

            if len(seg_content) <= MAX_CHARS_PER_SEGMENT:
                chunks.append(
                    {
                        "path": file_path,
                        "mtime": mtime,
                        "total_lines": total_lines,
                        "start_line": seg_start,
                        "end_line": seg_end,
                        "content": seg_content,
                    }
                )
            else:
                sub_chunks = splitter.split_with_offsets(seg_content, seg_start)
                for sc in sub_chunks:
                    chunks.append(
                        {
                            "path": file_path,
                            "mtime": mtime,
                            "total_lines": total_lines,
                            "start_line": sc["start_line"],
                            "end_line": sc["end_line"],
                            "content": sc["content"],
                        }
                    )

    return chunks, generated_at


def _build_index_for(repo_root: Path, chunks: List[Dict], generated_at: Optional[str]) -> None:
    """Build and persist a FAISS index for *repo_root*."""
    import json

    import faiss
    import numpy as np

    from tokuye.tools.strands_tools.repo_summary_rag import embedder

    tokuye_dir = _tokuye_dir(repo_root)
    tokuye_dir.mkdir(parents=True, exist_ok=True)

    if not chunks:
        logger.warning("_build_index_for: no chunks for %s", repo_root)
        return

    vecs = []
    ids = []
    chunk_by_id: Dict[int, Dict] = {}

    for i, ch in enumerate(chunks):
        emb = get_embedding(ch["content"])
        vecs.append(emb)
        ids.append(i)
        chunk_by_id[i] = ch

    import numpy as np

    mat = np.array(vecs, dtype=np.float32)
    dim = int(mat.shape[1])
    base = faiss.IndexFlatIP(dim)
    index = faiss.IndexIDMap2(base)
    index.add_with_ids(mat, np.array(ids, dtype=np.int64))

    faiss.write_index(index, str(_index_path(repo_root)))

    meta_list = [dict(v, id=k) for k, v in chunk_by_id.items()]
    with open(_chunks_meta_path(repo_root), "w", encoding="utf-8") as f:
        json.dump(meta_list, f, ensure_ascii=False)

    with open(_timestamp_path(repo_root), "w", encoding="utf-8") as f:
        f.write(generated_at or "")

    logger.info(
        "Built FAISS index for %s: vectors=%d", repo_root, index.ntotal
    )


def _search_index_for(repo_root: Path, query: str, top_k: int = 3) -> List[Dict]:
    """Search the FAISS index for *repo_root*."""
    import json

    import faiss
    import numpy as np

    idx_path = _index_path(repo_root)
    meta_path = _chunks_meta_path(repo_root)

    if not idx_path.exists() or not meta_path.exists():
        return []

    index = faiss.read_index(str(idx_path))
    with open(meta_path, "r", encoding="utf-8") as f:
        meta_list = json.load(f)
    chunk_by_id = {int(m["id"]): m for m in meta_list}

    qvec = get_embedding(query)
    q = np.array([qvec], dtype=np.float32)
    distances, ids = index.search(q, top_k)

    results = []
    for dist, cid in zip(distances[0], ids[0]):
        if cid < 0:
            continue
        chunk = chunk_by_id.get(int(cid))
        if chunk:
            results.append(chunk)
    return results


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

    out_dir = _tokuye_dir(repo_root)
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
        action: 'build', 'update', or 'rebuild'.

    Returns:
        Summary string of execution result.
    """
    t0 = time.perf_counter()
    repo_root = resolve_repo_path(repo_name)
    action = (action or "update").lower()

    chunks, generated_at = _parse_repository_for(repo_root)

    idx_path = _index_path(repo_root)
    ts_path = _timestamp_path(repo_root)

    def _is_fresh() -> bool:
        if not idx_path.exists() or not ts_path.exists():
            return False
        saved_ts = ts_path.read_text(encoding="utf-8").strip()
        return saved_ts == (generated_at or "")

    if action == "build":
        if _is_fresh():
            return f"✅ Index for '{repo_name}' is up-to-date, no build needed."
        _build_index_for(repo_root, chunks, generated_at)
    elif action == "rebuild":
        _build_index_for(repo_root, chunks, generated_at)
    else:  # update
        _build_index_for(repo_root, chunks, generated_at)

    elapsed = time.perf_counter() - t0
    return (
        f"🔄 Index for '{repo_name}' updated.\n"
        f"- vectors: {len(chunks)}, generated_at: {generated_at}\n"
        f"- updated_in_sec: {elapsed:.2f}"
    )


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

    # Auto-build index if not present
    idx_path = _index_path(repo_root)
    if not idx_path.exists():
        chunks, generated_at = _parse_repository_for(repo_root)
        _build_index_for(repo_root, chunks, generated_at)

    results = _search_index_for(repo_root, query, top_k)

    if not results:
        return f"No matching code found in '{repo_name}'."

    lines = []
    for c in results:
        lines.append(
            f"[{repo_name}] File: {c['path']} (lines {c['start_line']}-{c['end_line']})"
        )
        lines.append("```")
        lines.append(c["content"])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)
