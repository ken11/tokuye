# Tokuye

**Tokuye** (トクイェ) is an AI-powered development assistant agent that works alongside you like a friend. The name comes from the Ainu word meaning "friend" — reflecting our goal of creating a companion that supports your development journey.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

Tokuye is an AI-powered development assistant that understands your entire project context. Instead of repeatedly copying code snippets, it automatically analyzes your repository and intelligently searches for relevant code to maintain consistency.

## Key Features

- **Terminal-First**: Rich interactive TUI powered by Textual — no IDE required
- **Context-Aware**: Automatically analyzes your repository with FAISS-based semantic search
- **Git-Native**: Creates branches, commits, and PRs as part of the workflow
- **Cost-Transparent**: Real-time token usage and cost tracking per turn
- **MCP Support**: Extend capabilities via external MCP servers
- **State Machine Mode**: Structured multi-agent workflow (Planner → Developer → PR Creator → Reviewer)

## Install

=== "macOS / Linux (Recommended)"

    ```bash
    curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh
    ```

    This downloads the pre-built binary for your platform and installs it to `~/.local/bin`.

=== "uvx (no install)"

    ```bash
    uvx --from git+https://github.com/ken11/tokuye.git tokuye --project-root .
    ```

=== "uv tool"

    ```bash
    uv tool install git+https://github.com/ken11/tokuye.git
    ```

→ See [Installation](getting-started/installation.md) for all options and details.

## Quick Start

After installing, set up AWS credentials, create a global config, and run:

```bash
# Set up AWS credentials (choose one)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=ap-northeast-1
# or: export AWS_PROFILE=your_profile

# Create global config (once — applies to all projects)
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye"
cat > "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye/config.yaml" << 'EOF'
bedrock_model_id: global.anthropic.claude-sonnet-4-6
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
name: Alice
EOF

tokuye --project-root /path/to/your/project
```

→ See [Quick Start](getting-started/quickstart.md) for full details.

## Documentation

| Section | Description |
|---------|-------------|
| [Getting Started](getting-started/prerequisites.md) | Prerequisites, installation, and first run |
| [Configuration](configuration/project-config.md) | All config options, global config, MCP, phase-based models |
| [Features](features/tui.md) | TUI, repository analysis, state machine mode, issue management |
| [Advanced](advanced/usage.md) | CLI options, file exclusions, custom system prompts |
| [Philosophy](philosophy.md) | Why Tokuye exists and design goals |
| [Roadmap](roadmap.md) | Current limitations and future plans |
| [Contributing](contributing.md) | How to contribute, license, acknowledgments |
