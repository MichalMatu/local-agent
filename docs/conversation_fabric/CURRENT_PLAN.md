# Conversation Fabric — current execution plan

Status: Stage 8 automatic one-child proof completed; durable terminal/checkpoint recording accepted; adoption and retirement are next.

## Current baseline

Production remains unchanged:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent v4.19.12
- Chat Bridge 0.6.2

Canonical development line:

- branch: `develop/conversation-fabric`
- accepted CODE checkpoint: `a16918d32bc366dbc9d8a8793669baa214d13620`
- accepted commit: `Add durable child terminal records`
- exact-SHA canonical CI run: `37036591713`
- CI result: all five jobs passed (`test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`)
- same-SHA isolated candidate CI run: `37035403791`, also passed

Documentation-only commits may advance `develop/conversation-fabric`; always distinguish the accepted CODE checkpoint from the current docs branch head before effects.

Mac DEV checkout:

- `/Users/michal/local-agent-dev`

Production checkout:

- `/Users/michal/local-agent`

Preserved isolated Stage 8 root/profile:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- browser profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`

Production Chrome is never a source profile.

## Stage 8 completion ledger

Proof22 remains the automatic one-child completion proof.

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- admitted Stage 8 code SHA: `93fb65204db03c54d0080803d26266f3c06d777e`
- request digest: `sha256:460bb68b76a73350718a9f091bf3b071cfa8762f3222030e52af58e8b392a79d`
- transaction: `spawn-92f4107c2bf0bdd6abd122c5ddcfaa6417691c576d811efc6a1973f59c676615`
- plan digest: `sha256:43581f5fc966859b7339ddbdb0cc24de26fbe3ec30841784bc851ebd322dc61a`
- canonical child: `https://chatgpt.com/c/6abfcdf9-8438-83eb-86da-1c4b209afc47`
- spawn attempt: `1`
- durable spawn state: `done`
- durable child state at proof completion: `active`
- durable registration: matching
- bounded completion evidence: matching
- recovery/manual attach: not used
- production mutation: none

Stage 8 completion gate is satisfied. Do not start another spawn campaign for this milestone.

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

## Completed milestone — checkpoint and terminal recording

Accepted CODE checkpoint `a16918d32bc366dbc9d8a8793669baa214d13620` completes:

```text
active
  -> terminal_pending_evidence
  -> terminal_recorded
```

The state-machine states already existed. The accepted slice adds the minimum durable record and enforcement around them.

Contract summary:

1. `active -> terminal_pending_evidence` remains an explicit durable transition.
2. `terminal_recorded` is impossible without a valid durable terminal record.
3. terminal evidence binds to the exact child request ID/digest, the digest of the canonical durable `ChildRegistration`, and canonical child URL.
4. terminal evidence is bounded and schema-validated, including non-empty bounded evidence references.
5. identical semantic recording is idempotent; conflicting recording fails closed.
6. writes serialize through the existing workflow execution lock.
7. evidence is atomically persisted before terminal lifecycle state, giving a recoverable pending state if the state write fails after evidence persistence.
8. persisted request/registration/evidence/state relationships are revalidated on reload/restart.
9. no browser effect, adoption semantics or retirement semantics were added.

Implementation:

- `local_agent/conversation/terminal.py`
- `local_agent/conversation/store.py`
- `tests/test_conversation_terminal.py`

Focused coverage includes missing registration, missing evidence, conflicting evidence, invalid lifecycle ordering, exact digest/registration binding, idempotency, bounded schema validation, crash recovery between evidence/state writes, reload fail-closed behavior and lock reuse.

## Terminal milestone verification

Preimplementation audit:

- `conversation-terminal-evidence-preimplementation-audit-20261002-v1`
- status: `done`
- read-only against `93fb65204db03c54d0080803d26266f3c06d777e`

The malformed task `conversation-terminal-record-implementation-20261002-v1` never started and remains non-authoritative.

Accepted local/candidate verification on `a16918d32bc366dbc9d8a8793669baa214d13620`:

- focused conversation tests: 38 passed
- compile: passed
- Ruff: passed
- `git diff --check`: passed
- DEV checkout clean after synchronization
- production checkout unchanged and clean

The broad local smoke environment had missing `mcp`/`httpx2` dependencies after sanitizing an inherited host-ops lease descriptor. Canonical exact-SHA GitHub CI installed its declared dependencies and passed all five jobs, including `macos-smoke` and `bridge-browser`; that run is the acceptance gate.

## Current milestone — adoption and retirement

Adoption and retirement are the next ordered milestone. Their implementation contract has not yet been accepted.

The first step is a bounded read-only preimplementation audit on the accepted CODE checkpoint, not a speculative implementation.

The audit must establish from current repository contracts:

- where adoption and retirement already appear in lifecycle/state/workflow code;
- which durable records or evidence, if any, must precede each transition;
- exact ordering and fail-closed behavior;
- idempotency and conflict behavior;
- restart/reload validation requirements;
- locking/atomic-write boundaries;
- whether any browser effect is actually required.

Do not broaden the audit into multi-child orchestration or invent semantics from older chats. The smallest accepted contract must be derived from current code and durable evidence.

## Immediate execution plan

1. Fetch fresh `main`, `develop/conversation-fabric`, `host-ops:agent-control` and daemon state.
2. Verify `/Users/michal/local-agent-dev` is clean and distinguish the accepted CODE checkpoint from docs-only commits.
3. Verify production remains clean and unchanged.
4. Read the current handoff and re-open the accepted terminal record implementation/tests.
5. Run one read-only adoption/retirement preimplementation audit through `host-ops` and persist its result.
6. Define the minimum next state/evidence contract from repository state plus that audit.
7. Add focused positive/negative/idempotency/restart tests before behavior changes.
8. Implement one bounded slice only after the audit supports it.
9. Use direct GitHub operations for repository changes and `host-ops` for all Mac-local effects.
10. Run focused and diff-appropriate verification.
11. Push one accepted CODE checkpoint to `develop/conversation-fabric` and close exact-SHA CI.
12. Only then update durable handoff docs again.

## Ordered milestones after adoption and retirement

1. restart/recovery proof across every external-effect boundary;
2. manual lifecycle parity as a first-class fallback;
3. narrow Browser Driver promotion for child-chat lifecycle effects;
4. normalize the persistent DEV browser profile into a root-independent reusable location if still useful;
5. Superchat fleet/control layer;
6. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and broad Superchat automation remain out of scope.

For operational continuation use `docs/CURRENT_HANDOFF.md`. A ready-to-paste next-chat bootstrap is maintained in `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`. For longer-term ordering use `docs/DEVELOPMENT_PLAN.md`.
