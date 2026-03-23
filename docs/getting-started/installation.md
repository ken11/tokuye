# Installation

## Quick Start with uvx (Recommended)

Run Tokuye directly without installation:

```bash
cd /path/to/your/project

# Create config directory
mkdir -p .tokuye

# Create config file
cat > .tokuye/config.yaml << EOF
bedrock_model_id: global.anthropic.claude-sonnet-4-6
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
strands_session_dir: sessions
name: Alice
EOF

# Run directly from GitHub
uvx --from git+https://github.com/ken11/tokuye.git tokuye --project-root /path/to/your/project
```

## Install as a Tool

Install Tokuye globally using `uv tool`:

```bash
# Install from GitHub
uv tool install git+https://github.com/ken11/tokuye.git

# Run anywhere
tokuye --project-root /path/to/your/project
```

## Development Setup

For contributors or local development:

```bash
# Clone the repository
git clone https://github.com/ken11/tokuye.git
cd tokuye

# Install dependencies and create virtual environment
uv sync

# Run with uv
uv run tokuye --project-root /path/to/your/project
```
