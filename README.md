# Tokuye

**Tokuye** (トクイェ) is an AI-powered development assistant agent that works alongside you like a friend. The name comes from the Ainu word meaning "friend" — reflecting our goal of creating a companion that supports your development journey.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Tokuye is an AI-powered development assistant that understands your entire project context. Instead of repeatedly copying code snippets, it automatically analyzes your repository and intelligently searches for relevant code to maintain consistency.

## Prerequisites

- **AWS Bedrock Access**: IAM credentials with Bedrock permissions
- **AWS Configuration**: Set up via environment variables or AWS CLI profile
  ```bash
  # Option 1: Environment variables
  export AWS_ACCESS_KEY_ID=your_key
  export AWS_SECRET_ACCESS_KEY=your_secret
  export AWS_DEFAULT_REGION=ap-northeast-1
  
  # Option 2: AWS Profile
  export AWS_PROFILE=your_profile
  ```
- **Python**: 3.10 or higher
- **uv**: Fast Python package installer ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))

## ⚠️ Important Notes

### First-Time Execution

- **FAISS Index Building**: On first run, Tokuye builds a FAISS index for semantic code search. This may take some time depending on your project size.

### Token Usage & Costs

- **High Token Consumption**: Tokuye reads and embeds repository code, which can consume significant tokens depending on project size.
- **Bug Loop Risk**: If bugs cause infinite loops or repeated operations, token usage will increase proportionally. Monitor your AWS Bedrock costs carefully.
- **Cost Tracking**: Real-time cost estimates are displayed in the UI (based on ap-northeast-1 pricing). Always verify actual costs in your AWS billing dashboard.

### Best Practices

- Start with smaller projects to understand token consumption patterns
- Use `.tokuye/summary.ignore` to exclude large or irrelevant directories (see Advanced Usage)

## Installation

### Quick Start with uvx (Recommended)

Run Tokuye directly without installation:

```bash
cd /path/to/your/project

# Create config directory
mkdir -p .tokuye

# Create config file
cat > .tokuye/config.yaml << EOF
bedrock_model_id: global.anthropic.claude-sonnet-4-5-20250929-v1:0
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
strands_session_dir: sessions
name: Alice
EOF

# Run directly from GitHub
uvx --from git+https://github.com/ken11/tokuye.git tokuye --project-root /path/to/your/project
```

### Install as a Tool

Install Tokuye globally using `uv tool`:

```bash
# Install from GitHub
uv tool install git+https://github.com/ken11/tokuye.git

# Run anywhere
tokuye --project-root /path/to/your/project
```

### Development Setup

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

## Quick Start Example

```bash
cd /path/to/your/project

# Create config directory
mkdir -p .tokuye

# Create config file
cat > .tokuye/config.yaml << EOF
bedrock_model_id: global.anthropic.claude-sonnet-4-5-20250929-v1:0
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
strands_session_dir: sessions
name: Alice
EOF

tokuye --project-root .
```

---

## Philosophy & Design Goals

Tokuye aims to be an intelligent development agent that **understands your entire project context** without requiring you to manually provide it. Instead of repeatedly copying code snippets or explaining your codebase, Tokuye automatically analyzes your repository and intelligently searches for relevant code to avoid duplication and maintain consistency.

### Why Tokuye?

**Stay in Your Terminal, Keep Your Editor**

We built Tokuye because we wanted AI assistance without abandoning our familiar development environment. No need to switch to a specific IDE or learn a new editor — Tokuye runs in your terminal and works alongside Vim, Emacs, or whatever editor you prefer.

**AI as a Teammate, Not a Replacement**

Tokuye is designed to fit into your existing Git workflow:
1. You describe the issue
2. AI creates a branch and implements changes
3. You review the PR and merge (or request changes)

No dramatic workflow changes. Just AI-powered assistance that respects how you already work.

**Project-Level Cost Management**

AI development tools should be a project cost, not a personal expense. That's why Tokuye uses AWS Bedrock with IAM credentials — your organization can issue project-specific credentials and track costs per project/team. No need for individual subscriptions or personal credit cards.

(Sorry, Google Cloud fans — we went with AWS this time! 😅)

**Key Differentiators:**

- **Terminal-First**: Works with your existing editor setup (Vim, Emacs, etc.)
- **Transparent Git Operations**: You see exactly what branches and commits are created
- **Enterprise-Friendly**: IAM-based access control, potential for VPC-internal deployment
- **Project Cost Allocation**: Costs tied to AWS projects, not individual developers

### When to Choose Tokuye

✅ **Good fit if you:**
- Prefer terminal-based workflows
- Want to keep using your favorite editor
- Need project-level cost tracking and IAM control
- Work in environments where AWS access is easier than new SaaS subscriptions

❌ **Consider alternatives if you:**
- Prefer tight IDE integration (Cursor might be better)
- Need a fully managed cloud sandbox (Devin might be better)

### Core Principles

