# Current handoff — Conversation Fabric Stage 8

Date: 2026-10-01

## Purpose

This is the continuation checkpoint after the Local Agent v4.19.11 / Chat Bridge 0.6.2 production release and the Conversation Fabric branch cleanup. Read this first, then follow the canonical development plan, the Stage 8 execution ledger and exact GitHub evidence.

## Production state

Production is established on `main` at:

- Local Agent: v4.19.11
- Chat Bridge: 0.6.2
- `main`: `0088f55ef37eecf26e0d4363f999797b9e340e96`
- tag `v4.19.11`: points to the same production commit

PR #122 is merged and the old release candidate branch has been removed. Production `main` is stable and is not part of the Stage 8 development work.

## Development state

Canonical Conversation Fabric development continues only on:

- `develop/conversation-fabric`

The cleaned Stage 8 code baseline was validated at:

- `96c536a145904ae46add407004d9914d5088e215`

That exact code baseline passed all five canonical CI gates: test, coverage, Python 3.14, macOS smoke and Bridge browser smoke.

The old divergent development history is preserved only as a safety archive:

- `archive/conversation-fabric-pre-rebase`

Operational branches remain separate and must not be used as development branches:

- `chat-bridge-state`
- `operator-control`

## Architecture decision

```text
Superchat / ordinary ChatGPT reasoning
          |
          v
GitHub control + evidence
          |
          v
Local Agent deterministic orchestration/execution
          +--> host-ops deterministic tools
          +--> narrow ChatGPT Browser Driver
```

Permanent boundaries:

- GitHub is the durable control/evidence plane.
- Chat Bridge is a narrow browser transport/actuator, not workflow authority.
- Local Agent remains deterministic and model-free.
- Child chats have no independent machine authority.
- `local-agent` remains `execution_enabled: false` for the Stage 8 reasoning-child slice.
- No second scheduler, executor or control plane.
- No direct OpenAI API model loop.
- No Native Messaging control plane or abandoned event-wake direction.
- No production Chrome profile mutation during the Stage 8 proof.

## Stage 8 current gate

The next milestone is exactly one real ChatGPT child in the isolated DEV profile.

Required operator sequence:

```text
seed -> prepare -> login -> arm -> run
```

Hard limits:

- one parent conversation;
- one reasoning child;
- one durable `ChildRequest`;
- one browser spawn attempt;
- one dedicated DEV Chrome profile;
- exact `MichalMatu/local-agent` checkout identity;
- clean DEV checkout and exact 40-character commit SHA;
- no Local Agent task execution;
- fail closed on ambiguous create/submit state.

Required proof before any lifecycle expansion:

- canonical child `https://chatgpt.com/c/<id>`;
- matching durable `ChildRegistration`;
- matching durable `SpawnTransaction=done`;
- bounded completion evidence tied to the admitted request/plan.

Do not start adoption, terminal, retirement, restart/recovery, fleet scheduling, multi-child fan-out or the larger acceptance campaign before this one-child proof succeeds.

## Documentation map

Read in this order before changing Stage 8 behavior:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/DEVELOPMENT_PLAN.md`
4. `docs/conversation_fabric/CURRENT_PLAN.md`
5. `docs/ARCHITECTURE.md`
6. `docs/GOLDEN_STANDARD.md`
7. `docs/GITHUB_BRIDGE_CONTROL.md`
8. `docs/AUTONOMOUS_CHAT_LOOP.md`
9. relevant Chat Bridge docs
10. host-ops repository rules only if host-ops becomes part of the bounded milestone

## Continuation rule

A new conversation must begin with an exact-head preflight of `develop/conversation-fabric` before any live browser effect. Confirm branch identity, clean intended scope, current CI evidence and the Stage 8 safety invariants. Do not mutate `main`, `chat-bridge-state`, `operator-control` or the archive branch as part of that preflight.

Exact GitHub branch/commit/CI evidence outranks remembered chat context or browser appearance.
