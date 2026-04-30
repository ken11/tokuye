"""
Epic Mode (v3) configuration loader.

Reads `.tokuye/epic.yaml` from the Epic management project_root and exposes:
  - EpicConfig       : typed dataclass for the parsed config
  - load_epic_config : load and validate epic.yaml
  - resolve_repo_path: resolve a repo name to an absolute Path,
                       raising ValueError if the name is not in epic.yaml
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional

import yaml

from tokuye.utils.config import settings

logger = logging.getLogger(__name__)

EPIC_YAML_RELATIVE = ".tokuye/epic.yaml"


@dataclass
class RepoEntry:
    """A single repository entry from epic.yaml."""

    name: str
    path: Path  # absolute, resolved against epic project_root


@dataclass
class EpicConfig:
    """Parsed representation of .tokuye/epic.yaml."""

    project_root: Path
    repos: Dict[str, RepoEntry] = field(default_factory=dict)

    def repo_names(self) -> list[str]:
        return list(self.repos.keys())


# Module-level cache so we don't re-parse on every tool call.
_cached: Optional[EpicConfig] = None


def load_epic_config(force: bool = False) -> EpicConfig:
    """Load and validate `.tokuye/epic.yaml`.

    Uses ``settings.project_root`` as the Epic management directory.
    Results are cached; pass ``force=True`` to reload.

    Raises:
        FileNotFoundError: if epic.yaml does not exist.
        ValueError: if the YAML structure is invalid.
    """
    global _cached
    if _cached is not None and not force:
        return _cached

    if settings.project_root is None:
        raise ValueError("settings.project_root is not set")

    epic_yaml_path = settings.project_root / EPIC_YAML_RELATIVE
    if not epic_yaml_path.exists():
        raise FileNotFoundError(
            f"epic.yaml not found at {epic_yaml_path}. "
            "Epic Mode requires a .tokuye/epic.yaml file in the project root."
        )

    with open(epic_yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(f"epic.yaml must be a YAML mapping, got: {type(raw)}")

    repos_raw = raw.get("repos")
    if not repos_raw or not isinstance(repos_raw, dict):
        raise ValueError("epic.yaml must contain a 'repos' mapping with at least one entry")

    repos: Dict[str, RepoEntry] = {}
    for name, entry in repos_raw.items():
        if not isinstance(entry, dict) or "path" not in entry:
            raise ValueError(
                f"epic.yaml repos.{name} must have a 'path' key, got: {entry!r}"
            )
        raw_path = entry["path"]
        # Resolve relative paths against the Epic project_root
        resolved = (settings.project_root / raw_path).resolve()
        if not resolved.exists():
            logger.warning(
                "epic.yaml repos.%s path does not exist: %s", name, resolved
            )
        repos[name] = RepoEntry(name=name, path=resolved)

    config = EpicConfig(project_root=settings.project_root, repos=repos)
    _cached = config
    logger.info(
        "Loaded epic.yaml: %d repos (%s)",
        len(repos),
        ", ".join(repos.keys()),
    )
    return config


def resolve_repo_path(repo_name: str) -> Path:
    """Return the absolute Path for *repo_name* defined in epic.yaml.

    Raises:
        ValueError: if *repo_name* is not listed in epic.yaml.
    """
    config = load_epic_config()
    if repo_name not in config.repos:
        raise ValueError(
            f"Repository '{repo_name}' is not defined in epic.yaml. "
            f"Available repos: {config.repo_names()}"
        )
    return config.repos[repo_name].path
