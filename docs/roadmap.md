# Roadmap

## Current Limitations

| Limitation | Details |
|------------|---------|
| **Claude Only** | Currently supports Claude models only (via Bedrock). Other Bedrock models (Nova, Mistral) are supported in State Machine Mode for specific nodes. |
| **Titan Embeddings Only** | Uses Amazon Titan Embeddings v2 exclusively for FAISS indexing |
| **Cost Tracking** | Only supports ap-northeast-1 pricing table (use as reference only) |

## Roadmap

- [x] MCP (Model Context Protocol) client support
- [x] Phase-based model switching (thinking / executing)
- [x] State Machine Mode (v2) with specialized node agents
- [x] Custom system prompt support
- [ ] Slack integration for team collaboration
- [ ] Multi-region cost tracking
- [ ] Extended model support (non-Bedrock providers)
