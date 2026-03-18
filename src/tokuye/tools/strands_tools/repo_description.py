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

    # Use custom model if specified, otherwise fall back to default
    model_id = settings.repo_description_model_id if settings.repo_description_model_id else settings.bedrock_model_id

    model = BedrockModel(
        model_id=model_id,
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