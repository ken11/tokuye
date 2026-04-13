# TUI Interface

Tokuye provides a rich terminal chat interface powered by [Textual](https://textual.textualize.io/).

## Layout

The interface is split into two panels:

```
┌─────────────────────────────────┬──────────────────────┐
│           Chat Panel            │     Side Panel       │
│                                 │                      │
│  [Assistant message]      [⎘]  │  💰 Cost display     │
│  [User message]           [⎘]  │                      │
│                                 │  System log          │
│  thinking...                    │                      │
│                                 │  Token log           │
│  [Text input area]              │                      │
│  [Send] [Reset] [Recall Issue]  │                      │
└─────────────────────────────────┴──────────────────────┘
```

## Chat Panel

### Message Display

Each message is rendered as a Markdown widget with a colored border:

| Sender | Border color | Border title |
|--------|-------------|--------------|
| You | Bright white | `You` |
| Assistant | Light sky blue | Agent name (e.g. `Alice`) |
| System | Violet | `System` |

### Copy Button

Every message has a **⎘** button in the top-right corner. Clicking it copies the full message content to your clipboard.

- Uses `pyperclip` if available, falls back to Textual's built-in clipboard API
- A `Copied!` notification appears briefly after copying

### Thinking Indicator

While the agent is processing, a **`thinking...`** label is displayed below the chat log. It disappears automatically when the agent finishes.

### Input Area

- **Text input**: Multi-line text area (12 rows). Press `Enter` for new lines.
- **Send** (`Ctrl+D`): Submit the message
- **Reset**: Clear the conversation and start a new session (agent state is reset)
- **Recall Issue**: Restore the last saved issue content into the input area (see [Issue Management](issue-management.md))

## Side Panel

### Cost Display

Shows the estimated AWS Bedrock cost for the current session:

```
💰 Estimated cost: $0.12
This amount is an estimate for ap-northeast-1.
Accuracy is not guaranteed.
```

### System Log

Displays internal logs from Tokuye (INFO, WARNING, ERROR level). Useful for debugging tool calls and agent behavior.

### Token Log

Shows per-turn token usage breakdown:

```
📊 Turn Token Usage: 4,231 total (3,890 input + 341 output)
   Cache: 3,200 created, 690 read | Cache Cost: $0.000412 (¥0.06)
   Embeddings: 1,024 tokens | Embedding Cost: $0.000030 (¥0.00)
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+D` | Send message |
| `Enter` | New line in input |
| `Ctrl+A` | Toggle Continuation Mode |
| `Ctrl+Q` | Quit |

## Continuation Mode

Continuation Mode allows you to continue working on an existing branch without creating a new one.

When enabled, every message you send is automatically appended with an instruction telling the agent to commit directly to the current branch instead of creating a new branch.

### How to use

1. Check out the branch you want to continue working on
2. Toggle Continuation Mode on with `Ctrl+A` (or click the **Continuation** switch in the input area)
3. Send your message as usual — the agent will commit to the current branch

### Behavior

- **ON**: Tokuye detects the current Git branch and appends the following note to every message:
  ```
  [Continuation mode] Do NOT create a new branch. Commit directly to the current branch '<branch-name>'.
  ```
- **OFF**: Normal behavior — the agent creates a new branch as needed

> **Note**: If the repository is in a detached HEAD state, Continuation Mode cannot be enabled and will be automatically disabled with an error message.

## Theme Customization

The TUI theme is controlled by the `theme` setting in your config:

```yaml
theme: tokyo-night
```

Any theme name supported by Textual can be used. See the [Textual documentation](https://textual.textualize.io/) for available themes.
