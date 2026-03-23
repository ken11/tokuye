# Custom System Prompt

Tokuye allows you to replace the built-in system prompt with your own Markdown file.

## Configuration

Set `system_prompt_markdown_path` in your `.tokuye/config.yaml`:

```yaml
# Absolute path
system_prompt_markdown_path: /home/user/prompts/my_agent.md

# Or relative to project root
system_prompt_markdown_path: .tokuye/my_prompt.md
```

## Template Variables

The following variables are automatically substituted in your prompt file:

| Variable | Value |
|----------|-------|
| `{project_root}` | Absolute path to the project root |
| `{title}` | Agent title (e.g. `# Alice - AI Development Support Agent`) |
| `{optional_name_rule}` | Name introduction rule (set when `name` is configured) |

Unknown placeholders (e.g. JSON examples with `{key}`) are left intact and not substituted.

## Example

```markdown
{title}

{optional_name_rule}

## Role

You are a specialized agent for the project at `{project_root}`.
Focus only on the backend API layer. Do not modify frontend files.

## Rules

- Always write tests for new functions
- Follow the existing code style
- Use conventional commits
```

## Notes

- When `system_prompt_markdown_path` is set, the built-in system prompt is completely replaced
- The language setting (`language: en` / `language: ja`) still affects variable substitution
- If the file does not exist, Tokuye will raise an error on startup
