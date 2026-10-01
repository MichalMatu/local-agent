# Local Agent development plan

Status: current product direction and milestone ordering for Conversation Fabric.

## Stable production baseline

Production remains Local Agent v4.19.11 / Chat Bridge 0.6.2 on:

- `main@0088f55ef37eecf26e0d4363f999797b9e340e96`

Stage 8 development must not mutate production `main` or the production Chrome profile.

## Product direction

The target is one user-visible Local Agent product centered on one long-lived Operator Chat / Superchat:

```text
User
  -> Operator Chat / Superchat
    -> GitHub durable control/evidence
      -> Local Agent deterministic orchestration
        -> host-ops deterministic Mac/host effects
        -> narrow ChatGPT browser actuator for child-chat lifecycle
      -> durable result/evidence
    -> Operator Chat synthesis
```

Permanent boundaries:

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- ChatGPT conversations remain the reasoning layer.
- Chat Bridge is a narrow browser transport/actuator, not workflow authority.
- Browser DOM state is transport evidence, not scheduler or durable workflow state.
- Child chats have no independent machine authority.
- `local-agent` remains `execution_enabled=false` for the Stage 8 reasoning-child slice.
- No second scheduler, executor or control plane.
- No direct OpenAI API model loop.
- No Native Messaging control plane for this architecture.

## Branch roles

| Branch | Role |
| --- | --- |
| `main` | production runtime/source of truth |
| `develop/conversation-fabric` | canonical Conversation Fabric development line |
| `work/conversation-*` | temporary bounded candidate branches only |
| `chat-bridge-state` | operational desired state, not development |
| `operator-control` | global operator safety/control, not development |
| `archive/conversation-fabric-pre-rebase` | historical safety archive only |

## Current milestone: Stage 8 one-child proof

Stage 8 is intentionally limited to proving one exact durable reasoning-child request can create one real ChatGPT child in an isolated DEV browser profile and persist matching durable evidence.

The operator sequence is fixed:

```text
seed -> prepare -> login -> arm -> run
```

Each invocation performs one authority step. Do not auto-chain.

Hard limits:

- one parent;
- one reasoning child;
- one durable `ChildRequest`;
- one browser spawn attempt per proof;
- one isolated DEV Chrome profile;
- exact clean repository checkout and source SHA;
- no Local Agent task execution by the child;
- no production Chrome/profile mutation;
- fail closed after any potentially submitted ambiguous external effect.

The current implementation checkpoint and exact next actions are intentionally not duplicated here. They are canonical in:

- `docs/CURRENT_HANDOFF.md`
- `docs/conversation_fabric/CURRENT_PLAN.md`

## Stage 8 completion gate

Do not move to the next lifecycle milestone until one fresh proof has all of:

- canonical child `https://chatgpt.com/c/<id>`;
- matching durable `ChildRegistration`;
- matching durable `SpawnTransaction=done`;
- bounded completion evidence tied to the exact admitted request/plan.

## After Stage 8

Only after the one-child proof succeeds, continue in this order:

1. checkpoint and terminal recording;
2. adoption and retirement;
3. restart/recovery proof across every external-effect boundary;
4. manual lifecycle parity as a first-class fallback;
5. narrow Browser Driver promotion for child-chat lifecycle effects;
6. Superchat fleet/control layer;
7. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling and large acceptance campaigns remain out of scope during Stage 8.

## Verification discipline

For every non-trivial Conversation Fabric change:

1. start from the exact canonical development head;
2. make the smallest bounded change on a temporary candidate branch;
3. run focused positive and negative tests;
4. use real browser/process evidence for browser boundaries;
5. use `host-ops` for all Mac-local operations;
6. require exact-candidate CI before promotion;
7. fast-forward only `develop/conversation-fabric` after validation;
8. update `docs/CURRENT_HANDOFF.md` whenever the active checkpoint changes;
9. remove obsolete candidate branches/worktrees after accepted promotion.

Exact GitHub state and durable local evidence outrank remembered chat context.
