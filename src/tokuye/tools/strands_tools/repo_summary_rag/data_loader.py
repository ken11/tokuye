from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

from tokuye.tools.strands_tools.repo_summary_rag.parsers import \
    segment_code_by_path
from tokuye.tools.strands_tools.repo_summary_rag.splitter import \
    OffsetRecursiveSplitter
from tokuye.utils.config import settings

MAX_CHARS_PER_SEGMENT = 3500
CHUNK_SIZE = 3000
CHUNK_OVERLAP = 200
SEPARATORS = ["\n\n", "\n", " ", ""]


def _get_repo_summary_path() -> str:
    """Return absolute path of repo-summary.xml"""
    return os.path.join(settings.project_root, ".tokuye", "repo-summary.xml")


def parse_repository(
    xml_path: Optional[str] = None,
) -> Tuple[List[Dict], Optional[str]]:
    """
    Parse repo-summary.xml, split it into primary chunks by logical blocks
    (functions/classes, etc.), and further split overly long blocks into
    secondary chunks based on character count.

    Returns:
        (chunks, generated_at)
        chunks: List[Dict] ... Each element is a dict with the following keys:
            {
              "path": str,            # File path
              "mtime": float,         # mtime (from an XML attribute)
              "total_lines": int,     # Total lines in the file (XML attribute; falls back to counting lines)
              "start_line": int,      # Chunk start line (1-indexed, inclusive)
              "end_line": int,        # Chunk end line (1-indexed, inclusive)
              "content": str,         # Chunk content
            }
        generated_at: Optional[str] ... The root element's generatedAt attribute
    """
    xml_path = xml_path or _get_repo_summary_path()
    if not os.path.exists(xml_path):
        raise FileNotFoundError(
            "repo-summary.xml not found; run RepoSummarizeTool first."
        )

    tree = ET.parse(xml_path)
    root = tree.getroot()
    generated_at = root.get("generatedAt")

    chunks: List[Dict] = []

    for elem in root.findall(".//file"):
        file_path = elem.get("path", "Unknown path")
        mtime = float(elem.get("mtime", "0"))
        total_lines_attr = int(elem.get("lines", "0"))

        file_text = elem.text or ""
        if file_text.startswith("\n"):
            file_text = file_text.split("\n", 1)[1]  # drop exactly the one blank line inserted by render_xml

        file_lines = file_text.splitlines()
        total_lines = total_lines_attr  # use the authoritative line count written by render_xml

        lang, segments = segment_code_by_path(file_text, file_path)  # List[CodeSegment]
        language = None
        if lang != "plain":
            language = lang

        splitter = OffsetRecursiveSplitter(
            language=language,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        for seg in segments:
            seg_text = seg.text
            if len(seg_text) <= MAX_CHARS_PER_SEGMENT:
                chunks.append(
                    {
                        "path": file_path,
                        "mtime": mtime,
                        "total_lines": total_lines,
                        "start_line": seg.start_line,
                        "end_line": seg.end_line,
                        "content": seg_text,
                    }
                )
                continue

            for chunk in splitter.split_with_lines(seg_text):
                start_line = seg.start_line + (chunk.start_line - 1)
                end_line = seg.start_line + (chunk.end_line - 1)
                chunks.append(
                    {
                        "path": file_path,
                        "mtime": mtime,
                        "total_lines": total_lines,
                        "start_line": start_line,
                        "end_line": end_line,
                        "content": chunk.content,
                    }
                )

    return chunks, generated_at
