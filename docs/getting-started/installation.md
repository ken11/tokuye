# Installation

## Binary Install (macOS / Linux)

The easiest way to install Tokuye. Downloads a pre-built binary — no Python or uv required.

```bash
curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh
```

The script auto-detects your OS and architecture (`darwin/linux` × `x86_64/arm64`).

**Default install location:**

| OS | Path |
|----|------|
| macOS (writable `/usr/local/bin`) | `/usr/local/bin/tokuye` |
| macOS (fallback) / Linux | `~/.local/bin/tokuye` |

**Install a specific version:**

```bash
VERSION=v0.1.0 curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh
```

**Install to a custom directory:**

```bash
INSTALL_DIR=/usr/local/bin curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh
```

!!! note "PATH"
    If the install directory is not in your `PATH`, the script will print a reminder.
    For `~/.local/bin`, add the following to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):
    ```bash
    export PATH="$HOME/.local/bin:$PATH"
    ```

## After Installation: Create a Global Config

The install script will print the exact commands, but here they are for reference.
This only needs to be done **once** — the config applies to all your projects.

```bash
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye"
cat > "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye/config.yaml" << 'EOF'
bedrock_model_id: global.anthropic.claude-sonnet-4-6
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
name: Alice
EOF
```

Then run Tokuye in any project:

```bash
cd /path/to/your/project
tokuye --project-root /path/to/your/project
```

See [Global Configuration](../configuration/global-config.md) for all available options.

---

## Quick Start with uvx (No Install)

Run Tokuye directly without installation:

```bash
# Create global config (once)
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye"
cat > "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye/config.yaml" << 'EOF'
bedrock_model_id: global.anthropic.claude-sonnet-4-6
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
name: Alice
EOF

# Run directly from GitHub in any project
cd /path/to/your/project
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
