# Quick Start

## 1. Create a Global Config (once)

The global config applies to **all** your projects — you only need to do this once.

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

## 2. Run in Any Project

```bash
cd /path/to/your/project
tokuye --project-root .
```

That's it. No per-project setup required.

## Project-Specific Config (Optional)

If you need to override settings for a specific project (e.g. a different model or MCP servers), create a project config:

```bash
mkdir -p .tokuye
cat > .tokuye/config.yaml << 'EOF'
bedrock_model_id: global.anthropic.claude-opus-4-5
mcp_servers:
  - name: "my-mcp"
    type: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "."]
EOF
```

Project config values override the global config. `mcp_servers` are merged (not replaced).
See [Project Configuration](../configuration/project-config.md) for details.

## What Happens on First Run

1. Tokuye reads your global config (`~/.config/tokuye/config.yaml`) and, if present, the project config (`.tokuye/config.yaml`)
2. It builds a FAISS index of your repository (this takes a moment on first run)
3. The TUI chat interface launches in your terminal
4. You can start describing tasks immediately

## Example Workflow

```
You: # Issue

## Bug Description
The login form validation is not working properly when the email field is empty.
```

Tokuye will:

1. Analyze the issue
2. Search your codebase for relevant files
3. Propose a plan and wait for your approval
4. Create a branch, implement the fix, and open a PR
5. Optionally self-review the PR

## Next Steps

- [Global Configuration](../configuration/global-config.md) — shared settings across all projects
- [Project Configuration](../configuration/project-config.md) — per-project overrides
- [TUI Interface](../features/tui.md) — learn the UI controls
- [State Machine Mode](../features/state-machine-mode.md) — structured multi-agent workflow
