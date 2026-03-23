# Global Configuration

To avoid repeating the same settings in every project, create a global config file.

## Location

```
$XDG_CONFIG_HOME/tokuye/config.yaml
```

Default path (when `XDG_CONFIG_HOME` is not set):

```
~/.config/tokuye/config.yaml
```

## Setup

```bash
# Create the directory
mkdir -p "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye"

# Create the global config
cat > "${XDG_CONFIG_HOME:-$HOME/.config}/tokuye/config.yaml" << 'EOF'
bedrock_model_id: global.anthropic.claude-sonnet-4-6
model_temperature: 0.2
name: Alice

mcp_servers:
  - name: "github-mcp"
    type: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
EOF
```

## Precedence

Any key set in the global config applies to **all** projects. If the same key appears in a project config, the project value takes precedence — except for `mcp_servers`, which is merged.

| Scope | Path | Wins for scalar keys | `mcp_servers` behaviour |
|-------|------|---------------------|------------------------|
| Global | `$XDG_CONFIG_HOME/tokuye/config.yaml` | Only if project doesn't set it | Base list |
| Project | `<project_root>/.tokuye/config.yaml` | Always | Merged onto global list |

See [MCP Support](mcp.md#mcp-server-merging) for details on how `mcp_servers` merging works.
