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

## Completed milestone: Stage 8 automatic one-child proof

Stage 8 proved that one exact durable reasoning-child request can automatically create one real ChatGPT child in an isolated persistent DEV browser profile and persist matching durable evidence without granting the child execution authority.

Accepted Stage 8 code checkpoint:

- `93fb65204db03c54d0080803d26266f3c06d777e` — `Confirm spawn identity from owned route transition`
- exact-SHA GitHub Actions run `37022787748`: all jobs passed

Completion proof22:

- request digest: `sha256:460bb68b76a73350718a9f091bf3b071cfa8762f3222030e52af58e8b392a79d`
- transaction: `spawn-92f4107c2bf0bdd6abd122c5ddcfaa6417691c576d811efc6a1973f59c676615`
- plan digest: `sha256:43581f5fc966859b7339ddbdb0cc24de26fbe3ec30841784bc851ebd322dc61a`
- canonical child: `https://chatgpt.com/c/6abfcdf9-8438-83eb-86da-1c4b209afc47`
- spawn attempt: `1`
- durable `SpawnTransaction=done`
- matching durable `ChildRegistration`
- child lifecycle at proof completion: `active`
- bounded completion evidence: matching
- manual attach/recovery: not used
- production profile/main mutation: none

The accepted post-submit identity model is a chain of custody from the exact composer text and submitted claim through the supported provisional route to the same claimed canonical child tab. Full expanded long-message DOM text is not required because ChatGPT may lazily render collapsed messages.

Historical ambiguous proofs remain recovery evidence and must never be replayed.

## Completed milestone: checkpoint and terminal recording

Accepted CODE checkpoint:

- `a16918d32bc366dbc9d8a8793669baa214d13620` — `Add durable child terminal records`
- exact-SHA canonical GitHub Actions run `37036591713`: all five jobs passed

This milestone proves the deterministic lifecycle path:

```text
active
  -> terminal_pending_evidence
  -> terminal_recorded
```

Accepted properties:

- entry into `terminal_pending_evidence` is an explicit durable state transition;
- `terminal_recorded` cannot exist without valid durable terminal evidence;
- terminal evidence is bounded, schema-validated and tied to the exact child request digest plus the canonical durable `ChildRegistration` and child URL;
- evidence references are non-empty, bounded and digest-addressed;
- identical semantic terminal recording is idempotent;
- conflicting terminal evidence fails closed;
- writes use the existing workflow execution lock;
- terminal evidence is persisted before terminal lifecycle state, making a failure between writes restart-recoverable;
- persisted request, registration, evidence and state relationships are revalidated on reload/restart;
- positive and negative tests cover missing registration/evidence, conflicts, invalid ordering, exact binding, idempotency, bounds, crash recovery and lock reuse;
- no adoption/retirement semantics and no new browser effect were introduced.

Implementation lives in:

- `local_agent/conversation/terminal.py`
- `local_agent/conversation/store.py`
- `tests/test_conversation_terminal.py`

Documentation-only commits may advance `develop/conversation-fabric`; always distinguish the accepted CODE checkpoint from a later docs-only head.

## Current milestone: adoption and retirement

Adoption and retirement are next. Their exact contract is not yet accepted and must be derived from the current repository rather than previous conversation memory.

Start with one bounded read-only preimplementation audit on the accepted CODE checkpoint. The audit should identify existing lifecycle/state/workflow meanings, required durable evidence or preconditions, transition ordering, idempotency/conflict behavior, reload/restart validation, and locking/atomic-write boundaries. It must also determine whether any browser effect is genuinely part of the boundary.

Only after that audit should the smallest implementation slice and focused tests be defined.

The authoritative operational checkpoint is maintained in:

- `docs/CURRENT_HANDOFF.md`
- `docs/conversation_fabric/CURRENT_PLAN.md`

## Ordered milestones after adoption and retirement

Continue in this order:

1. restart/recovery proof across every external-effect boundary;
2. manual lifecycle parity as a first-class fallback;
3. narrow Browser Driver promotion for child-chat lifecycle effects;
4. normalize the persistent DEV browser profile into a root-independent reusable location if still useful;
5. Superchat fleet/control layer;
6. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and large acceptance campaigns remain out of scope until the corresponding lifecycle primitives are proven.

## Verification discipline

For every non-trivial Conversation Fabric change:

1. start from the exact canonical development CODE checkpoint, distinguishing later docs-only commits;
2. audit the existing contract/store/evidence patterns before changing behavior;
3. make the smallest bounded change;
4. run focused positive and negative tests;
5. use real browser/process evidence only when the boundary under test actually requires it;
6. use `host-ops` for all Mac-local operations;
7. establish exact-candidate CI when required by the qualification/release gate and never claim it without recorded evidence;
8. advance only `develop/conversation-fabric` after validation;
9. update `docs/CURRENT_HANDOFF.md` whenever the active checkpoint changes;
10. remove obsolete candidate branches/worktrees after accepted promotion when safe.

Exact GitHub state and durable local evidence outrank remembered chat context.
