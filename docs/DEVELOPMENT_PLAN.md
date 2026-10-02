# Local Agent development plan

Status: current product direction and milestone ordering for Conversation Fabric.

## Stable production baseline

Production remains Local Agent v4.19.12 / Chat Bridge 0.6.2 on:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`

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
| `work/conversation-*` / `work/stage8-*` | temporary bounded candidate branches only |
| `chat-bridge-state` | operational desired state, not development |
| `operator-control` | global operator safety/control, not development |
| `archive/conversation-fabric-pre-rebase` | historical safety archive only |

## Current milestone: Stage 8 automatic one-child proof

Stage 8 is intentionally limited to proving one exact durable reasoning-child request can create one real ChatGPT child in an isolated persistent DEV browser profile and persist matching durable evidence automatically.

The operator sequence remains:

```text
seed -> prepare -> login -> arm -> run
```

Each invocation performs one authority step. Do not auto-chain.

Hard limits:

- one parent;
- one reasoning child;
- one durable `ChildRequest`;
- one browser spawn attempt per proof;
- one isolated persistent DEV Chrome profile;
- exact clean repository checkout and source SHA;
- no Local Agent task execution by the child;
- no production Chrome/profile mutation;
- fail closed after any potentially submitted ambiguous external effect.

A manually attached child is valid recovery evidence but does not complete the automatic Stage 8 gate unless the same fresh proof also has the required automatic terminal durable evidence.

The current accepted code checkpoint and proof authority are intentionally canonical in:

- `docs/CURRENT_HANDOFF.md`
- `docs/conversation_fabric/CURRENT_PLAN.md`

At the 2026-10-02 checkpoint, accepted code had reached `d65cbaacf70ee272e4263ab0e73428aa1376210e` (`Wait for canonical child identity stabilization`) and proof15 was freshly prepared but not armed or run. Later documentation-only commits may advance `develop/conversation-fabric`; verify code-vs-doc head before effects.

## Stage 8 completion gate

Do not move to the next lifecycle milestone until one fresh proof has all of:

- canonical child `https://chatgpt.com/c/<id>`;
- matching durable `ChildRegistration`;
- matching durable `SpawnTransaction=done`;
- bounded completion evidence tied to the exact admitted request/plan;
- no production profile mutation;
- no child execution authority.

No blind retry is allowed after submit may have happened. An ambiguous live effect must be inspected/recovered as the existing child, never replayed.

## After Stage 8

Only after the automatic one-child proof succeeds, continue in this order:

1. checkpoint and terminal recording;
2. adoption and retirement;
3. restart/recovery proof across every external-effect boundary;
4. manual lifecycle parity as a first-class fallback;
5. narrow Browser Driver promotion for child-chat lifecycle effects;
6. normalize the persistent DEV browser profile into a root-independent reusable location if still useful;
7. Superchat fleet/control layer;
8. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling and large acceptance campaigns remain out of scope during Stage 8.

## Verification discipline

For every non-trivial Conversation Fabric change:

1. start from the exact canonical development code head;
2. make the smallest bounded change on a temporary candidate branch;
3. run focused positive and negative tests;
4. use real browser/process evidence for browser boundaries;
5. use `host-ops` for all Mac-local operations;
6. establish exact-candidate CI when required by the qualification/release gate and never claim it without recorded evidence;
7. fast-forward only `develop/conversation-fabric` after validation;
8. update `docs/CURRENT_HANDOFF.md` whenever the active checkpoint changes;
9. remove obsolete candidate branches/worktrees after accepted promotion.

Exact GitHub state and durable local evidence outrank remembered chat context.