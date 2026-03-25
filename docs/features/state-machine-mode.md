# State Machine Mode

State Machine Mode (v2) is a structured multi-agent workflow that replaces the single-agent v1 mode. Instead of one agent handling everything, specialized nodes handle each phase of development.

## Overview

```
User message
     │
     ▼
┌─────────────────┐
│ StateClassifier │  (lightweight LLM, stateless)
└────────┬────────┘
         │ determines next DevState
         ▼
┌────────────────────────────────────────────────┐
│                  Node Agents                   │
│                                                │
│  PLANNING          →  Planner                  │
│  IMPLEMENTING      →  Developer                │
│  PR_CREATING       →  PR Creator               │
│  REVIEWING         →  Reviewer                 │
│                                                │
│  (translation agents bridge between nodes)    │
└────────────────────────────────────────────────┘
```

## States

| State | Description |
|-------|-------------|
| `IDLE` | Waiting for user input |
| `PLANNING` | Planner analyzes the issue and creates a plan |
| `AWAITING_APPROVAL` | Waiting for user to approve the plan |
| `IMPLEMENTING` | Developer implements the approved plan |
| `AWAITING_REVIEW` | Waiting for user feedback after implementation |
| `PR_CREATING` | PR Creator creates a pull request |
| `SELF_REVIEWING` | PR Creator performs a self-review |
| `REVIEWING` | Reviewer reviews an existing PR |
| `AWAITING_REVIEW_APPROVAL` | Waiting for user to approve the review |
| `AWAITING_PR_FEEDBACK` | Waiting for user feedback on the PR |
| `AWAITING_REVIEW_FEEDBACK` | Waiting for user feedback on the review |

## Node Agents

Each node is a separate Strands Agent with its own system prompt, session history, and model.

### Planner

- **Model**: Primary model (`bedrock_model_id`)
- **Role**: Analyzes the issue, searches the codebase, and produces a structured implementation plan
- **Tools**: Repository analysis, file reading, issue management

### Developer

- **Model**: Implementation model (`bedrock_impl_model_id`, falls back to `bedrock_model_id`)
- **Role**: Implements the plan — creates branches, writes code, commits
- **Tools**: Full file management, git operations, patch tools
- **Note**: Receives instructions in English via a translation agent (supports Devstral and other code-focused models)

### PR Creator

- **Model**: PR model (`bedrock_pr_model_id`, falls back to `bedrock_model_id`)
- **Role**: Creates pull requests and performs self-reviews
- **Tools**: PR creation, PR review tools

### Reviewer

- **Model**: Primary model (`bedrock_model_id`)
- **Role**: Reviews existing PRs, posts inline comments, approves or requests changes
- **Tools**: PR review tools

## Translation Layer

Between nodes, Tokuye uses stateless translation agents to restructure outputs:

- **Plan → Developer**: Converts the Planner's output (possibly in Japanese) into English instructions for the Developer node
- **Developer → PR Creator**: Restructures the Developer's output into PR context

This allows each node to operate in its optimal format regardless of the user's language setting.

## Configuration

Enable State Machine Mode in your `.tokuye/config.yaml`:

```yaml
# Enable v2 state machine mode
state_machine_mode: true

# Primary model (Planner, Reviewer, translation agents)
bedrock_model_id: global.anthropic.claude-sonnet-4-6

# Developer node — use a code-focused model (optional)
bedrock_impl_model_id: mistral.devstral-2-123b

# State Classifier — use a lightweight model (optional)
bedrock_classifier_model_id: global.anthropic.claude-haiku-4-5-20251001-v1:0

# PR Creator node (optional)
bedrock_pr_model_id: amazon.nova-pro-v1:0
```

All `bedrock_*_model_id` fields fall back to `bedrock_model_id` if not set.

## State Indicators

The current state is displayed in the chat as a system message after each node completes:

```
[State: AWAITING_APPROVAL]
```

This lets you know what Tokuye is waiting for at each step.

## Typical Workflow

```
You:      # Issue — implement user authentication

[State: PLANNING]
Planner:  Here's my plan: 1) Add User model, 2) Add JWT middleware...

[State: AWAITING_APPROVAL]
You:      Looks good, go ahead

[State: IMPLEMENTING]
Developer: (creates branch, writes code, commits)

[State: AWAITING_REVIEW]
You:      Create a PR

[State: PR_CREATING]
PR Creator: Created PR #42 — "feat: add user authentication"

[State: AWAITING_PR_FEEDBACK]
You:      Self-review it

[State: SELF_REVIEWING → AWAITING_REVIEW]
Reviewer: Left 2 inline comments...
```

## Notes

- Each node maintains its own conversation history (session files are stored separately per node)
- Conversation history is summarized automatically to manage context length
- If the StateClassifier fails to parse a state, it stays in the current state
