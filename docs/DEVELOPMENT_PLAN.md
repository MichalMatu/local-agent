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
- child lifecycle: `active`
- bounded completion evidence: matching
- manual attach/recovery: not used
- production profile/main mutation: none

The accepted post-submit identity model is a chain of custody from the exact composer text and submitted claim through the supported provisional route to the same claimed canonical child tab. Full expanded long-message DOM text is not required because ChatGPT may lazily render collapsed messages.

Historical ambiguous proofs remain recovery evidence and must never be replayed.

## Current milestone: checkpoint and terminal recording

The next required lifecycle path is:

```text
active
  -> terminal_pending_evidence
  -> terminal_recorded
```

The existing state machine already reserves these states. The current milestone must add the smallest durable terminal/checkpoint evidence model and enforce the transition contract around it.

Completion requirements for this milestone:

- an active registered child can explicitly enter `terminal_pending_evidence`;
- `terminal_recorded` cannot be reached without valid durable terminal evidence;
- terminal evidence is schema-validated, bounded and tied to the exact child request digest and canonical registration;
- identical terminal evidence recording is idempotent;
- conflicting terminal evidence fails closed;
- mutations remain serialized by the existing workflow execution lock;
- persisted state/evidence survives restart and reload validation;
- positive and negative tests cover missing registration/evidence, conflicting evidence and invalid lifecycle ordering;
- no adoption/retirement semantics are introduced yet;
- no new browser effect is required for the deterministic storage/state proof.

The authoritative operational checkpoint is maintained in:

- `docs/CURRENT_HANDOFF.md`
- `docs/conversation_fabric/CURRENT_PLAN.md`

Documentation-only commits may advance `develop/conversation-fabric`; always distinguish the accepted code checkpoint from a later doc-only head.

## Ordered milestones after checkpoint and terminal recording

Continue in this order:

1. adoption and retirement;
2. restart/recovery proof across every external-effect boundary;
3. manual lifecycle parity as a first-class fallback;
4. narrow Browser Driver promotion for child-chat lifecycle effects;
5. normalize the persistent DEV browser profile into a root-independent reusable location if still useful;
6. Superchat fleet/control layer;
7. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and large acceptance campaigns remain out of scope until the corresponding lifecycle primitives are proven.

## Verification discipline

For every non-trivial Conversation Fabric change:

1. start from the exact canonical development code head;
2. audit the existing contract/store/evidence patterns before changing behavior;
3. make the smallest bounded change;
4. run focused positive and negative tests;
5. use real browser/process evidence only when the boundary under test actually requires it;
6. use `host-ops` for all Mac-local operations;
7. establish exact-candidate CI when required by the qualification/release gate and never claim it without recorded evidence;
8. advance only `develop/conversation-fabric` after validation;
9. update `docs/CURRENT_HANDOFF.md` whenever the active checkpoint changes;
10. remove obsolete candidate branches/worktrees after accepted promotion.

Exact GitHub state and durable local evidence outrank remembered chat context.
