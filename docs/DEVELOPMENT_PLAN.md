# Local Agent development plan

Status: current product direction and milestone ordering for Conversation Fabric.

## Stable production baseline

Production remains Local Agent v4.19.12 / Chat Bridge 0.6.2 on:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`

Conversation Fabric development must not mutate production `main` or the production Chrome profile without a separate explicit release decision.

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
- `local-agent` remains `execution_enabled=false` for reasoning-child browser work.
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

## Completed lifecycle milestones

### Stage 8 automatic one-child proof

- accepted CODE: `93fb65204db03c54d0080803d26266f3c06d777e` — `Confirm spawn identity from owned route transition`
- exact-SHA CI: `37022787748`, all five jobs passed
- Proof22 created exactly one canonical child automatically with matching durable request/registration/spawn completion evidence and no production mutation.

Do not repeat this spawn milestone. Historical ambiguous attempts remain recovery evidence and must never be blindly replayed.

### Checkpoint and terminal recording

- accepted CODE: `a16918d32bc366dbc9d8a8793669baa214d13620` — `Add durable child terminal records`
- exact-SHA canonical CI: `37036591713`, all five jobs passed

Proven lifecycle:

```text
active -> terminal_pending_evidence -> terminal_recorded
```

Terminal evidence is bounded, exact-request/registration-bound, persisted before state completion, retry-idempotent, conflict-fail-closed and reload-validated.

### Adoption and retirement

- accepted CODE: `e76dc4a114f750cc0beabdbb2ad626d41ff2e986` — `Add durable child adoption and retirement`
- exact-SHA canonical CI: `37054505079`, all five jobs passed

The accepted adoption/retirement contract is:

```text
terminal_recorded
  -> durable adoption record
  -> workflow reasoning node succeeded
  -> retired
```

The durable adoption record binds the exact child request digest, exact terminal-record digest, workflow ID and reasoning-node ID. It is persisted before workflow-node success so interruption is restart-recoverable. Identical semantic retries are idempotent, conflicts fail closed, and retirement requires both durable adoption and a succeeded bound workflow node. Reload validation enforces those invariants.

No browser effect was added by terminal or adoption/retirement slices.

Documentation-only commits may advance `develop/conversation-fabric`; always distinguish the accepted CODE checkpoint from a later docs-only head.

## Current milestone: restart/recovery proof across external-effect boundaries

The next goal is to prove that the complete proven single-child lifecycle is restart-safe at every external-effect boundary, not merely at the deterministic file-write boundaries already unit-tested.

The first step is a bounded read-only boundary inventory on accepted CODE `e76dc4a114f750cc0beabdbb2ad626d41ff2e986`.

The inventory must map, for each external effect:

- durable intent/checkpoint before effect;
- the effect itself;
- durable evidence/completion after effect;
- observable state after restart at every interruption point;
- whether retry is safe, prohibited, or must use recovery/attach;
- ambiguity/conflict handling;
- current test/live-proof coverage;
- smallest missing proof.

Priority boundaries include spawn/browser submission and canonical identity, durable registration/spawn completion, terminal recording, adoption/workflow advancement, and any real cleanup/retirement effect if one exists.

The audit may conclude that a boundary is already sufficiently proven by existing code/tests/evidence. Do not create a new live browser campaign unless a specific missing proof requires it.

The authoritative operational checkpoint is maintained in:

- `docs/CURRENT_HANDOFF.md`
- `docs/conversation_fabric/CURRENT_PLAN.md`

## Ordered milestones after restart/recovery proof

Continue in this order:

1. manual lifecycle parity as a first-class fallback;
2. narrow Browser Driver promotion for child-chat lifecycle effects;
3. normalize the persistent DEV browser profile into a root-independent reusable location if still useful;
4. Superchat fleet/control layer;
5. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and large acceptance campaigns remain out of scope until the corresponding lifecycle primitives are proven.

## Verification discipline

For every non-trivial Conversation Fabric change:

1. start from the exact canonical development CODE checkpoint, distinguishing later docs-only commits;
2. audit current contracts/evidence before changing behavior;
3. make the smallest bounded change;
4. add positive, negative, idempotency and failure/restart tests appropriate to the boundary;
5. use real browser/process evidence only when the boundary under test actually requires it;
6. use `host-ops` for all Mac-local operations;
7. use direct GitHub operations for repository-side changes;
8. establish exact-SHA CI before accepting a CODE checkpoint;
9. advance only `develop/conversation-fabric` after validation;
10. update durable handoff docs whenever the accepted checkpoint changes;
11. remove obsolete candidate branches/worktrees after accepted promotion when safe.

Exact GitHub state and durable local evidence outrank remembered chat context.
