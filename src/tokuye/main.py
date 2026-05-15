import asyncio
import os
import signal
import sys
from pathlib import Path
from typing import Optional

import typer

from tokuye.tui.base_interface import ChatInterface
from tokuye.utils.config import load_yaml_config, settings, validate_settings, _resolve_source_model_id
from tokuye.utils.token_tracker import token_tracker

os.environ["BYPASS_TOOL_CONSENT"] = "true"
os.environ["EDITOR_DISABLE_BACKUP"] = "true"


def signal_handler(sig, frame):
    print("\nExiting application...")
    sys.exit(0)


def main(
    project_root: Optional[Path] = typer.Option(
        None, "--project-root", "-p", help="Root directory of the project"
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
    if project_root is None:
        project_root = Path.cwd()
    project_root = project_root.absolute()

    if not project_root.exists() or not project_root.is_dir():
        typer.echo(f"Error: {project_root} is not a valid directory", err=True)
        raise typer.Exit(code=1)

    settings.project_root = project_root
    settings.language = language
    load_yaml_config(settings)

    # --- Mode detection --------------------------------------------------
    # v3 Epic Mode: .tokuye/epic.yaml must exist; .gitignore check is skipped.
    # Normal mode:  .gitignore must exist.
    epic_yaml_path = project_root / ".tokuye" / "epic.yaml"
    if settings.epic_mode:
        if not epic_yaml_path.exists():
            typer.echo(
                f"Error: Epic Mode is enabled but .tokuye/epic.yaml not found in {project_root}",
                err=True,
            )
            raise typer.Exit(code=1)
    else:
        gitignore_path = project_root / ".gitignore"
        if not gitignore_path.exists():
            typer.echo(f"Error: .gitignore not found in {project_root}", err=True)
            raise typer.Exit(code=1)

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

    def _resolve_identifier(model_id: str) -> str:
        source = _resolve_source_model_id(model_id)
        if "claude-sonnet-4-6" in source:
            return "sonnet-4-6"
        if "claude-haiku-4-5-" in source:
            return "haiku-4-5"
        if "claude-opus-4-6-" in source:
            return "opus-4-6"
        if "devstral-2" in source:
            return "devstral-2"
        if "nova-pro-v1" in source:
            return "nova-pro"
        return ""

    if settings.bedrock_impl_model_id:
        settings.impl_model_identifier = _resolve_identifier(settings.bedrock_impl_model_id)
    else:
        settings.impl_model_identifier = settings.model_identifier

    if settings.bedrock_classifier_model_id:
        settings.classifier_model_identifier = _resolve_identifier(settings.bedrock_classifier_model_id)
    else:
        settings.classifier_model_identifier = settings.model_identifier

    if settings.bedrock_pr_model_id:
        settings.pr_model_identifier = _resolve_identifier(settings.bedrock_pr_model_id)
    else:
        settings.pr_model_identifier = settings.model_identifier

    validate_settings()
    token_tracker.set_cost_table()

    signal.signal(signal.SIGINT, signal_handler)

    if settings.epic_mode:
        app_title = "AI Dev Agent [Epic Mode v3]"
    else:
        app_title = "AI Dev Agent"

    textual_app = ChatInterface(
        settings.project_root,
        title=app_title,
        log_level=log_level,
        max_steps=settings.max_steps,
    )

    try:
        asyncio.run(textual_app.run_async())
    except KeyboardInterrupt:
        print("\nExiting due to keyboard interrupt...")
        sys.exit(0)


_app = typer.Typer(help="tokuye — AI development support agent")
_app.command(name="start", help="Start interactive AI development agent (default)")(main)


def _init_skills_command(
    dest: Path = typer.Argument(
        ...,
        help="Destination directory to copy the default skills into (e.g. .tokuye/skills)",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing skill directories"
    ),
):
    """Copy the bundled default skills to a local directory for customisation.

    After running this command, point skills_dir in your config.yaml at the
    destination directory and edit the SKILL.md files to suit your project.
    """
    import shutil

    src_skills = Path(__file__).parent / "skills"
    if not src_skills.exists():
        typer.echo(f"Error: bundled skills directory not found at {src_skills}", err=True)
        raise typer.Exit(code=1)

    dest = dest.expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    copied = []
    skipped = []
    for skill_dir in sorted(src_skills.iterdir()):
        if not skill_dir.is_dir():
            continue
        target = dest / skill_dir.name
        if target.exists() and not force:
            skipped.append(skill_dir.name)
            continue
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill_dir, target)
        copied.append(skill_dir.name)

    if copied:
        typer.echo(f"Copied skills to {dest}:")
        for name in copied:
            typer.echo(f"  ✓ {name}")
    if skipped:
        typer.echo("Skipped (already exist — use --force to overwrite):")
        for name in skipped:
            typer.echo(f"  - {name}")

    typer.echo(f"\nNext: set  skills_dir: {dest}  in your .tokuye/config.yaml")


_app.command(name="init-skills", help="Copy bundled default skills to a local directory for customisation")(_init_skills_command)


def cli():
    """CLI entry point."""
    # Backward-compatible: `tokuye [options]` without a subcommand name runs
    # `start` directly.  With a subcommand name (e.g. `tokuye init-skills`),
    # the Typer app dispatches normally.
    import sys
    subcommands = {"start", "init-skills"}
    if len(sys.argv) < 2 or sys.argv[1] not in subcommands:
        # No subcommand given — inject "start" so Typer routes to main()
        sys.argv.insert(1, "start")
    _app()


if __name__ == "__main__":
    cli()
