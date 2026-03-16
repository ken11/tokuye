import logging
import os
import re
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
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    model_temperature: float = 0.2
    pr_branch_prefix: str = "tokuye/"
    max_steps: int = 100

    strands_session_dir: str = "sessions"

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


def load_yaml_config(settings_instance: Settings) -> Settings:
    """
    Load settings from .tokuye/config.yaml and update settings instance
    """
    if not settings_instance.project_root:
        raise ValueError("project_root must be set before loading YAML config")

    config_path = settings_instance.project_root / ".tokuye" / "config.yaml"

    # Load only if config.yaml exists
    if config_path.exists():
        with open(config_path, "r") as f:
            yaml_config = yaml.safe_load(f)

        # Overwrite with settings loaded from YAML
        if yaml_config:
            if "bedrock_model_id" in yaml_config:
                settings_instance.bedrock_model_id = yaml_config["bedrock_model_id"]
            if "bedrock_embedding_model_id" in yaml_config:
                settings_instance.bedrock_embedding_model_id = yaml_config[
                    "bedrock_embedding_model_id"
                ]
            if "model_temperature" in yaml_config:
                settings_instance.model_temperature = yaml_config["model_temperature"]
            if "pr_branch_prefix" in yaml_config:
                settings_instance.pr_branch_prefix = yaml_config["pr_branch_prefix"]
            if "strands_session_dir" in yaml_config:
                settings_instance.strands_session_dir = yaml_config[
                    "strands_session_dir"
                ]
            if "name" in yaml_config:
                settings_instance.name = yaml_config["name"]
            if "theme" in yaml_config:
                settings_instance.theme = yaml_config["theme"]
            if "mcp_servers" in yaml_config:
                mcp_configs = []
                for server_cfg in yaml_config["mcp_servers"]:
                    try:
                        # Expand ${ENV_VAR} references in env values
                        if "env" in server_cfg and isinstance(server_cfg["env"], dict):
                            server_cfg["env"] = {
                                k: _expand_env_vars(v)
                                for k, v in server_cfg["env"].items()
                            }
                        mcp_configs.append(
                            Settings.McpServerConfig(**server_cfg)
                        )
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(
                            f"Invalid MCP server config: {server_cfg}, error: {e}"
                        )
                settings_instance.mcp_servers = mcp_configs

    return settings_instance


settings = Settings()


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
            "Claude Sonnet 4.6, Claude Haiku 4.5, Claude Opus 4.6."
        )
