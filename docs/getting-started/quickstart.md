# Quick Start

## Minimal Setup

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

tokuye --project-root .
```

## What Happens on First Run

1. Tokuye reads your `.tokuye/config.yaml`
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

- [Configuration](../configuration/project-config.md) — customize models, themes, and more
- [TUI Interface](../features/tui.md) — learn the UI controls
- [State Machine Mode](../features/state-machine-mode.md) — structured multi-agent workflow
