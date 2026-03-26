# Installation

## Binary Install (macOS / Linux)

The easiest way to install Tokuye. Downloads a pre-built binary — no Python or uv required.

```bash
curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh
```

The script auto-detects your OS and architecture (`darwin/linux` × `x86_64/arm64`) and installs the binary to `~/.local/bin/tokuye`.

**Install a specific version:**

```bash
VERSION=v0.1.0 curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh
```

**Install to a custom directory:**

```bash
INSTALL_DIR=/usr/local/bin curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh
```

!!! note "PATH"
    If `~/.local/bin` is not in your `PATH`, the script will print a reminder. Add the following to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):
    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    ```

---

## Quick Start with uvx (No Install)

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
strands_session_dir: .tokuye/sessions
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
