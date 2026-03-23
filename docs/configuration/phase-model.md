# Phase-Based Model Switching

!!! warning "Beta Feature"
    This feature is experimental and may change in future releases.

Tokuye supports using **two different models** depending on the current work phase.

## Phases

| Phase | Role | Recommended model |
|-------|------|-------------------|
| `thinking` | Investigation, analysis, planning, review | Larger / smarter model (e.g. Claude Sonnet) |
| `executing` | File writes, patches, commits, branch creation | Lighter / faster model (e.g. Claude Haiku) |

The agent calls the built-in `report_phase` tool to declare its current phase, and Tokuye automatically swaps the underlying Bedrock model accordingly.

## Configuration

Set `bedrock_plan_model_id` in your `.tokuye/config.yaml` to enable this feature:

```yaml
# Primary model — used for executing phase (file writes, patches, commits)
bedrock_model_id: global.anthropic.claude-sonnet-4-6

# Plan model — used for thinking phase (investigation, analysis, planning)
# When set, phase-based model switching is activated.
bedrock_plan_model_id: global.anthropic.claude-opus-4-6-v1

model_temperature: 0.2
```

When `bedrock_plan_model_id` is **not** set, the `report_phase` tool is still callable but becomes a no-op — the single model handles all phases as before.

## How It Works

1. On startup, Tokuye creates two `BedrockModel` instances: one for thinking, one for executing.
2. The agent starts each invocation on the **thinking** model.
3. When the agent calls `report_phase("executing")`, the model is swapped to the executing model mid-invocation.
4. Calling `report_phase("thinking")` switches back.
5. Token usage and cost tracking automatically use the correct cost table for each model.

## Notes

- Both models must be Claude models accessible via your AWS Bedrock configuration.
- Cost tracking requires that `bedrock_plan_model_id` contains one of the supported model name fragments (`claude-sonnet-4-6`, `claude-haiku-4-5`, `claude-opus-4-6`).
- The cost shown in the UI is an approximation based on the model active at the **end** of each invocation.
