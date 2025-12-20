import datetime
import logging
import re
from pathlib import Path
from typing import Dict

from strands import Agent, tool
from strands.models import BedrockModel
from tokuye.tools.strands_tools.repo_summary import (FileSummary, RepoSummary,
                                                     _build_dir_tree,
                                                     collect_files, render_xml)
from tokuye.utils.config import settings
from tokuye.utils.token_tracker import token_tracker

logger = logging.getLogger(__name__)


def is_essential_file(path: Path) -> bool:
    """
    Determine if a file is essential for understanding the project

    Args:
        path: File path

    Returns:
        True if judged as an important file, False otherwise
    """
    # Configuration files, main source code, README, etc. are important
    essential_patterns = [
        r".*\.py$",
        r".*\.js$",
        r".*\.ts$",
        r".*\.vue$",
        r".*\.go$",
        r".*\.java$",
        r".*\.rb$",
        r".*\.c$",
        r".*\.cpp$",
        r".*\.h$",
        r".*\.md$",
        r".*\.rst$",
        r".*\.yaml$",
        r".*\.yml$",
        r".*\.json$",
        r".*Dockerfile$",
        r".*\.dockerignore$",
        r".*\.gitignore$",
        r".*\.github/.*",
    ]

    # Patterns that are clearly unnecessary
    non_essential_patterns = [
        r".*/node_modules/.*",
        r".*/vendor/.*",
        r".*/dist/.*",
        r".*/build/.*",
        r".*/tmp/.*",
        r".*/temp/.*",
        r".*/\.cache/.*",
    ]

    path_str = str(path)

    # Non-essential if matches unnecessary pattern
    if any(re.match(pattern, path_str) for pattern in non_essential_patterns):
        return False

    # Essential if matches important pattern
    return any(re.match(pattern, path_str) for pattern in essential_patterns)


def create_filtered_summary(repo_root: Path, detail_level: Dict) -> RepoSummary:
    """
    Generate filtered summary based on detail level

    Args:
        repo_root: Root directory of repository
        detail_level: Detail level settings (max_files, max_content_length)

    Returns:
        Filtered RepoSummary object
    """
    max_files = detail_level.get("max_files")
    max_content_length = detail_level.get("max_content_length")

    # Collect files
    all_files = collect_files(repo_root)

    # Sort by importance
    all_files.sort(key=lambda p: (0 if is_essential_file(p) else 1, p.stat().st_size))

    # Limit number of files
    if max_files and len(all_files) > max_files:
        files = all_files[:max_files]
    else:
        files = all_files

    # Generate summary
    summaries = []
    total_chars = 0
    secret_flag = False

    for p in files:
        text = p.read_text(errors="ignore")

        # Limit content length
        if max_content_length and len(text) > max_content_length:
            text = (
                text[:max_content_length]
                + f"\n\n/* ... remaining {len(text) - max_content_length} characters omitted ... */"
            )

        path = str(p.relative_to(repo_root))

        summaries.append(
            FileSummary(
                path=path,
                lines=text.count("\n") + 1,
                chars=len(text),
                content=text,
                mtime=p.stat().st_mtime,
            )
        )
        total_chars += len(text)

    return RepoSummary(
        repo_root=str(repo_root),
        total_files=len(summaries),
        total_chars=total_chars,
        generated_at=datetime.datetime.utcnow().isoformat() + "Z",
        files=summaries,
        tree=_build_dir_tree(files, repo_root),
        secret_detected=secret_flag,
    )


def generate_repo_description() -> str:
    """
    Load repo-summary.xml, send to LLM, and generate project purpose and description

    Returns:
        Generated project description
    """
    # Verify project root
    if settings.project_root is None:
        raise ValueError("project_root is not set in settings")

    return generate_repo_description_with_detail_control(settings.project_root)


