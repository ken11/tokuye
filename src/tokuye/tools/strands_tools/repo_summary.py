"""
Repository summarization tool that generates structured summaries of codebases.

Inspired by Repomix's repository packing functionality:
https://github.com/yamadashy/repomix (MIT License)
"""

import datetime
import logging
import re
import textwrap
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.sax.saxutils import escape as xml_escape

import chardet
from pathspec import PathSpec
from strands import tool
from tokuye.tools.strands_tools.utils import (_check_ignored_batch,
                                              _load_global_gitignore_patterns)
from tokuye.utils.config import settings

logger = logging.getLogger(__name__)


DEFAULT_IGNORE = [".git/**", ".DS_Store", ".env", "repo-summary.*"]

BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".exe",
    ".dll",
    ".so",
    ".class",
    ".woff",
    ".woff2",
    ".ttf",
    ".ico",
    ".heif",
    ".heic",
    ".bin",
    ".md",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def load_ignore(repo_root: Path) -> PathSpec:
    patterns: List[str] = DEFAULT_IGNORE.copy()

    # Load local .gitignore
    p = repo_root / ".gitignore"
    if p.exists():
        patterns += p.read_text().splitlines()

    # Load global gitignore patterns
    patterns += _load_global_gitignore_patterns()

    return PathSpec.from_lines("gitwildmatch", patterns)


def is_binary(path: Path, sample_size: int = 2048) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        raw = path.read_bytes()[:sample_size]
    except Exception:
        return True
    if b"\x00" in raw:
        return True
    detected = chardet.detect(raw)
    return detected["encoding"] is None


def load_summary_ignore(repo_root: Path) -> List[str]:
    summary_ignore_path = repo_root / ".tokuye" / "summary.ignore"
    if summary_ignore_path.exists():
        return summary_ignore_path.read_text().splitlines()
    return []


def is_likely_seed_data(path: Path, content: str) -> bool:
    """
    Determine whether an SQL file is likely seed data or a migration.

    Args:
        path: File path
        content: File contents

    Returns:
        True if it is judged to be seed data; otherwise False.
    """
    if path.suffix.lower() != ".sql":
        return False

    migration_indicators = ["CREATE TABLE", "ALTER TABLE", "DROP TABLE", "ADD COLUMN"]
    if any(indicator in content for indicator in migration_indicators):
        return False

    insert_count = content.count("INSERT INTO")
    update_count = content.count("UPDATE ")

    if (insert_count + update_count) > 10:
        return True

    return False


def collect_files(repo_root: Path) -> List[Path]:
    """
    Collect files from repository, respecting .gitignore (including global).
    Uses git check-ignore for efficiency and accuracy.
    """
    # Collect all candidate files first
    candidate_files = []

    for p in repo_root.rglob("*"):
        if p.is_file() and p.stat().st_size <= MAX_FILE_SIZE and not is_binary(p):
            candidate_files.append(p)

    # Use batch git check-ignore for efficiency
    ignored_paths = _check_ignored_batch(repo_root, candidate_files)

    # Load summary.ignore patterns
    summary_ignore_patterns = load_summary_ignore(repo_root)
    summary_spec = None
    if summary_ignore_patterns:
        summary_spec = PathSpec.from_lines("gitwildmatch", summary_ignore_patterns)

    # Filter files
    files = []

    for p in candidate_files:
        rel_path = p.relative_to(repo_root)
        if ".tokuye" in rel_path.parts:
            continue
        # Skip if ignored by git
        if p in ignored_paths:
            continue

        # Skip if matches summary.ignore
        if summary_spec:
            try:
                if summary_spec.match_file(str(rel_path)):
                    continue
            except ValueError:
                continue

        # Special handling for SQL files
        if p.suffix.lower() == ".sql":
            content = p.read_text(errors="ignore")
            if is_likely_seed_data(p, content):
                continue

        files.append(p)

    return files


COMMENT_REGEX: Dict[str, re.Pattern] = {
    ".py": re.compile(r"^\s*#.*?$", re.M),
    ".js": re.compile(r"^\s*//.*?$", re.M),
    ".ts": re.compile(r"^\s*//.*?$", re.M),
    ".go": re.compile(r"^\s*//.*?$", re.M),
    ".java": re.compile(r"^\s*//.*?$", re.M),
    ".c": re.compile(r"^\s*//.*?$", re.M),
    ".cpp": re.compile(r"^\s*//.*?$", re.M),
}


def strip_comments(code: str, suffix: str) -> str:
    rx = COMMENT_REGEX.get(suffix)
    return re.sub(rx, "", code) if rx else code


SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),  # GCP
    re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH)"),  # Private key
]


def contains_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)


@dataclass
class FileSummary:
    path: str
    lines: int
    chars: int
    content: str
    mtime: float = 0


@dataclass
class RepoSummary:
    repo_root: str
    total_files: int
    total_chars: int
    generated_at: str
    files: List[FileSummary]
    tree: List[str]
    secret_detected: bool


