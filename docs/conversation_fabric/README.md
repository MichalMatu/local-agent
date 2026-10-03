# Conversation Fabric

This directory contains the active Conversation Fabric design and Stage 8 execution documents.

## Branch model

- `main` — stable production source of truth.
- `develop/conversation-fabric` — single long-lived Conversation Fabric development branch.
- `work/conversation-*` — temporary validation/candidate branches only.
- `chat-bridge-state` and `operator-control` — operational branches, not development branches.
- `archive/conversation-fabric-pre-rebase` — historical safety archive only.

## Architecture boundary

```text
ChatGPT parent / Superchat
  -> GitHub durable control + evidence
  -> Local Agent deterministic orchestration
     -> host-ops for Mac/host effects
     -> narrow ChatGPT browser actuator for child-chat lifecycle
  -> durable result/evidence
  -> parent synthesis
```

Hard invariants:

- GitHub owns durable control/evidence.
- Local Agent remains deterministic and model-free.
- Chat Bridge/browser DOM is transport, not workflow authority.
- child chats have no independent machine authority.
- `local-agent` execution remains disabled for the Stage 8 reasoning-child slice.
- no second scheduler/executor, direct model loop or Native Messaging control plane is part of Stage 8.
- ambiguous external effects fail closed and are never blindly replayed.

## Current milestone

Stage 8 proves exactly one real reasoning child in an isolated DEV browser profile using:

```text
seed -> prepare -> login -> arm -> run
```

The milestone ends when one fresh request has:

- exactly one canonical `https://chatgpt.com/c/<id>`;
- matching durable `ChildRegistration`;
- matching durable `SpawnTransaction=done`;
- bounded completion evidence;
- no child execution authority;
- no production profile mutation.

## Read order

For a continuation session, read only the documents needed for the current task:

1. `../CURRENT_HANDOFF.md` — exact current checkpoint and immutable evidence.
2. `CURRENT_PLAN.md` — exact next implementation/test/promotion sequence.
3. `HANDOFF_PROMPT.md` — copy/paste bootstrap for a new implementation conversation.
4. `DEV_LAB.md` — Mac/DEV/profile/state isolation rules.
5. `TARGET_PRODUCT_ARCHITECTURE.md` — longer-lived ownership and architecture rationale.

For broader milestone ordering, use `../DEVELOPMENT_PLAN.md`.

Do not use archived plans or remembered chat history to infer current operational state. Exact GitHub state and durable DEV evidence are authoritative.
