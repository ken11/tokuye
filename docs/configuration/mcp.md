# MCP Support

Tokuye supports [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) servers as additional tool providers. You can connect to external MCP servers to extend the agent's capabilities beyond the built-in tools.

## Configuration

Add an `mcp_servers` section to your `.tokuye/config.yaml`:

```yaml
mcp_servers:
  # SSE (Server-Sent Events) transport
  - name: "my-sse-server"
    type: "sse"
    url: "http://localhost:8000/sse"

  # stdio transport
  - name: "my-stdio-server"
    type: "stdio"
    command: "python"
    args: ["path/to/mcp_server.py"]
    env:                          # optional environment variables
      SOME_API_KEY: "your-key"

  # npx-based MCP server example
  - name: "github-mcp"
    type: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "ghp_xxxx"
```

## Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | ✅ | Display name for the server (used in logs) |
| `type` | string | ✅ | Transport type: `"sse"` or `"stdio"` |
| `url` | string | SSE only | URL of the SSE endpoint |
| `command` | string | stdio only | Command to execute |
| `args` | list | No | Command arguments |
| `env` | dict | No | Environment variables for the subprocess |
| `allowed_tools` | list | No | Allowlist of tool names to expose (if omitted, all tools are exposed) |
| `rejected_tools` | list | No | Denylist of tool names to hide |

## How It Works

1. On startup, Tokuye reads `mcp_servers` from `config.yaml`
2. Each configured server is connected (SSE or stdio)
3. If `allowed_tools` or `rejected_tools` is specified, tools are filtered before being passed to the agent
4. If a server fails to connect, it is skipped with a warning — built-in tools remain available
5. Connections are cleaned up on exit or conversation reset

## Tool Filtering

MCP servers often expose many tools, but you may want to restrict which ones the agent can use.

- **`allowed_tools`**: Only these tools will be available. All others are hidden.
- **`rejected_tools`**: These tools will be hidden. All others are available.
- When both are specified, `allowed_tools` is applied first, then `rejected_tools` removes from the allowed set.

```yaml
mcp_servers:
  - name: "github"
    type: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: "your-token"
    allowed_tools:
      - "get_pull_request"
      - "list_pull_requests"
      - "get_pull_request_diff"
    rejected_tools:
      - "merge_pull_request"
```

## MCP Server Merging

`mcp_servers` is the only config key that is **merged** between global and project configs. All other keys are simply overridden by the project config.

**How merging works:**

1. Global `mcp_servers` are loaded first as the base list.
2. Project `mcp_servers` are applied on top:
   - If a server has the **same `name`** as a global entry, the **project entry replaces it entirely**.
   - If a server has a **new `name`**, it is **appended** to the list.
   - Global entries whose `name` does not appear in the project config are **kept as-is**.

**Example:**

=== "Global config"

    ```yaml
    # ~/.config/tokuye/config.yaml
    mcp_servers:
      - name: "github"
        type: "stdio"
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-github"]
        env:
          GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"

      - name: "slack"
        type: "stdio"
        command: "npx"
        args: ["-y", "@anthropic/mcp-server-slack"]
        env:
          SLACK_BOT_TOKEN: "${SLACK_BOT_TOKEN}"
    ```

=== "Project config"

    ```yaml
    # .tokuye/config.yaml
    mcp_servers:
      # Override "github" — use different allowed_tools for this project
      - name: "github"
        type: "stdio"
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-github"]
        env:
          GITHUB_PERSONAL_ACCESS_TOKEN: "${GITHUB_TOKEN}"
        allowed_tools:
          - "get_pull_request"
          - "list_pull_requests"

      # Add a project-specific server
      - name: "filesystem"
        type: "stdio"
        command: "npx"
        args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp/sandbox"]
    ```

**Result:** The agent sees three MCP servers:

| Server | Source | Notes |
|--------|--------|-------|
| `github` | Project | Replaced — project version has `allowed_tools` |
| `slack` | Global | Kept — not mentioned in project config |
| `filesystem` | Project | Added — new entry |

## Full Example

```yaml
bedrock_model_id: global.anthropic.claude-sonnet-4-6
bedrock_embedding_model_id: amazon.titan-embed-text-v2:0
model_temperature: 0.2
pr_branch_prefix: tokuye/
strands_session_dir: .tokuye/sessions
name: Alice
theme: tokyo-night

mcp_servers:
  - name: "filesystem"
    type: "stdio"
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"]

  - name: "my-custom-server"
    type: "sse"
    url: "http://localhost:3000/sse"
```

!!! note
    MCP support requires the `strands-agents-tools[mcp]` extra, which is included by default. If you encounter import errors, ensure the `mcp` package is installed: `pip install 'mcp>=1.23.0,<2.0.0'`
