# Conversation Fabric — current execution plan

Status: Stage 8, terminal recording, adoption/retirement, and restart/recovery boundary proof are complete. Manual lifecycle parity is next.

## Current baseline

Production remains unchanged:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent v4.19.12
- Chat Bridge 0.6.2

Canonical development line:

- branch: `develop/conversation-fabric`
- accepted CODE checkpoint: `2557f9477ff34ebb5b8502a15747e5d78f29bd5a`
- accepted commit: `Add restart recovery boundary proofs`
- exact-SHA canonical CI run: `37056289262`
- CI result: all five jobs passed (`test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`)
- accepted checkpoint is test-only relative to the adoption/retirement runtime checkpoint; no runtime behavior changed

Documentation-only commits may advance the canonical branch; always distinguish accepted CODE from later docs-only heads before effects.

Mac DEV checkout:

- `/Users/michal/local-agent-dev`

Production checkout:

- `/Users/michal/local-agent`

Preserved Stage 8 evidence:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- browser profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`

Production Chrome is never a source profile.

## Closed milestone ledger

### Stage 8 automatic one-child proof

- accepted CODE: `93fb65204db03c54d0080803d26266f3c06d777e` — `Confirm spawn identity from owned route transition`
- exact-SHA CI `37022787748`: all five jobs passed
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

Accepted path:

```text
terminal_recorded
  -> durable adoption record
  -> workflow reasoning node succeeded
  -> retired
```

The durable adoption record binds the exact child request digest, terminal-record digest, workflow ID and reasoning-node ID. It is persisted before workflow-node success so interruption is restart-recoverable. Identical semantic retries are idempotent, conflicts fail closed, and retirement requires both durable adoption and a succeeded bound workflow node. Reload validation enforces those invariants.

No browser effect was added by terminal or adoption/retirement slices.

### Restart/recovery boundary proof

- accepted CODE: `2557f9477ff34ebb5b8502a15747e5d78f29bd5a` — `Add restart recovery boundary proofs`
- exact-SHA canonical CI: `37056289262`, all five jobs passed

Durable read-only boundary evidence:

- `conversation-restart-recovery-boundary-summary-20261002-v2`: `done`

The audit classified the lifecycle boundaries as follows:

- B1 create: durable create intent before browser create; lost acknowledgement recovers the same transaction/tab and replacement creation is prohibited;
- B2 pre-submit: durable tab/bootstrap state allows strict recovery or one bounded reattach while submit has not happened;
- B3 submit/identity: `bootstrap_submitting` restart reconciles instead of resubmitting; ambiguity requires manual attach;
- B4 identity/registration intent: `identity_discovered -> registration_submitting`, no browser effect;
- B5 registration write: `registration_submitting -> ChildRegistration -> done`;
- B6 completion evidence: durable registration plus `done` recovers completion evidence/cleanup;
- B7 terminal: terminal record persists before `terminal_recorded`;
- B8 adoption: adoption record persists before reasoning-node `succeeded`;
- B9 retirement: durable adoption plus succeeded node allows `retired`; no external cleanup effect currently exists.

B1-B3 were already covered by runner tests and Chromium/MV3 restart smokes. B7-B9 already had restart/failure-injection proof. The smallest missing proof was explicit runner restart coverage for B4-B6.

The accepted change adds only `tests/test_conversation_restart_recovery.py`; runtime source is unchanged.

Verification:

- `conversation-restart-recovery-proof-verify-20261002-v1`: compile passed, Ruff passed, 49 focused tests passed, diff check passed;
- local `bridge-browser` could not start because the DEV checkout lacked a visible `playwright` Node module; this was environment-only and made no source change;
- exact-SHA GitHub CI installed isolated tooling and passed `bridge-browser` and every other job;
- production remained unchanged and clean.

## Non-negotiable invariants

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- Chat Bridge remains a bounded browser actuator, not workflow authority.
- child chats never receive independent machine execution authority.
- `local-agent` remains `execution_enabled=false` for reasoning-child browser work.
- no production Chrome/profile mutation.
- no Native Messaging control plane.
- no blind replay after a potentially submitted ambiguous effect.
- browser DOM is transport evidence, not durable workflow state.

## Current milestone — manual lifecycle parity

The next goal is to make the manual fallback path first-class while preserving one durable lifecycle and one source of authority.

Begin with a bounded read-only ownership/contract audit. Do not change behavior before the audit identifies a concrete parity gap.

The audit must map manual operations for:

- attaching an existing/ambiguous child to the exact admitted request and spawn transaction;
- canonical registration and conflicting/idempotent registration behavior;
- continuing a manually attached child through active, terminal evidence, adoption and retirement;
- restart/resume behavior for manual evidence and operator intervention;
- automatic-only browser assumptions that must not become durable manual-state assumptions;
- existing APIs that already provide parity versus the smallest missing contract/test.

Required matrix columns:

- manual operation;
- durable owner/precondition;
- exact lifecycle transition;
- durable evidence before/after effect;
- idempotency/conflict rule;
- restart/recovery rule;
- browser dependency, if any;
- existing tests/proofs;
- smallest missing parity proof.

At minimum inspect:

- `attach_ambiguous_live_slice` and related manual recovery paths in `local_agent/development/live_runner.py`;
- conversation registration/state store;
- spawn store ambiguity/queue resolution;
- terminal record path;
- adoption/retirement path;
- workflow reasoning-node transition contracts.

Do not create a new child or launch a broad browser campaign for the audit. Reuse the existing lifecycle primitives wherever possible and do not introduce a second scheduler or parallel state machine.

## Immediate execution plan

1. Fetch fresh mutable refs and daemon state.
2. Verify DEV clean and production unchanged.
3. Reopen manual attach/recovery, conversation/spawn stores, terminal/adoption and workflow state/tests.
4. Run one bounded read-only manual lifecycle parity audit through `host-ops` and persist its result.
5. Build the ownership/state-transition matrix from repository evidence.
6. Classify current manual operations as already parity-safe versus missing proof/contract.
7. Select the smallest genuine parity gap.
8. Add positive, negative, idempotency and restart tests before behavior changes.
9. Implement only the smallest gap and reuse existing durable APIs.
10. Use browser evidence only if that gap genuinely crosses a browser boundary.
11. Establish exact-SHA CI before accepting another CODE checkpoint.
12. Update durable docs only after acceptance.

## Ordered milestones after manual lifecycle parity

1. narrow Browser Driver promotion for child-chat lifecycle effects;
2. normalize the persistent DEV browser profile into a root-independent reusable location if still useful;
3. Superchat fleet/control layer;
4. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and broad Superchat automation remain out of scope.

For operational continuation use `docs/CURRENT_HANDOFF.md`. A ready-to-paste next-chat bootstrap is maintained in `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`. For longer-term ordering use `docs/DEVELOPMENT_PLAN.md`.