def _get_last_modified_time(repo_root: Path, file_path: str) -> float:
    """Get last modified time of file"""
    full_path = repo_root / file_path
    if not full_path.exists():
        return 0
    return full_path.stat().st_mtime


def _get_existing_summary(
    repo_root: Path, output_style: str = "xml"
) -> Optional[Tuple[RepoSummary, Dict[str, float]]]:
    """
    Load existing repo-summary.xml and return RepoSummary object and file modification time dictionary
    Returns None if it doesn't exist
    """
    summary_path = repo_root / ".tokuye" / f"repo-summary.{output_style}"
    if not summary_path.exists():
        return None

    if output_style != "xml":
        # Currently only XML format is supported
        return None

    try:
        tree = ET.parse(summary_path)
        root = tree.getroot()

        # Get basic information
        repo_root_str = root.get("root", str(repo_root))
        generated_at = root.get(
            "generatedAt", datetime.datetime.utcnow().isoformat() + "Z"
        )

        # Get statistics
        stats_elem = root.find(".//stats")
        total_files = (
            int(stats_elem.get("totalFiles", "0")) if stats_elem is not None else 0
        )
        total_chars = (
            int(stats_elem.get("totalChars", "0")) if stats_elem is not None else 0
        )

        # Get tree information
        tree_elem = root.find(".//tree")
        tree_lines = (
            tree_elem.text.strip().split("\n")
            if tree_elem is not None and tree_elem.text
            else []
        )

        # Get file information
        files = []
        file_mtimes = {}
        for file_elem in root.findall(".//file"):
            path = file_elem.get("path", "")
            lines = int(file_elem.get("lines", "0"))
            chars = int(file_elem.get("chars", "0"))
            content = file_elem.text.strip() if file_elem.text else ""

            # Get last modified time from XML (0 if doesn't exist)
            mtime = float(file_elem.get("mtime", "0"))
            file_mtimes[path] = mtime

            files.append(
                FileSummary(
                    path=path,
                    lines=lines,
                    chars=chars,
                    content=content,
                    mtime=mtime,
                )
            )

        # Create RepoSummary object
        summary = RepoSummary(
            repo_root=repo_root_str,
            total_files=total_files,
            total_chars=total_chars,
            generated_at=generated_at,
            files=files,
            tree=tree_lines,
            secret_detected=False,
        )

        return summary, file_mtimes
    except Exception as e:
        logger.error(f"Error loading existing summary: {e}")
        return None


def summarize_repo(repo_root: Path, force_full_update: bool = False) -> RepoSummary:
    """
    Generate repository summary
    If force_full_update=True, ignore existing summary and rescan all files
    Otherwise, update only files changed since last generation
    """
    # Load existing summary
    existing_summary = (
        _get_existing_summary(repo_root) if not force_full_update else None
    )

    # Get current file list
    current_files = collect_files(repo_root)
    current_file_paths = {str(p.relative_to(repo_root)) for p in current_files}

    if existing_summary:
        existing_summary_obj, existing_file_mtimes = existing_summary
        existing_file_paths = {f.path for f in existing_summary_obj.files}

        # Identify added, removed, and updated files
        added_files = current_file_paths - existing_file_paths
        removed_files = existing_file_paths - current_file_paths
        potentially_updated_files = current_file_paths.intersection(existing_file_paths)

        # Identify updated files (compare last modified time)
        updated_files = set()
        for path in potentially_updated_files:
            current_mtime = _get_last_modified_time(repo_root, path)
            if (
                path not in existing_file_mtimes
                or current_mtime > existing_file_mtimes[path]
            ):
                updated_files.add(path)

        # Return existing summary if no changes
        if not added_files and not removed_files and not updated_files:
            logger.info("No changes detected, reusing existing summary")
            # Update only generation time
            existing_summary_obj.generated_at = (
                datetime.datetime.utcnow().isoformat() + "Z"
            )
            return existing_summary_obj

        # Update existing summary if there are changes
        logger.info(
            f"Updating summary: {len(added_files)} added, {len(removed_files)} removed, {len(updated_files)} updated"
        )

        # Convert existing file summaries to dictionary
        file_summaries_dict = {f.path: f for f in existing_summary_obj.files}

        # Remove deleted files
        for path in removed_files:
            if path in file_summaries_dict:
                del file_summaries_dict[path]

        # Process added and updated files
        total_chars = existing_summary_obj.total_chars
        secret_flag = existing_summary_obj.secret_detected

        for p in current_files:
            path = str(p.relative_to(repo_root))
            if path in added_files or path in updated_files:
                # Subtract character count for existing files
                if path in file_summaries_dict:
                    total_chars -= file_summaries_dict[path].chars

                # Create new file summary
                text = p.read_text(errors="ignore")
                secret_flag |= contains_secret(text)
                total_chars += len(text)

                # Get current last modified time
                current_mtime = _get_last_modified_time(repo_root, path)

                file_summaries_dict[path] = FileSummary(
                    path=path,
                    lines=text.count("\n") + 1,
                    chars=len(text),
                    content=text,
                    mtime=current_mtime,
                )

        # Rebuild directory tree
        tree_lines = _build_dir_tree(current_files, repo_root)

        # Return updated RepoSummary
        return RepoSummary(
            repo_root=str(repo_root),
            total_files=len(file_summaries_dict),
            total_chars=total_chars,
            generated_at=datetime.datetime.utcnow().isoformat() + "Z",
            files=list(file_summaries_dict.values()),
            tree=tree_lines,
            secret_detected=secret_flag,
        )

    # If no existing summary, scan all files
    logger.info(
        "No existing summary found or full update requested, scanning all files"
    )
    tree_lines = _build_dir_tree(current_files, repo_root)

    summaries = []
    total_chars = 0
    secret_flag = False

    for p in current_files:
        text = p.read_text(errors="ignore")
        secret_flag |= contains_secret(text)
        total_chars += len(text)

        path = str(p.relative_to(repo_root))
        current_mtime = _get_last_modified_time(repo_root, path)

        summaries.append(
            FileSummary(
                path=path,
                lines=text.count("\n") + 1,
                chars=len(text),
                content=text,
                mtime=current_mtime,
            )
        )

    return RepoSummary(
        repo_root=str(repo_root),
        total_files=len(summaries),
        total_chars=total_chars,
        generated_at=datetime.datetime.utcnow().isoformat() + "Z",
        files=summaries,
        tree=tree_lines,
        secret_detected=secret_flag,
    )