- **Context-Aware Development**: Automatically understands your project structure and codebase
- **Repository Analysis First**: Powerful repository analysis tools are the foundation of intelligent assistance
- **Security by Default**: Respects `.gitignore` patterns to prevent accidental exposure of sensitive files (e.g., `.env`)
- **Cost Transparency**: Real-time cost estimation displayed during usage (currently supports ap-northeast-1 pricing)

### Key Features

#### 🔍 Repository Analysis Tools

- **repo-summary**: Inspired by [Repomix](https://repomix.com/), analyzes your entire repository and converts it to Claude-friendly XML format
- **repo-summary-rag**: Pre-indexes code using FAISS for semantic code search (tree-sitter implementation inspired by LangChain)
  - Supports Python, JavaScript, TypeScript, Go, Ruby via tree-sitter
  - Function/class-level semantic chunking
  - Differential index updates for efficiency

#### 💬 Interactive TUI

- Beautiful terminal chat interface powered by Textual
- Real-time token usage and cost tracking
- Session persistence and conversation summarization
- Customizable themes (see Textual documentation)

#### 🛠️ Development Tools

- **File Operations**: Read, write, search, copy, move, delete (respects `.gitignore`)
- **Git Integration**: Branch creation, commit management
- **Patch Application**: Automatic git diff patch application with multiple fallback strategies
- **Issue Management**: Save and recall issue content

## Technology Stack

- **LLM**: Claude Sonnet 4/4.5, Haiku 4.5, Opus 4.5 via AWS Bedrock
- **Embeddings**: Amazon Titan Embeddings v2 (512-dimensional vectors)
- **Agent Framework**: [Strands Agents](https://strandsagents.com/latest/) - AWS AI Agent Framework
- **Code Analysis**: tree-sitter with multi-language support
- **Vector Search**: FAISS for fast similarity search
- **UI**: Textual (TUI framework)

### Why AWS Bedrock Only?

Tokuye exclusively supports AWS Bedrock for LLM access. This isn't a limitation — it's a deliberate design choice aligned with our philosophy:

- **Cost Ownership**: AI tool costs should be borne by the project, not the developer. AWS IAM allows organizations to issue project-specific credentials and track costs per project/team.
- **Enterprise-Friendly**: In many business environments, obtaining AWS IAM credentials is straightforward
- **Access Control**: IAM policies provide fine-grained control over who can use which models
- **Audit Trail**: CloudTrail integration for compliance and usage tracking
- **No New Subscriptions**: Avoids the hassle of setting up new Anthropic or OpenAI subscriptions, which can be bureaucratically complex in some organizations
- **Simple Authentication**: Works with standard boto3 configuration (`AWS_ACCESS_KEY_ID`, `AWS_PROFILE`, etc.)

## Configuration

Create a `.tokuye/config.yaml` file in your project root:

```yaml
# Model Configuration
bedrock_model_id: global.anthropic.claude-sonnet-4-5-20250929-v1:0
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2

# Git Configuration
pr_branch_prefix: tokuye/

# Session Management
strands_session_dir: sessions

# UI Customization
name: Alice  # Agent character name
theme: tokyo-night  # Textual theme (see Textual docs for options)
```

## Advanced Usage

### Basic Commands

```bash
# If installed with uv tool
tokuye --project-root /path/to/your/project

# Or run directly with uvx
uvx --from git+https://github.com/ken11/tokuye.git tokuye --project-root /path/to/your/project

# With custom log level
tokuye --project-root /path/to/your/project --log-level debug

# Specify language (ja or en)
tokuye --project-root /path/to/your/project --language en
```

### Development Mode

If you're working on Tokuye itself:

```bash
cd /path/to/tokuye
uv run tokuye --project-root /path/to/your/project
```

### Issue Management

Tokuye provides a convenient way to save and recall issue descriptions:

- **Save Issue**: Start your message with `# Issue` and the content will be automatically saved to `.tokuye/current_issue.md`
- **Recall Issue**: Click the "Recall Issue" button in the UI to restore the saved issue content

Example:
```
# Issue

## Bug Description
The login form validation is not working properly...
```

### Excluding Files from Repository Summary

Create a `.tokuye/summary.ignore` file to exclude specific paths from repository analysis:
- Add one path pattern per line (supports glob patterns)
- Useful for excluding large generated files, vendor directories, or irrelevant code

## Current Limitations

- **Claude Only**: Currently supports Claude models only (via Bedrock)
- **Titan Embeddings Only**: Uses Amazon Titan Embeddings v2 exclusively
- **Cost Tracking**: Only supports ap-northeast-1 pricing table (use as reference only)

## Roadmap

- [ ] MCP (Model Context Protocol) client support
- [ ] Slack integration for team collaboration
- [ ] Custom system prompt configuration
- [ ] Multi-region cost tracking
- [ ] Extended model support

## Project Structure

```
src/tokuye/
├── agent/              # AI agent core implementation
├── textual/            # TUI interface
├── tools/              # Agent tools (file ops, git, RAG)
│   └── strands_tools/
│       └── repo_summary_rag/  # RAG search system
├── prompts/            # System prompt management
└── utils/              # Configuration & token tracking
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
