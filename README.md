# Tokuye

https://github.com/user-attachments/assets/846b294d-b540-4220-8394-c0a9cb63984c

**Tokuye** (トクイェ) is an AI-powered development assistant agent that works alongside you like a friend. The name comes from the Ainu word meaning "friend" — reflecting our goal of creating a companion that supports your development journey.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Tokuye is an AI-powered development assistant that understands your entire project context. Instead of repeatedly copying code snippets, it automatically analyzes your repository and intelligently searches for relevant code to maintain consistency.

## 📖 Documentation

**[https://ken11.github.io/tokuye/](https://ken11.github.io/tokuye/)**

Full documentation including configuration, features, and advanced usage is available on the docs site.

## Quick Start

```bash
# 1. Install (macOS / Linux)
curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh

# 2. Set up AWS credentials (choose one)
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=ap-northeast-1
# or: export AWS_PROFILE=your_profile

# 3. Create global config (once, applies to all projects)
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye"
cat > "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye/config.yaml" << 'EOF'
bedrock_model_id: global.anthropic.claude-sonnet-4-6
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
name: Alice
EOF

# 4. Run in any project
tokuye --project-root /path/to/your/project
```

## Skills

Tokuye uses a **Skills** system to keep the system prompt lean and reduce token usage.
Skills are Markdown files (`SKILL.md`) that contain detailed instructions loaded on demand — only when the agent needs them.

### Default skills

Three skills are bundled with Tokuye:

| Skill | Description |
|---|---|
| `workflow` | Step-by-step work process (investigation → plan → implement → finalize) |
| `tool-usage` | Tool priority order and per-tool handling rules |
| `response-format` | Required response structure for all replies |

### Customising skills

To customise skills for your project, copy the bundled defaults to a local directory:

```bash
tokuye init-skills .tokuye/skills
```

Then point `skills_dir` at that directory in your `.tokuye/config.yaml`:

```yaml
skills_dir: .tokuye/skills
```

Edit the `SKILL.md` files freely — add project-specific conventions, coding standards, deployment procedures, etc.
You can also add entirely new skill directories (each needs a `SKILL.md` with YAML frontmatter).

### Skill format

```
.tokuye/skills/
  my-skill/
    SKILL.md        ← YAML frontmatter + Markdown instructions
```

```markdown
---
name: my-skill
description: One-line description of what this skill does and when to load it.
---

# My Skill

Instructions go here...
```

The `description` field is injected into the system prompt so the agent knows when to activate the skill.
Full instructions are only loaded when the agent calls the `skills` tool — keeping every-turn token cost low.

## Prerequisites

- **AWS Bedrock Access**: IAM credentials with Bedrock permissions

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh
```

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

MIT License - see LICENSE file for details

## Acknowledgments

Tokuye builds upon the excellent work of several open-source projects:

### Core Dependencies

- **[Strands Agents](https://strandsagents.com/latest/)** - AWS AI Agent Framework that powers Tokuye's agent architecture
- **[Textual](https://textual.textualize.io/)** - Beautiful TUI framework for the interactive terminal interface

### Code Attribution

Portions of Tokuye's code are derived from or inspired by the following MIT-licensed projects:

- **[langchain-community](https://github.com/langchain-ai/langchain-community)** (MIT License, LangChain)
  - File management toolkit (`file_management.py`)
  - Code segmentation and tree-sitter-based parsing (`repo_summary_rag/languages/`)
  - See [NOTICE.md](src/tokuye/tools/strands_tools/NOTICE.md) for detailed attribution

- **[langchain](https://github.com/langchain-ai/langchain)** (MIT License, LangChain)
  - Recursive text splitter with offset tracking (`repo_summary_rag/splitter.py`)
  - Based on `libs/text-splitters/langchain_text_splitters/character.py`
  - See [NOTICE.md](src/tokuye/tools/strands_tools/NOTICE.md) for detailed attribution

- **[Repomix](https://github.com/yamadashy/repomix)** (MIT License)
  - Repository summarization approach (`repo_summary.py`)
  - Inspiration for Claude-friendly XML output format
  - See [NOTICE.md](src/tokuye/tools/strands_tools/NOTICE.md) for detailed attribution

All derived code has been modified and adapted for Tokuye's architecture and requirements. We are grateful to the maintainers and contributors of these projects for making their work available under permissive licenses.

For complete license texts and detailed attribution, see [src/tokuye/tools/strands_tools/NOTICE.md](src/tokuye/tools/strands_tools/NOTICE.md).

---

**Note**: Cost estimates are approximate and based on ap-northeast-1 pricing. Please verify actual costs in your AWS billing dashboard.
