# Conversation Fabric

Conversation Fabric is the reasoning-child layer beneath one Superchat parent. This directory contains current implementation/acceptance material plus historical design evidence.

## Current branch model

- `main` — production source of truth.
- `chat-bridge-state` — operational Chat Bridge desired/runtime state.
- `operator-control` — operational Conversation Operator control/evidence.
- `work/*` — disposable short-lived candidate branches only.

There is no long-lived Conversation Fabric development branch in the current operating model. Historical `develop/*` or `archive/*` refs are not source of truth.

## Architecture boundary

```text
operator's normal authenticated Chrome
  -> parent Superchat tab
  -> Chat Bridge
  -> bounded reasoning-only child tabs in the same Chrome session
  -> child evidence/results
  -> parent synthesis
  -> target repository .agent/tasks (only when execution is justified)
  -> deterministic Local Agent execution
```

GitHub owns durable control/evidence. Chat Bridge owns normal browser tab/content lifecycle. Children never receive machine execution authority.

Production child isolation is logical: exact tab id, canonical conversation URL, spawn transaction and request/bootstrap digests. It is not implemented by a second Chrome process or a separate browser profile.

Isolated Chromium remains valid for deterministic tests and CI only.

## Current implementation boundary

The existing live actuator still launches a Playwright persistent context. That path is now considered transitional and must not be used for the next production acceptance. The immediate implementation goal is to route the live child lifecycle through the installed Chat Bridge in the already authenticated primary Chrome session, reusing the existing `chrome.tabs`, `chrome.scripting`, spawn and content-script primitives.

## Read order

1. `../CURRENT_HANDOFF.md`
2. `CURRENT_PLAN.md`
3. `NEXT_CHAT_PROMPT.md`
4. `../GOLDEN_STANDARD.md`
5. `../OPERATIONS.md`

`CHECKPOINT_2026-10-04_SUPERCHAT_READY.md`, `SELF_DIAGNOSTIC_2026-10-04.md`, DEV-lab notes, isolated-profile material, old handoff prompts and implementation plans are historical evidence. Consult them only when investigating a specific failure; do not treat them as current instructions.
