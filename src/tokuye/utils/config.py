import logging
import os
import re
import boto3
from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic_settings import BaseSettings


logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    project_root: Optional[Path] = None

    class McpServerConfig(BaseSettings):
        """Configuration for a single MCP server."""
        name: str
        type: str  # "sse" or "stdio"
        url: Optional[str] = None  # for sse
        command: Optional[str] = None  # for stdio
        args: Optional[List[str]] = None  # for stdio
        env: Optional[Dict[str, str]] = None  # for stdio
        allowed_tools: Optional[List[str]] = None  # allowlist of tool names
        rejected_tools: Optional[List[str]] = None  # denylist of tool names

    mcp_servers: List[McpServerConfig] = []

    language: str = "en"

    name: Optional[str] = ""

    theme: Optional[str] = "tokyo-night"

    bedrock_model_id: str = "global.anthropic.claude-sonnet-4-6"
    model_identifier: str = ""
    bedrock_plan_model_id: str = ""
    plan_model_identifier: str = ""
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"

    bedrock_repo_description_model_id: str = ""  # repo-description生成用; 未指定時はbedrock_model_idにフォールバック
    
    # --- State machine mode (v2) -----------------------------------------
    state_machine_mode: bool = False
    bedrock_impl_model_id: str = ""        # Developer node; falls back to bedrock_model_id
    impl_model_identifier: str = ""
    bedrock_classifier_model_id: str = ""  # State Classifier node; falls back to bedrock_model_id
    classifier_model_identifier: str = ""
    bedrock_pr_model_id: str = ""          # PR Creator node; falls back to bedrock_model_id
    pr_model_identifier: str = ""

    model_temperature: float = 0.2
    pr_branch_prefix: str = "tokuye/"
    max_steps: int = 100

    system_prompt_markdown_path: Optional[str] = ""

    strands_session_dir: str = ".tokuye/sessions"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


def _expand_env_vars(value: str) -> str:
    """Expand ``${VAR}`` references in *value* with environment variables.

    - ``${VAR}`` is replaced with the value of the environment variable ``VAR``.
    - If the variable is not set, it is replaced with an empty string and a
      warning is logged.
    - Literal text without ``${…}`` is returned unchanged.
    """

    def _replacer(match: re.Match) -> str:
        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value is None:
            logger.warning(
                "Environment variable '%s' referenced in config.yaml is not set; "
                "substituting empty string",
                var_name,
            )
            return ""
        return env_value

    return re.sub(r"\$\{([^}]+)}", _replacer, value)


def _get_global_config_path() -> Path:
    """Return the path to the global config file.

    Uses ``$XDG_CONFIG_HOME/tokuye/config.yaml`` if the environment variable
    is set, otherwise falls back to ``~/.config/tokuye/config.yaml``.
    """
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / "tokuye" / "config.yaml"


def _parse_mcp_servers(raw_list: list) -> List[Settings.McpServerConfig]:
    """Parse a list of raw MCP server dicts into ``McpServerConfig`` objects."""
    configs: List[Settings.McpServerConfig] = []
    for server_cfg in raw_list:
        try:
            if "env" in server_cfg and isinstance(server_cfg["env"], dict):
                server_cfg["env"] = {
                    k: _expand_env_vars(v)
                    for k, v in server_cfg["env"].items()
                }
            configs.append(Settings.McpServerConfig(**server_cfg))
        except Exception as e:
            logger.warning("Invalid MCP server config: %s, error: %s", server_cfg, e)
    return configs


