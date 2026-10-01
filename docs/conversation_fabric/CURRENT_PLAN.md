# Conversation Fabric — current execution plan

Status: canonical implementation/checkpoint ledger for `develop/conversation-fabric`.

## Production baseline

Production remains stable on `main` at Local Agent v4.19.11 / Chat Bridge 0.6.2:

- `main`: `0088f55ef37eecf26e0d4363f999797b9e340e96`
- tag `v4.19.11`: same production commit

Production is not part of the Stage 8 development work.

## Development baseline

`develop/conversation-fabric` is the only long-lived development branch for Conversation Fabric.

The old divergent development head is preserved only as:

- `archive/conversation-fabric-pre-rebase`

The cleaned Stage 8 code baseline was promoted and validated at:

- `96c536a145904ae46add407004d9914d5088e215`

That exact code baseline passed all five canonical CI gates:

- test
- coverage
- Python 3.14
- macOS smoke
- Bridge browser smoke

Temporary `work/conversation-*` branches are validation candidates only and must be removed after accepted promotion. The Stage 8 rebase helper branch has already been removed.

Protected operational branches remain separate:

- `chat-bridge-state`
- `operator-control`

## Architecture invariants

- GitHub is the durable control/evidence plane.
- Chat Bridge is a narrow browser transport/actuator only.
- Browser/DOM state is not workflow, task or scheduler authority.
- Local Agent is the deterministic executor/control core.
- host-ops is a deterministic capability/effects layer.
- child chats have no independent machine authority.
- `execution_enabled` for `local-agent` remains false for the Stage 8 reasoning-child slice.
- no second scheduler, executor or control plane;
- no direct OpenAI API model loop;
- no Native Messaging control plane or abandoned event-wake direction;
- no production Chrome profile mutation during the Stage 8 proof.

## Stage 8 — bounded real-child proof

Goal: prove one exact durable reasoning-child request can create one real ChatGPT child in the isolated DEV browser profile, discover one canonical child URL and persist matching durable evidence without granting Local Agent execution authority.

Required operator sequence:

```text
seed -> prepare -> login -> arm -> run
```

Each invocation performs exactly one authority step. Do not auto-chain the sequence.

Required bounds:

- one parent;
- one reasoning child;
- one `ChildRequest`;
- one browser spawn attempt;
- one dedicated DEV Chrome profile;
- exact repository identity `MichalMatu/local-agent`;
- exact clean Git checkout and 40-character source SHA;
- no production Chrome profile mutation;
- no Local Agent task execution;
- fail closed on post-submit ambiguity.

Required durable proof before any later lifecycle expansion:

- canonical child `https://chatgpt.com/c/<id>` identity;
- matching `ChildRegistration`;
- matching `SpawnTransaction=done`;
- bounded completion evidence tied to the exact admitted request/plan.

## Active Stage 8 implementation

The active development line is built directly on the current production `main` baseline and contains the bounded additions needed for the proof:

- `local_agent/conversation/` durable child request/registration/spawn contracts and stores;
- `local_agent/development/` DEV lab plus `live_seed`, `live_slice`, `live_runner`, `live_flow`;
- `local_agent/workflow/` workflow contracts/stores required by the Stage 8 seed;
- Chat Bridge `worker_spawn.js` and `spawn_content.js`, with one service-worker import line;
- focused Python/browser tests and workflow fixtures.

The active line deliberately does not restore the old event-wake/native transport direction, old Chat Bridge runtime, later adoption/retirement/campaign modules or a second executor/control plane.

## Branch cleanup checkpoint — complete

Completed on 2026-10-01:

- confirmed stable production `main` baseline;
- archived old divergent development head at `archive/conversation-fabric-pre-rebase`;
- reset the active development line to current `main` before rebuilding Stage 8;
- rebuilt Stage 8 from current production instead of merging stale development history;
- restored required workflow method specs, fixtures and focused coverage tests;
- preserved current Chat Bridge 0.6.2 rather than downgrading to the old development Bridge;
- removed stale/superseded Conversation Fabric documentation from the active line;
- validated the promoted Stage 8 code baseline with the full five-job CI matrix;
- removed the temporary Stage 8 rebase helper branch.

## Next action

Before any real browser effect, a new implementation conversation must perform an exact-head preflight of `develop/conversation-fabric`:

1. confirm branch/head identity and relation to `main`;
2. confirm current CI evidence and no unexpected code drift;
3. confirm the isolated DEV checkout/profile and clean source state;
4. confirm `local-agent` remains `execution_enabled=false`;
5. confirm the Chat Bridge manifest has no Native Messaging permission/control path;
6. confirm one-child/one-spawn limits and fail-closed ambiguity handling;
7. only then begin `seed -> prepare -> login -> arm -> run`.

Stop after the one-child proof and review durable evidence before extending lifecycle behavior.

## After Stage 8 proof

Only after the one-child live proof succeeds may the next bounded lifecycle milestone be considered:

```text
checkpoint -> terminal -> adoption -> retirement -> restart/recovery
```

Fleet scheduling, multi-child fan-out, rollover and broader Superchat automation remain explicitly out of scope until the single-child lifecycle and recovery boundaries are proven.
