# CLI Usage & Exclusions

## CLI Options

```bash
tokuye [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--project-root` | *(required)* | Path to the project root directory |
| `--log-level` | `error` | Log level: `debug`, `info`, `warning`, `error` |
| `--language` | `en` | UI language: `en` or `ja` |

### Examples

```bash
# Basic usage
tokuye --project-root /path/to/your/project

# Run with uvx (no installation required)
uvx --from git+https://github.com/ken11/tokuye.git tokuye --project-root /path/to/your/project

# Enable debug logging
tokuye --project-root . --log-level debug

# Japanese UI
tokuye --project-root . --language ja
```

### Development Mode

If you're working on Tokuye itself:

```bash
cd /path/to/tokuye
uv run tokuye --project-root /path/to/your/project
```

## Excluding Files from Repository Summary

Create a `.tokuye/summary.ignore` file to exclude specific paths from repository analysis.

### Format

- One path pattern per line
- Supports glob patterns
- Lines starting with `#` are comments
- Applied in addition to `.gitignore`

### Example

```
# Exclude vendor directory
vendor/
node_modules/

# Exclude generated files
*.generated.ts
dist/
build/

# Exclude large data files
data/*.csv
fixtures/

# Exclude test snapshots
**/__snapshots__/
```

### When to Use

- Large generated files that don't need to be understood by the agent
- Vendor/dependency directories already excluded from version control
- Binary assets or data files
- Directories that are irrelevant to the current task

Excluding unnecessary files reduces token usage and speeds up index builds.
