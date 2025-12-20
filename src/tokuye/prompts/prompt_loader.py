from pathlib import Path

from tokuye.utils.config import settings


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
    prompt = prompt.format(
        project_root=settings.project_root,
        title=title,
        optional_name_rule=optional_name_rule,
    )

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