def generate_description_from_summary(summary_path: Path) -> str:
    """
    Generate repository description from summary file

    Args:
        summary_path: Path to summary file

    Returns:
        Generated repository description
    """
    with open(summary_path, "r", encoding="utf-8") as f:
        repo_summary = f.read()

    model = BedrockModel(
        model_id=settings.bedrock_model_id,
        temperature=settings.model_temperature,
        streaming=False,
    )
    agent = Agent(model=model, callback_handler=None)

    # Create prompt
    prompt = f"""以下のリポジトリ要約を分析して、このプロジェクト/プロダクトの目的と概要を日本語で説明してください。

リポジトリ要約:
{repo_summary}

以下の形式で回答してください：

# プロジェクト概要

## 目的
このプロジェクトの主な目的を説明

## 機能
主要な機能や特徴を箇条書きで列挙

## 技術スタック
使用している主要な技術・ライブラリ・フレームワーク

## アーキテクチャ
プロジェクトの構造や設計について

回答は具体的で分かりやすく、技術的な詳細も含めてください。"""

    if settings.language == "en":
        prompt = f"""Analyze the following repository summary and explain, in English, the purpose and overview of this project/product.

Repository Summary:
{repo_summary}

Please answer in the following format:

# Project Overview

## Purpose
Explain the primary purpose of this project.

## Features
List the key features and characteristics in bullet points.

## Tech Stack
List the main technologies, libraries, and frameworks used.

## Architecture
Describe the project structure and design/architecture.

Make the answer specific and easy to understand, including relevant technical details."""

    # Send to LLM and generate description
    response = agent(prompt)
    description = response.message["content"][0]["text"]

    # Record token usage
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        input_tokens = response.usage_metadata.get("input_tokens", 0)
        output_tokens = response.usage_metadata.get("output_tokens", 0)
        token_tracker.add_repo_description_usage(input_tokens, output_tokens)
        logger.info(
            f"Repository description token usage: {input_tokens} input, {output_tokens} output"
        )

    return description


def generate_repo_description_with_detail_control(repo_root: Path) -> str:
    """
    Attempt to generate repo-description while gradually reducing detail level

    Args:
        repo_root: Root directory of repository

    Returns:
        Generated repository description
    """
    detail_levels = [
        {"max_files": 1000, "max_content_length": None},  # All files, full content
        {
            "max_files": 1000,
            "max_content_length": 5000,
        },  # All files, content limited
        {
            "max_files": 500,
            "max_content_length": 5000,
        },  # File count limited, content limited
        {"max_files": 200, "max_content_length": 2000},  # Further limited
        {"max_files": 100, "max_content_length": 1000},  # Minimal
    ]

    # Try normal method first
    try:
        # Use existing repo-summary.xml
        summary_path = repo_root / ".tokuye" / "repo-summary.xml"
        if summary_path.exists():
            description = generate_description_from_summary(summary_path)

            # Determine output path
            output_path = repo_root / ".tokuye" / "repo-description.md"

            # Save generated description to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(description)

            return f"Repository description generated and saved to: {output_path}"
    except Exception as e:
        logger.warning(f"Failed to generate description with full summary: {e}")

    # Try with gradually reduced detail level
    for level in detail_levels:
        try:
            logger.info(f"Trying with detail level: {level}")

            # Generate repo-summary with this detail level
            filtered_summary = create_filtered_summary(repo_root, level)
            temp_path = repo_root / ".tokuye" / "temp-filtered-summary.xml"
            temp_path.write_text(render_xml(filtered_summary))

            # Generate repo-description
            description = generate_description_from_summary(temp_path)

            # Delete temporary file
            temp_path.unlink()

            # Determine output path
            output_path = repo_root / ".tokuye" / "repo-description.md"

            # Save generated description to file
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(description)

            return f"Repository description generated and saved to: {output_path} (using filtered summary with {level})"
        except Exception as e:
            logger.warning(f"Failed with detail level {level}: {e}")
            continue

    # If all detail levels failed
    raise Exception("Failed to generate repo description at any detail level")


@tool(
    name="generate_repo_description",
    description="Generate project purpose and description using LLM based on repository summary and save to .tokuye/repo-description.md",
)
def generate_repo_description_tool() -> str:
    """
    Call existing generate_repo_description() to generate and save .tokuye/repo-description.md.
    Returns success/failure message string.
    """
    try:
        return generate_repo_description()
    except Exception as e:
        return f"Error generating repository description: {str(e)}"
