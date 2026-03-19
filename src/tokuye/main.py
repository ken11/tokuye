import asyncio
import os
import signal
import sys
from pathlib import Path

import typer

from tokuye.textual.base_interface import ChatInterface
from tokuye.utils.config import load_yaml_config, settings, validate_settings, _resolve_source_model_id
from tokuye.utils.token_tracker import token_tracker

os.environ["BYPASS_TOOL_CONSENT"] = "true"
os.environ["EDITOR_DISABLE_BACKUP"] = "true"


def signal_handler(sig, frame):
    print("\nExiting application...")
    sys.exit(0)


def main(
    project_root: Path = typer.Option(
        ..., "--project-root", "-p", help="Root directory of the project"
    ),
    log_level: str = typer.Option(
        "info", "--log-level", "-l", help="Log level (debug, info, warning, error)"
    ),
    language: str = typer.Option("en", "--language", "-lang", help="Language"),
):
    """
    Start interactive AI development agent

    Args:
        project_root: Root directory of the project
        log_level: Log level (debug, info, warning, error)
    """
    project_root = project_root.absolute()

    if not project_root.exists() or not project_root.is_dir():
        typer.echo(f"Error: {project_root} is not a valid directory", err=True)
        raise typer.Exit(code=1)

    settings.project_root = project_root
    settings.language = language
    load_yaml_config(settings)

    _exec_source = _resolve_source_model_id(settings.bedrock_model_id)
    if "claude-sonnet-4-6" in _exec_source:
        settings.model_identifier = "sonnet-4-6"
    if "claude-haiku-4-5-" in _exec_source:
        settings.model_identifier = "haiku-4-5"
    if "claude-opus-4-6-" in _exec_source:
        settings.model_identifier = "opus-4-6"
    if "devstral-2" in _exec_source:
        settings.model_identifier = "devstral-2"
    if "nova-pro-v1" in _exec_source:
        settings.model_identifier = "nova-pro"

    if settings.bedrock_plan_model_id:
        _plan_source = _resolve_source_model_id(settings.bedrock_plan_model_id)
        if "claude-sonnet-4-6" in _plan_source:
            settings.plan_model_identifier = "sonnet-4-6"
        if "claude-haiku-4-5-" in _plan_source:
            settings.plan_model_identifier = "haiku-4-5"
        if "claude-opus-4-6-" in _plan_source:
            settings.plan_model_identifier = "opus-4-6"
        if "devstral-2" in _plan_source:
            settings.plan_model_identifier = "devstral-2"
        if "nova-pro-v1" in _plan_source:
            settings.plan_model_identifier = "nova-pro"

    validate_settings()
    token_tracker.set_cost_table()

    signal.signal(signal.SIGINT, signal_handler)

    textual_app = ChatInterface(
        settings.project_root,
        log_level=log_level,
        max_steps=settings.max_steps,
    )

    try:
        asyncio.run(textual_app.run_async())
    except KeyboardInterrupt:
        print("\nExiting due to keyboard interrupt...")
        sys.exit(0)


def cli():
    """CLI entry point for typer."""
    typer.run(main)


if __name__ == "__main__":
    cli()
