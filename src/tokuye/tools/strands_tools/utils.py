import logging
import sys
from pathlib import Path
from typing import List, Optional, Set

import pathspec
from git import Repo

logger = logging.getLogger(__name__)


def is_relative_to(path: Path, root: Path) -> bool:
    """Check if path is relative to root."""
    if sys.version_info >= (3, 9):
        # No need for a try/except block in Python 3.8+.
        return path.is_relative_to(root)
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


INVALID_PATH_TEMPLATE = (
    "Error: Access denied to {arg_name}: {value}."
    " Permission granted exclusively to the current working directory"
)


class FileValidationError(ValueError):
    """Error for paths outside the root directory."""


def get_validated_relative_path(root: Path, user_path: str) -> Path:
    """Resolve a relative path, raising an error if not within the root directory."""
    # Note, this still permits symlinks from outside that point within the root.
    # Further validation would be needed if those are to be disallowed.
    root = root.resolve()
    full_path = (root / user_path).resolve()

    if not is_relative_to(full_path, root):
        raise FileValidationError(
            f"Path {user_path} is outside of the allowed directory {root}"
        )
    return full_path


def _load_gitignore_spec(root: Path) -> Optional[pathspec.PathSpec]:
    """
    Load .gitignore (local + global) and return PathSpec.
    Used as fallback when git check-ignore is not available.
    """
    root = root.resolve()
    patterns: List[str] = []

    # Load local .gitignore
    gi = root / ".gitignore"
    if gi.exists():
        try:
            patterns += gi.read_text().splitlines()
        except Exception as e:
            logger.warning(f"Failed to read .gitignore: {e}")

    # Load global gitignore patterns
    global_patterns = _load_global_gitignore_patterns()
    patterns += global_patterns

    if not patterns:
        return None

    spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    return spec


def _load_global_gitignore_patterns() -> List[str]:
    """
    Load global gitignore patterns from common locations.

    Returns:
        List of gitignore patterns from global configuration
    """
    patterns: List[str] = []

    # Common global gitignore locations
    global_ignore_paths = [
        Path.home() / ".gitignore_global",
        Path.home() / ".config" / "git" / "ignore",
    ]

    for path in global_ignore_paths:
        if path.exists():
            try:
                content = path.read_text().splitlines()
                patterns += content
                logger.debug(f"Loaded {len(content)} patterns from {path}")
            except Exception as e:
                logger.warning(f"Failed to read global gitignore {path}: {e}")

    return patterns


def _is_ignored_by_git(root: Path, abs_path: Path) -> bool:
    """
    Check if path is ignored by git using git check-ignore command.
    Falls back to pathspec-based checking if git command fails.

    Args:
        root: Root directory of repository
        abs_path: Absolute path to check

    Returns:
        True if ignored, False otherwise
    """
    try:
        rel = abs_path.resolve().relative_to(root.resolve())
    except ValueError:
        return True

    rel_str = str(rel)

    if rel_str.startswith(".git/") or rel_str == ".git":
        return True
    # Special case: .tokuye directory should not be ignored
    if rel_str.startswith(".tokuye/") or rel_str == ".tokuye":
        return False

    # Try git check-ignore first
    try:
        repo = Repo(root)
        # git check-ignore returns the path if it's ignored, empty string otherwise
        result = repo.git.check_ignore(rel_str, with_exceptions=False).strip()
        return bool(result)
    except Exception as e:
        logger.debug(f"git check-ignore failed, falling back to pathspec: {e}")
        # Fallback to pathspec-based checking
        spec = _load_gitignore_spec(root)
        return spec.match_file(rel_str) if spec else False


def _check_ignored_batch(root: Path, paths: List[Path]) -> Set[Path]:
    """
    Check multiple paths at once using git check-ignore for efficiency.
    Falls back to pathspec-based checking if git command fails.

    Args:
        root: Root directory of repository
        paths: List of absolute paths to check

    Returns:
        Set of paths that are ignored
    """
    ignored: Set[Path] = set()

    # Filter out .tokuye paths first
    paths_to_check = []
    for p in paths:
        try:
            rel_str = str(p.resolve().relative_to(root.resolve()))
            if not (rel_str.startswith(".tokuye/") or rel_str == ".tokuye"):
                paths_to_check.append(p)
            if rel_str.startswith(".git/") or rel_str == ".git":
                ignored.add(p)
        except ValueError:
            ignored.add(p)

    if not paths_to_check:
        return ignored

    # Try git check-ignore with batch mode
    try:
        repo = Repo(root)
        rel_paths = [str(p.relative_to(root)) for p in paths_to_check]

        # git check-ignore returns only the ignored paths
        result = repo.git(c="core.quotepath=false").check_ignore(*rel_paths, with_exceptions=False).strip()
        if result:
            ignored_rel_paths = set(result.splitlines())
            for p in paths_to_check:
                if str(p.relative_to(root)) in ignored_rel_paths:
                    ignored.add(p)
    except Exception as e:
        logger.debug(f"git check-ignore batch failed, falling back to pathspec: {e}")
        # Fallback to pathspec-based checking
        spec = _load_gitignore_spec(root)
        if spec:
            for p in paths_to_check:
                try:
                    rel_str = str(p.relative_to(root))
                    if spec.match_file(rel_str):
                        ignored.add(p)
                except ValueError:
                    ignored.add(p)

    return ignored
