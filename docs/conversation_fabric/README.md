# Conversation Fabric

This directory is the canonical entry point for active Conversation Fabric development.

## Branch model

- `main` is the stable production source of truth.
- `develop/conversation-fabric` is the single long-lived development branch for Conversation Fabric.
- temporary `work/conversation-*` branches are disposable validation branches only.
- the pre-reset divergent history is preserved on `archive/conversation-fabric-pre-rebase` and is not an active development line.
- `chat-bridge-state` and `operator-control` remain protected operational branches.

## Target architecture

The target path is intentionally single-plane:

```text
ChatGPT parent / Superchat
  -> GitHub durable control + evidence
  -> Local Agent deterministic control/execution
  -> host-ops deterministic capabilities
  -> narrow ChatGPT Browser Driver for child-chat UI lifecycle
  -> GitHub durable result/evidence
  -> parent reads and synthesizes
```

Hard invariants:

- GitHub is the durable control/evidence authority.
- Chat Bridge/browser DOM is transport only, never scheduler or workflow authority.
- Local Agent is deterministic and does not run a model loop.
- host-ops is a capability/effects layer, not a planner.
- child chats have no independent machine authority.
- `local-agent` execution remains disabled for the Stage 8 reasoning-child slice.
- no MCP server, direct OpenAI API reasoning loop, second scheduler/executor, Native Messaging control plane or abandoned event-wake path is part of the target architecture.

## Current milestone: Stage 8

Prove exactly one real reasoning child in the isolated DEV browser profile:

1. `seed`
2. `prepare`
3. `login`
4. `arm`
5. `run`
6. confirm one canonical `/c/<id>` child identity
7. persist matching `ChildRegistration` and `SpawnTransaction` evidence

Limits for this milestone:

- one parent
- one child request
- one browser spawn attempt
- dedicated DEV Chrome profile
- no Local Agent execution authority
- no fleet, scheduler, rollover or multi-child expansion
- fail closed on ambiguous post-submit browser state

## Canonical documents

1. `TARGET_PRODUCT_ARCHITECTURE.md` — target ownership and hard invariants.
2. `CURRENT_PLAN.md` — current branch state, exact Stage 8 scope and next action.
3. `DEV_LAB.md` — isolated development/runtime boundary.

Historical plans, audits and superseded architecture notes are preserved only on `archive/conversation-fabric-pre-rebase`.
