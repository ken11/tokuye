# Prerequisites

## Required

### AWS Bedrock Access

Tokuye uses AWS Bedrock exclusively for LLM and embedding models. You need:

- An AWS account with Bedrock model access enabled
- IAM credentials with Bedrock permissions

Configure credentials via environment variables or AWS CLI profile:

```bash
# Option 1: Environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=ap-northeast-1

# Option 2: AWS Profile
export AWS_PROFILE=your_profile
```

### Python

Python 3.10 or higher is required.

### uv

Tokuye uses [uv](https://docs.astral.sh/uv/) as its package manager.

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### gh CLI (optional but recommended)

The [GitHub CLI](https://cli.github.com/) (`gh`) is required for PR creation, review, and issue operations.

```bash
# macOS
brew install gh

# Authenticate
gh auth login
```

---

## ⚠️ Important Notes

### First-Time Execution

On first run, Tokuye builds a FAISS index for semantic code search. This may take some time depending on your project size.

### Token Usage & Costs

- **High Token Consumption**: Tokuye reads and embeds repository code, which can consume significant tokens depending on project size.
- **Bug Loop Risk**: If bugs cause infinite loops or repeated operations, token usage will increase proportionally. Monitor your AWS Bedrock costs carefully.
- **Cost Tracking**: Real-time cost estimates are displayed in the UI (based on ap-northeast-1 pricing). Always verify actual costs in your AWS billing dashboard.

### Best Practices

- Start with smaller projects to understand token consumption patterns
- Use `.tokuye/summary.ignore` to exclude large or irrelevant directories (see [CLI Usage & Exclusions](../advanced/usage.md))
