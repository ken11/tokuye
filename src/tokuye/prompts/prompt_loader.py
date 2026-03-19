from pathlib import Path

from tokuye.utils.config import settings


class _KeepUnknown(dict):
    """dict subclass that leaves unknown format placeholders intact.

    When ``str.format_map`` encounters a key not present in the mapping it
    calls ``__missing__``.  Returning ``"{key}"`` causes the original
    placeholder to be preserved in the output string instead of raising
    ``KeyError``.
    """

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def load_prompt(prompt_file: str) -> str:
    """
    Load prompt file and replace configuration variables

    Args:
        prompt_file: Prompt filename (including extension)

    Returns:
        str: Prompt string with variables replaced
    """
    # Get prompt file path
    prompt_dir = Path(__file__).parent
    prompt_path = prompt_dir / prompt_file

    # Error if file doesn't exist
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    # Load prompt file
    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt = f.read()

    if settings.language == "ja":
        if settings.name:
            title = f"# {settings.name} - AI開発支援エージェント"
            optional_name_rule = (
                f"以後、あなたは自分を {settings.name} として扱う。\n"
                "ただし、ユーザーへの返答で毎回名乗る必要はない（自然に振る舞う）。"
            )
        else:
            title = "# AI開発支援エージェント"
            optional_name_rule = ""
    elif settings.language == "en":
        if settings.name:
            title = f"# {settings.name} - AI Development Support Agent"
            optional_name_rule = (
                f"From now on, you will treat yourself as {settings.name}.\n"
                "However, you do not need to introduce yourself by name in every reply (behave naturally)."
            )
        else:
            title = "# AI Development Support Agent"
            optional_name_rule = ""

    # Replace configuration variables
    # Use format_map with _KeepUnknown so unknown placeholders (e.g. JSON
    # examples in prompt files) are left intact instead of raising KeyError.
    variables = _KeepUnknown({
        "project_root": str(settings.project_root),
        "title": title,
        "optional_name_rule": optional_name_rule,
    })
    prompt = prompt.format_map(variables)

    return prompt


def load_prompt_if_exists(prompt_file: str) -> str:
    """
    Load prompt file and replace configuration variables
    Returns None if file doesn't exist

    Args:
        prompt_file: Prompt filename (including extension)

    Returns:
        str: Prompt string with variables replaced, or None if file doesn't exist
    """
    # Get prompt file path
    prompt_dir = Path(__file__).parent
    prompt_path = prompt_dir / prompt_file

    # Return None if file doesn't exist
    if not prompt_path.exists():
        return None

    # Use normal load_prompt if it exists
    return load_prompt(prompt_file)


def load_custom_system_prompt(path: str) -> str:
    """
    Load a custom system prompt from an arbitrary file path.

    The path is resolved as follows:
      - If absolute, used as-is.
      - If relative, resolved against ``settings.project_root``.

    Variable substitution (``{project_root}``, ``{title}``,
    ``{optional_name_rule}``) is applied the same way as :func:`load_prompt`,
    but unknown placeholders are left intact instead of raising ``KeyError``.

    Args:
        path: Absolute or project-root-relative path to the markdown file.

    Returns:
        str: Prompt string with variables replaced.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    resolved = Path(path)
    if not resolved.is_absolute():
        resolved = Path(settings.project_root) / resolved

    if not resolved.exists():
        raise FileNotFoundError(
            f"Custom system prompt file not found: {resolved}"
        )

    with open(resolved, "r", encoding="utf-8") as f:
        prompt = f.read()

    if settings.language == "ja":
        if settings.name:
            title = f"# {settings.name} - AI開発支援エージェント"
            optional_name_rule = (
                f"以後、あなたは自分を {settings.name} として扱う。\n"
                "ただし、ユーザーへの返答で毎回名乗る必要はない（自然に振る舞う）。"
            )
        else:
            title = "# AI開発支援エージェント"
            optional_name_rule = ""
    else:
        if settings.name:
            title = f"# {settings.name} - AI Development Support Agent"
            optional_name_rule = (
                f"From now on, you will treat yourself as {settings.name}.\n"
                "However, you do not need to introduce yourself by name in every reply (behave naturally)."
            )
        else:
            title = "# AI Development Support Agent"
            optional_name_rule = ""

    # Use format_map with _KeepUnknown so unknown placeholders are left intact
    variables = _KeepUnknown({
        "project_root": str(settings.project_root),
        "title": title,
        "optional_name_rule": optional_name_rule,
    })
    return prompt.format_map(variables)
