# Conversation Fabric

Conversation Fabric is the reasoning-child layer beneath one Superchat parent. This directory contains current acceptance/checkpoint material plus historical design evidence.

## Current branch model

- `main` — production source of truth.
- `chat-bridge-state` — operational Chat Bridge desired/runtime state.
- `operator-control` — operational Conversation Operator control/evidence.
- `work/*` — disposable short-lived candidate branches only.

There is no long-lived Conversation Fabric development branch in the current operating model. Historical `develop/*` or `archive/*` refs are not source of truth.

## Architecture boundary

```text
Superchat parent
  -> bounded reasoning-only child chats
  -> child evidence/results
  -> parent synthesis
  -> target repository .agent/tasks (only when execution is justified)
  -> deterministic Local Agent execution
```

GitHub owns durable control/evidence. Chat Bridge/browser is transport/lifecycle machinery. Children never receive machine execution authority.

## Read order for the next live proof

1. `../CURRENT_HANDOFF.md`
2. `CHECKPOINT_2026-10-04_SUPERCHAT_READY.md`
3. `CURRENT_PLAN.md`
4. `NEXT_CHAT_PROMPT.md`
5. `../GOLDEN_STANDARD.md`
6. `../OPERATIONS.md`

`SELF_DIAGNOSTIC_2026-10-04.md`, DEV-lab notes, old handoff prompts and implementation plans are historical evidence. Consult them only when investigating a specific failure; do not treat them as current instructions.
