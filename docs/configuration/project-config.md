# Project Configuration

Create a `.tokuye/config.yaml` in your project root to configure Tokuye.

## Configuration Resolution Order

Settings are resolved in the following order (later wins):

1. Pydantic defaults / `.env`
2. **Global config** — `$XDG_CONFIG_HOME/tokuye/config.yaml` (default: `~/.config/tokuye/config.yaml`)
3. **Project config** — `<project_root>/.tokuye/config.yaml`

> **Exception:** `mcp_servers` is **merged** across global and project configs instead of being replaced. See [MCP Support](mcp.md) for details.

## Full Reference

```yaml
# ---------------------------------------------------------------------------
# Model Configuration
# ---------------------------------------------------------------------------

# Primary model (used for executing phase / v1 mode)
bedrock_model_id: global.anthropic.claude-sonnet-4-6

# Embedding model for FAISS index
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0

# Model temperature (0.0 = deterministic, 1.0 = creative)
model_temperature: 0.2

# Plan model for thinking phase (enables phase-based model switching when set)
# See: configuration/phase-model.md
bedrock_plan_model_id: ""

# Model for repo-description generation (falls back to bedrock_model_id if unset)
bedrock_repo_description_model_id: ""

# ---------------------------------------------------------------------------
# State Machine Mode (v2)
# See: features/state-machine-mode.md
# ---------------------------------------------------------------------------

state_machine_mode: false

# Developer node model (falls back to bedrock_model_id if unset)
bedrock_impl_model_id: ""

# State Classifier node model (falls back to bedrock_model_id if unset)
bedrock_classifier_model_id: ""

# PR Creator node model (falls back to bedrock_model_id if unset)
bedrock_pr_model_id: ""

# ---------------------------------------------------------------------------
# Git Configuration
# ---------------------------------------------------------------------------

# Prefix for branches created by Tokuye
pr_branch_prefix: tokuye/

# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

# Directory to store session files (relative to project root)
strands_session_dir: sessions

# Maximum number of agent steps per turn
max_steps: 100

# ---------------------------------------------------------------------------
# UI Customization
# ---------------------------------------------------------------------------

# Agent character name (displayed in chat border and header)
name: Alice

# Textual theme name (see Textual docs for available themes)
theme: tokyo-night

# Language: "en" or "ja"
language: en

# ---------------------------------------------------------------------------
# Custom System Prompt
# ---------------------------------------------------------------------------

# Path to a custom system prompt markdown file
# Absolute, or relative to project root
# See: advanced/custom-prompt.md
system_prompt_markdown_path: ""

# ---------------------------------------------------------------------------
# MCP Servers
# See: configuration/mcp.md
# ---------------------------------------------------------------------------

mcp_servers: []
```

## Minimal Example

```yaml
bedrock_model_id: global.anthropic.claude-sonnet-4-6
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
strands_session_dir: sessions
name: Alice
```
