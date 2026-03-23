# Contributing

## How to Contribute

Contributions are welcome! Please feel free to submit issues or pull requests on [GitHub](https://github.com/ken11/tokuye).

## Development Setup

```bash
git clone https://github.com/ken11/tokuye.git
cd tokuye

# Install dependencies including dev extras
uv sync --extra dev

# Run linter
uv run ruff check src/

# Run formatter
uv run ruff format src/

# Run tests
uv run pytest
```

## License

MIT License — see [LICENSE](https://github.com/ken11/tokuye/blob/main/LICENSE) file for details.

---

## Acknowledgments

Tokuye builds upon the excellent work of several open-source projects.

### Core Dependencies

- **[Strands Agents](https://strandsagents.com/latest/)** — AWS AI Agent Framework that powers Tokuye's agent architecture
- **[Textual](https://textual.textualize.io/)** — Beautiful TUI framework for the interactive terminal interface

### Code Attribution

Portions of Tokuye's code are derived from or inspired by the following MIT-licensed projects:

- **[langchain-community](https://github.com/langchain-ai/langchain-community)** (MIT License, LangChain)
  - File management toolkit (`file_management.py`)
  - Code segmentation and tree-sitter-based parsing (`repo_summary_rag/languages/`)
  - See [NOTICE.md](https://github.com/ken11/tokuye/blob/main/src/tokuye/tools/strands_tools/NOTICE.md) for detailed attribution

- **[langchain](https://github.com/langchain-ai/langchain)** (MIT License, LangChain)
  - Recursive text splitter with offset tracking (`repo_summary_rag/splitter.py`)
  - Based on `libs/text-splitters/langchain_text_splitters/character.py`
  - See [NOTICE.md](https://github.com/ken11/tokuye/blob/main/src/tokuye/tools/strands_tools/NOTICE.md) for detailed attribution

- **[Repomix](https://github.com/yamadashy/repomix)** (MIT License)
  - Repository summarization approach (`repo_summary.py`)
  - Inspiration for Claude-friendly XML output format
  - See [NOTICE.md](https://github.com/ken11/tokuye/blob/main/src/tokuye/tools/strands_tools/NOTICE.md) for detailed attribution

All derived code has been modified and adapted for Tokuye's architecture and requirements. We are grateful to the maintainers and contributors of these projects for making their work available under permissive licenses.

For complete license texts and detailed attribution, see [NOTICE.md](https://github.com/ken11/tokuye/blob/main/src/tokuye/tools/strands_tools/NOTICE.md).
