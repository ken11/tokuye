# Philosophy & Design Goals

## Why Tokuye?

### Stay in Your Terminal, Keep Your Editor

We built Tokuye because we wanted AI assistance without abandoning our familiar development environment. No need to switch to a specific IDE or learn a new editor — Tokuye runs in your terminal and works alongside Vim, Emacs, or whatever editor you prefer.

### AI as a Teammate, Not a Replacement

Tokuye is designed to fit into your existing Git workflow:

1. You describe the issue
2. AI creates a branch and implements changes
3. You review the PR and merge (or request changes)

No dramatic workflow changes. Just AI-powered assistance that respects how you already work.

### Project-Level Cost Management

AI development tools should be a project cost, not a personal expense. That's why Tokuye uses AWS Bedrock with IAM credentials — your organization can issue project-specific credentials and track costs per project/team. No need for individual subscriptions or personal credit cards.

### Key Differentiators

- **Terminal-First**: Works with your existing editor setup (Vim, Emacs, etc.)
- **Transparent Git Operations**: You see exactly what branches and commits are created
- **Enterprise-Friendly**: IAM-based access control, potential for VPC-internal deployment
- **Project Cost Allocation**: Costs tied to AWS projects, not individual developers

## When to Choose Tokuye

✅ **Good fit if you:**

- Prefer terminal-based workflows
- Want to keep using your favorite editor
- Need project-level cost tracking and IAM control
- Work in environments where AWS access is easier than new SaaS subscriptions

❌ **Consider alternatives if you:**

- Prefer tight IDE integration (Cursor might be better)
- Need a fully managed cloud sandbox (Devin might be better)

## Core Principles

### Context-Aware Development

Tokuye automatically understands your project structure and codebase before taking any action. Repository analysis tools are the foundation — not an afterthought.

### Security by Default

All file operations are sandboxed to the project root. `.gitignore` patterns are respected to prevent accidental exposure of sensitive files (e.g., `.env`).

### Cost Transparency

Real-time cost estimation is displayed during usage. Every token consumed is visible, broken down by input, output, cache creation, cache read, and embeddings.

## Why AWS Bedrock Only?

Tokuye exclusively supports AWS Bedrock for LLM access. This is a deliberate design choice:

- **Cost Ownership**: AI tool costs should be borne by the project, not the developer. AWS IAM allows organizations to issue project-specific credentials and track costs per project/team.
- **Enterprise-Friendly**: In many business environments, obtaining AWS IAM credentials is straightforward.
- **Access Control**: IAM policies provide fine-grained control over who can use which models.
- **Audit Trail**: CloudTrail integration for compliance and usage tracking.
- **No New Subscriptions**: Avoids the hassle of setting up new Anthropic or OpenAI subscriptions.
- **Simple Authentication**: Works with standard boto3 configuration (`AWS_ACCESS_KEY_ID`, `AWS_PROFILE`, etc.).
