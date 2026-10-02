# Conversation Fabric — current execution plan

Status: Stage 8 automatic one-child milestone completed; current milestone is checkpoint and terminal recording.

## Current baseline

Production remains unchanged:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent v4.19.12
- Chat Bridge 0.6.2

Canonical development line:

- branch: `develop/conversation-fabric`
- accepted Stage 8 code checkpoint before documentation-only updates: `93fb65204db03c54d0080803d26266f3c06d777e`
- accepted commit: `Confirm spawn identity from owned route transition`
- exact-SHA CI run: `37022787748`
- CI result: all five jobs passed (`test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`)

Mac DEV checkout:

- `/Users/michal/local-agent-dev`

Preserved isolated live root/profile:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- browser profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`

Production Chrome is never a source profile.

## Stage 8 completion ledger

Proof22 is the automatic completion proof.

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- admitted code SHA: `93fb65204db03c54d0080803d26266f3c06d777e`
- request digest: `sha256:460bb68b76a73350718a9f091bf3b071cfa8762f3222030e52af58e8b392a79d`
- transaction: `spawn-92f4107c2bf0bdd6abd122c5ddcfaa6417691c576d811efc6a1973f59c676615`
- plan digest: `sha256:43581f5fc966859b7339ddbdb0cc24de26fbe3ec30841784bc851ebd322dc61a`
- canonical child: `https://chatgpt.com/c/6abfcdf9-8438-83eb-86da-1c4b209afc47`
- spawn attempt: `1`
- durable spawn state: `done`
- durable child state: `active`
- durable registration: matching
- bounded completion evidence: matching
- recovery/manual attach: not used
- production mutation: none

The bounded Chrome History check found exactly one canonical child URL in the transition window after the matching provisional route.

Stage 8 completion gate is therefore satisfied.

## Accepted browser identity model

Post-submit full bootstrap text is not a reliable DOM requirement because ChatGPT may collapse and lazily render long user messages.

The accepted chain of custody is:

```text
exact bootstrap in active composer immediately before click
  -> submitted claim bound to transaction/request/bootstrap digests
  -> supported provisional route observed
  -> same claimed tab
  -> canonical /c/<id>
  -> exactly one user turn
  -> matching durable registration + SpawnTransaction=done
```

Exact expanded DOM text remains a valid stronger path when available, but automatic completion no longer depends on it.

## Non-negotiable invariants

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- Chat Bridge remains a bounded browser actuator.
- child chats never receive independent machine execution authority.
- `local-agent` remains `execution_enabled=false` for reasoning-child browser work.
- no production Chrome/profile mutation.
- no Native Messaging control plane.
- no blind replay after a potentially submitted ambiguous effect.
- browser DOM is transport evidence, not durable workflow state.

## Current milestone — checkpoint and terminal recording

The existing lifecycle already defines:

```text
active
  -> terminal_pending_evidence
  -> terminal_recorded
  -> retired
```

Only the first two transitions are in scope now. Retirement is a later milestone.

The implementation must introduce the smallest durable terminal/checkpoint evidence contract for an already registered active child.

Required properties:

1. `active -> terminal_pending_evidence` remains an explicit durable transition.
2. `terminal_recorded` is impossible without durable terminal evidence.
3. evidence binds to the exact child request digest and canonical child registration.
4. identical recording is idempotent; conflicting recording fails closed.
5. writes serialize through the existing workflow execution lock.
6. evidence is bounded, schema-validated and restart-safe.
7. no browser effect is required to prove the deterministic storage/state contract.
8. no adoption/retirement behavior is introduced in this slice.

## Immediate execution plan

1. Audit the current conversation contracts, state machine, store implementation and tests before editing.
2. Audit existing durable evidence/checkpoint patterns elsewhere in the repository and reuse established primitives rather than inventing a second storage model.
3. Define the minimum terminal/checkpoint record schema and validation rules.
4. Add positive, idempotency, conflict, missing-registration/evidence and invalid-transition tests.
5. Implement the smallest store mutation API that atomically persists terminal evidence and advances lifecycle only when its preconditions hold.
6. Run focused tests on the Mac through `host-ops`.
7. Run repository/bridge verification appropriate to the diff.
8. Push one accepted checkpoint to `develop/conversation-fabric` and establish exact-SHA CI.
9. Only after this milestone passes may work continue to adoption and retirement.

## Ordered milestones after this one

1. adoption and retirement;
2. restart/recovery proof across every external-effect boundary;
3. manual lifecycle parity as a first-class fallback;
4. narrow Browser Driver promotion for child-chat lifecycle effects;
5. normalize the persistent DEV browser profile into a root-independent reusable location if still useful;
6. Superchat fleet/control layer;
7. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and broad Superchat automation remain out of scope.

For operational continuation use `docs/CURRENT_HANDOFF.md`. For longer-term ordering use `docs/DEVELOPMENT_PLAN.md`.
