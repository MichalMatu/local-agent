# Conversation Fabric — unified development direction

Status: **superseded as a standalone target architecture**.

The canonical target-product direction is now:

- [`TARGET_PRODUCT_ARCHITECTURE.md`](TARGET_PRODUCT_ARCHITECTURE.md)

The canonical current implementation/checkpoint ledger remains:

- [`CURRENT_PLAN.md`](CURRENT_PLAN.md)

This file is intentionally kept as a stable historical path because earlier commits, chats and development checkpoints reference it. Its former detailed architecture is preserved in Git history through commit `6cc122791dabe3bd87e6c5f002f9528d25aafe7b` and earlier branch history.

## Non-negotiable current direction

Current development must preserve these target rules:

- one long-lived Operator Chat / Superchat in ordinary ChatGPT;
- ChatGPT remains the reasoning/planning layer;
- **GitHub-backed Local Agent contracts are the only control/evidence plane between ChatGPT reasoning and Local Agent execution**;
- **no MCP server is part of the target architecture**;
- **Local Agent does not replace ordinary ChatGPT reasoning with a direct OpenAI API model loop**;
- Local Agent remains deterministic control/execution and durable conversation-lifecycle infrastructure;
- `host-ops` becomes the internal deterministic tool runtime;
- Chat Bridge is retained only as a narrow ChatGPT Browser Driver for physical child-chat UI lifecycle operations;
- manual child creation/paste/attach remains a first-class fallback using the same durable Conversation Fabric contracts;
- per-repository execution bindings and durable evidence remain authoritative despite the single user-facing control surface;
- DOM/browser state is transport evidence only, never task/workflow/conversation authority.

MCP, direct OpenAI API reasoning and any parallel non-GitHub control channel may appear in historical documentation, but they are not current implementation options, fallbacks or future phases unless the user explicitly changes the canonical architecture.

Use `CURRENT_PLAN.md` only to answer what stage is currently implemented, verified or next. Its current Stage 8 browser work is compatible with the target only as bounded proof of the narrow child-chat lifecycle driver; it must not be interpreted as restoring Bridge ownership of planning, scheduling, repository routing or durable state.

Historical design details in prior versions of this file are evidence and rationale, not a second current architecture.
