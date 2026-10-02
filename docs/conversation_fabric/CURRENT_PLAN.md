# Conversation Fabric — current execution plan

Status: Stage 8, terminal recording, and adoption/retirement are complete. Restart/recovery proof across external-effect boundaries is next.

## Current baseline

Production remains unchanged:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent v4.19.12
- Chat Bridge 0.6.2

Canonical development line:

- branch: `develop/conversation-fabric`
- accepted CODE checkpoint: `e76dc4a114f750cc0beabdbb2ad626d41ff2e986`
- accepted commit: `Add durable child adoption and retirement`
- exact-SHA canonical CI run: `37054505079`
- CI result: all five jobs passed (`test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`)

Documentation-only commits may advance the canonical branch; always distinguish accepted runtime CODE from later docs-only heads before effects.

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

Accepted Stage 8 CODE checkpoint:

- `93fb65204db03c54d0080803d26266f3c06d777e` — `Confirm spawn identity from owned route transition`
- exact-SHA CI `37022787748`: all five jobs passed

Proof22 remains authoritative:

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- request digest: `sha256:460bb68b76a73350718a9f091bf3b071cfa8762f3222030e52af58e8b392a79d`
- transaction: `spawn-92f4107c2bf0bdd6abd122c5ddcfaa6417691c576d811efc6a1973f59c676615`
- canonical child: `https://chatgpt.com/c/6abfcdf9-8438-83eb-86da-1c4b209afc47`
- spawn attempt: `1`
- matching durable registration/completion evidence
- no manual attach/recovery
- no production mutation

Do not start another Stage 8 spawn campaign.

### Terminal/checkpoint recording

Accepted CODE checkpoint:

- `a16918d32bc366dbc9d8a8793669baa214d13620` — `Add durable child terminal records`
- canonical exact-SHA CI `37036591713`: all five jobs passed

Accepted path:

```text
active -> terminal_pending_evidence -> terminal_recorded
```

Terminal evidence is durable, bounded, schema-validated, exact-request/registration-bound, persisted before lifecycle completion, idempotent for the same semantic record, conflicting records fail closed, and reload validation rechecks the cross-record invariants.

### Adoption and retirement

Accepted CODE checkpoint:

- `e76dc4a114f750cc0beabdbb2ad626d41ff2e986` — `Add durable child adoption and retirement`
- canonical exact-SHA CI `37054505079`: all five jobs passed

Audit evidence:

- `conversation-adoption-retirement-preimplementation-audit-20261002-v1`: `done`
- `conversation-adoption-retirement-audit-summary-20261002-v1`: `done`

The audit found no existing Conversation Fabric adoption subsystem. The smallest contract uses the already-legal transitions:

```text
child:    terminal_recorded -> retired
workflow: waiting_conversation -> succeeded
```

with a durable adoption record between them.

Accepted properties:

1. adoption requires the exact admitted request, canonical registration and durable terminal record;
2. the adoption record binds request digest, terminal-record digest, workflow ID and reasoning-node ID;
3. the adoption record is bounded and schema-validated;
4. adoption is persisted before workflow-node success;
5. interrupted adoption-write/workflow-state ordering is retryable and restart-safe;
6. identical semantic adoption is idempotent and conflicts fail closed;
7. retirement requires durable adoption plus the bound workflow node in `succeeded`;
8. retired reload fails closed if adoption, terminal evidence or succeeded workflow state is missing;
9. mutations use the existing workflow execution lock;
10. no browser effect was introduced.

Implementation:

- `local_agent/conversation/adoption.py`
- `local_agent/conversation/store.py`
- `tests/test_conversation_adoption.py`

Verification:

- `conversation-adoption-retirement-implementation-20261002-v2`: focused 47 tests passed;
- squashed verification `conversation-adoption-retirement-candidate-verify-20261002-v1`: compile, Ruff, 56 focused/workflow tests and `git diff --check` passed;
- first integration task v1 failed before source mutation because of patch-script encoding and is non-authoritative;
- DEV was synchronized clean to the accepted SHA;
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

## Current milestone — restart/recovery proof across external-effect boundaries

The next milestone is not a broad live campaign. First produce a read-only boundary inventory on the accepted CODE checkpoint.

The audit must enumerate every external-effect boundary in the proven single-child lifecycle where a process can stop after durable intent/checkpoint but before durable completion evidence.

Required boundary matrix columns:

- operation/effect boundary;
- pre-effect durable intent/checkpoint;
- external effect;
- post-effect durable evidence/completion;
- observable restart state;
- safe retry / prohibited retry / attach-or-recover rule;
- ambiguity/conflict fail-closed rule;
- existing unit/integration/live proof;
- smallest missing proof.

At minimum inspect:

- spawn transaction and exact browser submit/canonical identity;
- child registration and spawn completion evidence;
- terminal evidence before terminal lifecycle state;
- adoption record before workflow-node success;
- retirement and any external cleanup boundary if one actually exists;
- workflow publication/checkpoint/evidence primitives used by these flows.

Do not infer a missing proof from memory. Re-open current code and durable proof artifacts. Do not launch browser effects during the audit.

## Immediate execution plan

1. Fetch fresh mutable refs and daemon state.
2. Verify DEV clean and production unchanged.
3. Re-open spawn transaction/store, conversation store, terminal/adoption contracts, workflow checkpoint/evidence/recovery code and their tests.
4. Run one bounded read-only boundary inventory through `host-ops` and persist its result.
5. Classify existing boundaries as already proven versus missing proof.
6. Select the smallest genuinely missing restart/recovery boundary.
7. Add failure-injection/restart tests before behavior changes.
8. Implement only if the audit exposes a contract gap; otherwise prove the existing contract without code changes.
9. Use a live browser proof only when the selected missing boundary necessarily crosses the browser effect.
10. Establish exact-SHA CI for any new CODE checkpoint before accepting it.
11. Update durable docs only after acceptance.

## Ordered milestones after restart/recovery proof

1. manual lifecycle parity as a first-class fallback;
2. narrow Browser Driver promotion for child-chat lifecycle effects;
3. normalize the persistent DEV browser profile into a root-independent reusable location if still useful;
4. Superchat fleet/control layer;
5. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and broad Superchat automation remain out of scope.

For operational continuation use `docs/CURRENT_HANDOFF.md`. A ready-to-paste next-chat bootstrap is maintained in `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`. For longer-term ordering use `docs/DEVELOPMENT_PLAN.md`.