def _build_dir_tree(files: List[Path], root: Path) -> List[str]:
    """
    List both directories and files with hierarchical indentation.
    Example:
        src/
          cli/
            actions/
              defaultAction.ts
    """
    # Sort relative paths
    rels = sorted([p.relative_to(root) for p in files])

    tree_lines: list[str] = []
    last_dirs: list[str] = []

    for rel in rels:
        parts = rel.parts
        # Indent by directory hierarchy depth
        for depth in range(len(parts) - 1):
            dir_path = "/".join(parts[: depth + 1]) + "/"
            if len(last_dirs) <= depth or last_dirs[depth] != dir_path:
                tree_lines.append("  " * depth + dir_path)
                # Extend last_dirs when going deeper
                if len(last_dirs) <= depth:
                    last_dirs.append(dir_path)
                else:
                    last_dirs[depth] = dir_path
        # Output filename
        file_indent = "  " * (len(parts) - 1)
        tree_lines.append(f"{file_indent}{parts[-1]}")

    return tree_lines


def render_xml(summary: RepoSummary) -> str:
    """
    Generated XML contains:
      1. <about> - File overview
      2. <stats> - Count/character statistics
      3. <tree>  - Directory & file structure
      4. <files> - Full text in each <file path="...">
    All XML escaped, so standard DOM/SAX parsers can read without issues.
    """
    esc = xml_escape

    # 1) <about>
    about_block = textwrap.dedent(
        """\
        <about>
          <purpose>
            This file is a one-file compilation of the entire Git repository for LLM input.
            Sections:
              - &lt;stats&gt;  simple repository statistics
              - &lt;tree&gt;   directory &amp; file structure
              - &lt;files&gt;  full contents of every text file
          </purpose>

          <notes>
            - This file is read-only; edit the original repository files instead.
            - Files matched by .gitignore or default ignore patterns are excluded.
            - Binary files are excluded.
            - May contain sensitive information; handle with care.
          </notes>
        </about>"""
    ).rstrip()

    # 2) <stats>
    stats_block = (
        f'<stats totalFiles="{summary.total_files}" '
        f'totalChars="{summary.total_chars}" />'
    )

    # 3) <tree>
    tree_text = "\n".join(summary.tree)
    dir_block = f"<tree>\n{esc(tree_text)}\n</tree>"

    # 4) <files>
    file_blocks = []
    for f in summary.files:
        body = esc(f.content.rstrip())
        file_blocks.append(
            f'<file path="{esc(f.path)}" lines="{f.lines}" chars="{f.chars}" mtime="{f.mtime}">\n'
            f"{body}\n"
            f"</file>"
        )
    files_block = "<files>\n" + "\n".join(file_blocks) + "\n</files>"

    # 5) Wrap everything
    header = (
        f'<repoSummary generatedAt="{esc(summary.generated_at)}" '
        f'root="{esc(summary.repo_root)}">\n'
    )
    footer = "</repoSummary>"

    return "\n".join([header, about_block, stats_block, dir_block, files_block, footer])


@tool(
    name="repo_summarize",
    description="Scan repository and return summary in XML",
)
def repo_summarize(
    force_full_update: bool = False,
) -> str:
    """
    Traverse project root to generate XML summary and write to .tokuye/repo-summary.xml.
    Returns path string of output file.
    """
    # Check project root
    if settings.project_root is None:
        raise ValueError("project_root is not set in settings")

    root: Path = settings.project_root
    summary = summarize_repo(root, force_full_update)

    content = render_xml(summary)

    # Prepare output directory
    out_dir = root / ".tokuye"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write to file
    out_file = out_dir / "repo-summary.xml"
    out_file.write_text(content, encoding="utf-8")

    # Return result
    return f"Written summary to {out_file}"