def _apply_yaml_to_settings(
    settings_instance: Settings,
    yaml_config: dict,
    merge_mcp: bool = False,
) -> None:
    """Apply *yaml_config* values onto *settings_instance* in-place.

    When *merge_mcp* is ``True`` the ``mcp_servers`` list is **merged** with
    the existing value instead of replaced.  Servers whose ``name`` matches an
    existing entry are replaced; others are appended.  This allows a project
    config to override individual servers defined in the global config while
    keeping the rest.
    """
    simple_keys = [
        "bedrock_model_id",
        "bedrock_embedding_model_id",
        "bedrock_plan_model_id",
        "state_machine_mode",
        "bedrock_impl_model_id",
        "bedrock_repo_description_model_id",
        "bedrock_classifier_model_id",
        "bedrock_pr_model_id",
        "model_temperature",
        "pr_branch_prefix",
        "strands_session_dir",
        "name",
        "system_prompt_markdown_path",
        "theme",
    ]
    for key in simple_keys:
        if key in yaml_config:
            setattr(settings_instance, key, yaml_config[key])

    if "mcp_servers" in yaml_config:
        new_servers = _parse_mcp_servers(yaml_config["mcp_servers"])
        if merge_mcp and settings_instance.mcp_servers:
            # Build a dict keyed by server name from the existing list
            merged: dict[str, Settings.McpServerConfig] = {
                s.name: s for s in settings_instance.mcp_servers
            }
            # Project-side entries override by name; new names are appended
            for s in new_servers:
                merged[s.name] = s
            settings_instance.mcp_servers = list(merged.values())
        else:
            settings_instance.mcp_servers = new_servers


def load_yaml_config(settings_instance: Settings) -> Settings:  # noqa: C901
    """
    Load settings from global and project config.yaml files.

    Resolution order (later wins):
      1. Pydantic defaults / ``.env``
      2. Global config  — ``$XDG_CONFIG_HOME/tokuye/config.yaml``
      3. Project config — ``<project_root>/.tokuye/config.yaml``

    ``mcp_servers`` is special-cased: the project list is **merged** with the
    global list rather than replacing it.  See :func:`_apply_yaml_to_settings`.
    """
    if not settings_instance.project_root:
        raise ValueError("project_root must be set before loading YAML config")

    config_path = settings_instance.project_root / ".tokuye" / "config.yaml"

    # --- 1. Global config ------------------------------------------------
    global_path = _get_global_config_path()
    if global_path.exists():
        try:
            with open(global_path, "r") as f:
                global_cfg = yaml.safe_load(f)
            if global_cfg:
                _apply_yaml_to_settings(settings_instance, global_cfg)
                logger.info("Loaded global config from %s", global_path)
        except Exception as e:
            logger.warning("Failed to load global config (%s): %s", global_path, e)

    # --- 2. Project config (overrides global; mcp_servers are merged) -----
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                project_cfg = yaml.safe_load(f)
            if project_cfg:
                _apply_yaml_to_settings(
                    settings_instance, project_cfg, merge_mcp=True
                )
                logger.info("Loaded project config from %s", config_path)
        except Exception as e:
            logger.warning("Failed to load project config (%s): %s", config_path, e)

    return settings_instance


settings = Settings()


def _resolve_source_model_id(model_id: str) -> str:
    """Return the underlying foundation-model ID for an application inference profile.

    If *model_id* is the ARN of an application inference profile
    (``…:application-inference-profile/<id>``), call ``GetInferenceProfile``
    and return the ARN of the first source model so that the caller can
    perform normal model-name matching against it.

    For any other value (plain model ID, system-defined inference profile ARN,
    cross-region profile ID, …) the input is returned unchanged.
    """
    if "application-inference-profile/" not in model_id:
        return model_id

    try:
        client = boto3.client("bedrock")
        response = client.get_inference_profile(
            inferenceProfileIdentifier=model_id
        )
        models = response.get("models", [])
        if models:
            return models[0]["modelArn"]
        logger.warning(
            "GetInferenceProfile returned no models for %r; "
            "model_identifier will not be resolved",
            model_id,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Failed to resolve application inference profile {model_id!r}. "
            "Make sure the ARN is correct and the IAM role has "
            "'bedrock:GetInferenceProfile' permission."
        ) from exc

    return model_id


def validate_settings():
    if settings.project_root is None:
        raise ValueError(
            "project_root must be specified via the command line argument (e.g. --project-root)."
        )

    if settings.bedrock_embedding_model_id != "amazon.titan-embed-text-v2:0":
        raise ValueError(
            f"Unsupported bedrock_embedding_model_id: {settings.bedrock_embedding_model_id!r}. "
            "Currently only 'amazon.titan-embed-text-v2:0' is supported."
        )

    if settings.model_identifier == "":
        raise ValueError(
            "model_identifier must be specified. Supported models are: "
            "Claude Sonnet 4.6, Claude Haiku 4.5, Claude Opus 4.6, Mistral Devstral 2, Amazon Nova Pro."
        )
