# Tokuye

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

# 2. Create global config (once, applies to all projects)
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye"
cat > "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye/config.yaml" << 'EOF'
bedrock_model_id: global.anthropic.claude-sonnet-4-6
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
name: Alice
EOF

# 3. Run in any project
cd /path/to/your/project
tokuye --project-root /path/to/your/project
```

## Prerequisites

- **AWS Bedrock Access**: IAM credentials with Bedrock permissions

## Installation

```bash
# macOS / Linux — pre-built binary (recommended)
curl -fsSL https://raw.githubusercontent.com/ken11/tokuye/main/install.sh | sh

# Run directly via uvx (no install, requires uv)
uvx --from git+https://github.com/ken11/tokuye.git tokuye --project-root /path/to/your/project

# Install globally via uv tool (requires uv)
uv tool install git+https://github.com/ken11/tokuye.git
tokuye --project-root /path/to/your/project
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
