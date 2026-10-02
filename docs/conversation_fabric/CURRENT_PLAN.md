# Conversation Fabric — current execution plan

Status: Stage 8 automatic one-child milestone completed; terminal/checkpoint preimplementation audit completed; implementation has not started successfully yet.

## Current baseline

Production remains unchanged:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent v4.19.12
- Chat Bridge 0.6.2

Canonical development line:

- branch: `develop/conversation-fabric`
- accepted Stage 8 CODE checkpoint before documentation-only updates: `93fb65204db03c54d0080803d26266f3c06d777e`
- accepted commit: `Confirm spawn identity from owned route transition`
- exact-SHA CI run: `37022787748`
- CI result: all five jobs passed (`test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`)

Documentation-only commits may advance `develop/conversation-fabric`; always distinguish the accepted CODE checkpoint from the current docs branch head before effects.

Mac DEV checkout:

- `/Users/michal/local-agent-dev`

Production checkout:

- `/Users/michal/local-agent`

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

Stage 8 completion gate is satisfied. Do not start another spawn campaign for this milestone.

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
5. writes serialize through the existing workflow/conversation mutation locking model.
6. evidence is bounded, schema-validated and restart/reload safe.
7. no browser effect is required to prove the deterministic storage/state contract.
8. no adoption/retirement behavior is introduced in this slice.

## Preimplementation audit checkpoint

The required read-only preimplementation audit has already completed successfully through `host-ops`:

- task/result: `conversation-terminal-evidence-preimplementation-audit-20261002-v1`
- status: `done`
- code audited: `93fb65204db03c54d0080803d26266f3c06d777e`
- DEV checkout was clean at audit start
- production `main` remained unchanged

The audit inspected:

- `local_agent/conversation/state.py` lifecycle transitions;
- conversation request/registration/state validation and storage;
- `ConversationStore.transition_state`, `register_child`, registration loading and atomic state writes;
- workflow store checkpoint/evidence patterns;
- workflow mutation/execution locking primitives;
- existing bounded atomic write helpers and tests.

The audit is evidence only; it made no repository changes.

## Failed implementation attempt — no effects

The first queued implementation task did not execute:

- task/result: `conversation-terminal-record-implementation-20261002-v1`
- status: `failed`
- failure: `invalid_task_file`
- parser error: `JSONDecodeError: Invalid control character at: line 12 column 2004 (char 2309)`
- `started_at=null`

Therefore no commands from that task ran and no source mutation from it is authoritative. Its payload may be inspected as a draft only. Do not replay it blindly; reconstruct the smallest implementation from current repository contracts and the completed audit.

## Immediate execution plan

1. Fetch fresh `main`, `develop/conversation-fabric`, `host-ops:agent-control` and daemon state.
2. Verify `/Users/michal/local-agent-dev` is clean and determine whether it is still on the accepted code checkpoint or only intentional documentation commits ahead.
3. Read the completed audit result before editing.
4. Re-inspect the exact current `contract.py`, `state.py`, `store.py` and `tests/test_conversation_store.py` surfaces identified by the audit.
5. Define the minimum terminal/checkpoint record schema and validation rules; do not treat the malformed implementation task as accepted design.
6. Add positive, idempotency, conflict, missing-registration/evidence and invalid-transition tests.
7. Implement the smallest store mutation API that atomically persists terminal evidence and advances lifecycle only when its preconditions hold.
8. Run focused tests on the Mac through `host-ops`.
9. Run repository/bridge verification appropriate to the actual diff.
10. Push one accepted CODE checkpoint to `develop/conversation-fabric` and establish exact-SHA CI.
11. Update durable handoff docs when the accepted checkpoint changes.
12. Only after this milestone passes may work continue to adoption and retirement.

## Ordered milestones after this one

1. adoption and retirement;
2. restart/recovery proof across every external-effect boundary;
3. manual lifecycle parity as a first-class fallback;
4. narrow Browser Driver promotion for child-chat lifecycle effects;
5. normalize the persistent DEV browser profile into a root-independent reusable location if still useful;
6. Superchat fleet/control layer;
7. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and broad Superchat automation remain out of scope.

For operational continuation use `docs/CURRENT_HANDOFF.md`. A ready-to-paste next-chat bootstrap is maintained in `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`. For longer-term ordering use `docs/DEVELOPMENT_PLAN.md`.
