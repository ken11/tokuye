from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic_settings import BaseSettings


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
