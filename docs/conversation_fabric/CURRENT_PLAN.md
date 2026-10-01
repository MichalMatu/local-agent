# Conversation Fabric — current execution plan

Status: canonical implementation/checkpoint ledger for the cleaned `develop/conversation-fabric` line.

## Production baseline

Production remains `main` at Local Agent v4.19.11 / Chat Bridge 0.6.2. Production is stable and must not be changed as part of Stage 8 branch cleanup.

The old divergent `develop/conversation-fabric` history was preserved as `archive/conversation-fabric-pre-rebase`. The active development branch was reset to the current `main` baseline before Stage 8 promotion.

## Current development lane

`develop/conversation-fabric` is the only long-lived development branch for Conversation Fabric.

Temporary `work/conversation-*` branches are validation candidates only. They may be deleted after their accepted state is promoted back to `develop/conversation-fabric`.

Protected operational branches remain untouched:

- `chat-bridge-state`
- `operator-control`

## Architecture invariants

- GitHub is the durable control/evidence plane.
- Chat Bridge is a narrow browser transport/actuator only.
- browser/DOM state is not workflow, task or scheduler authority.
- Local Agent is the deterministic executor/control core.
- host-ops is a deterministic capability/effects layer.
- child chats have no independent machine authority.
- `execution_enabled` for `local-agent` remains false for the Stage 8 reasoning-child slice.
- no MCP server, direct OpenAI API model loop, second control plane, second scheduler/executor, Native Messaging control plane or abandoned event-wake direction is part of the target architecture.

## Stage 8 — bounded real-child proof

Goal: prove one exact durable reasoning-child request can create one real ChatGPT child in the isolated DEV browser profile, discover one canonical child URL and persist matching durable evidence without granting Local Agent execution authority.

Required sequence:

```text
seed -> prepare -> login -> arm -> run
```

Required bounds:

- one parent
- one reasoning child
- one `ChildRequest`
- one browser spawn attempt
- one dedicated DEV Chrome profile
- exact repository identity `MichalMatu/local-agent`
- exact clean Git checkout / 40-char source SHA
- no production Chrome profile mutation
- no Local Agent task execution
- fail closed on post-submit ambiguity

Required durable proof before any later lifecycle expansion:

- canonical child `/c/<id>` identity
- matching `ChildRegistration`
- matching `SpawnTransaction=done`
- bounded completion evidence tied to the exact admitted request/plan

## Current implementation candidate

The isolated Stage 8 candidate is built directly on the current `main` baseline and contains only the development-side additions needed for this proof:

- `local_agent/conversation/` durable child request/registration/spawn contracts and stores
- `local_agent/development/` DEV lab plus `live_seed`, `live_slice`, `live_runner`, `live_flow`
- `local_agent/workflow/` workflow contracts/stores required by the Stage 8 seed
- Chat Bridge `worker_spawn.js` and `spawn_content.js`, with one service-worker import line
- focused Python/browser tests and workflow fixtures

The candidate deliberately does not restore the old event-wake/native transport direction, old Chat Bridge runtime, later adoption/retirement/campaign modules, or a second executor/control plane.

## Branch cleanup checkpoint — 2026-10-01

Completed:

- confirmed stable production `main` baseline
- archived old divergent development head at `archive/conversation-fabric-pre-rebase`
- reset `develop/conversation-fabric` to current `main`
- rebuilt the Stage 8 candidate from `main` instead of merging old development history
- restored missing workflow method specs and workflow test fixtures
- preserved current Chat Bridge 0.6.2 rather than downgrading to the old development Bridge

Before promoting the candidate to `develop/conversation-fabric`:

1. CI must be green on the exact candidate SHA.
2. stale historical/superseded docs must stay in the archive branch, not the active development line.
3. final diff review must confirm no event-wake/native control path, production Chrome mutation or Local Agent execution authority was reintroduced.

## After Stage 8 proof

Only after the one-child live proof succeeds may the next bounded lifecycle milestone be considered: checkpoint -> terminal -> adoption -> retirement -> restart/recovery.

Fleet scheduling, multi-child fan-out, rollover and broader Superchat automation remain explicitly out of scope for Stage 8.
