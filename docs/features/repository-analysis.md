# Repository Analysis

Tokuye's repository analysis tools are the foundation of its context-aware assistance. Before writing a single line of code, Tokuye understands your entire project.

## repo-summary

Inspired by [Repomix](https://repomix.com/), `repo-summary` analyzes your entire repository and converts it to a Claude-friendly XML format.

- Traverses the project directory tree
- Respects `.gitignore` patterns
- Respects `.tokuye/summary.ignore` for additional exclusions
- Outputs a structured XML summary that the agent uses as context

The summary is stored at `.tokuye/repo-summary.xml` and regenerated when the agent detects changes.

## repo-summary-rag

`repo-summary-rag` pre-indexes your code using FAISS for fast semantic search.

### How It Works

1. Code files are parsed using [tree-sitter](https://tree-sitter.github.io/tree-sitter/) into function/class-level chunks
2. Each chunk is embedded using Amazon Titan Embeddings v2 (512-dimensional vectors)
3. Embeddings are stored in a FAISS index at `.tokuye/`
4. On subsequent runs, only changed files are re-indexed (differential update)

### Supported Languages

| Language | Parser |
|----------|--------|
| Python | `tree-sitter-python` |
| JavaScript | `tree-sitter-javascript` |
| TypeScript | `tree-sitter-typescript` |
| Go | `tree-sitter-go` |
| Ruby | `tree-sitter-ruby` |

### Semantic Chunking

Code is split at function and class boundaries, not arbitrary line counts. This means search results are always complete, meaningful units of code — not truncated snippets.

### Differential Updates

The index tracks file modification times. On each agent invocation, only files that have changed since the last index build are re-embedded. This keeps startup fast even on large projects.

## Excluding Files

Create a `.tokuye/summary.ignore` file to exclude specific paths from repository analysis:

```
# Exclude vendor directory
vendor/

# Exclude generated files
*.generated.ts
dist/

# Exclude large data files
data/*.csv
```

- One path pattern per line
- Supports glob patterns
- Applied in addition to `.gitignore`

See [CLI Usage & Exclusions](../advanced/usage.md) for more details.
