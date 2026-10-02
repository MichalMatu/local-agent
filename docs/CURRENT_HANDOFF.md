# Current handoff — Conversation Fabric after adoption and retirement

Date: 2026-10-02
Status: Stage 8, terminal recording, and adoption/retirement milestones are complete. Restart/recovery proof across external-effect boundaries is next.

## Read this first

This file is the authoritative operational continuation point for Conversation Fabric work. Repository state, durable docs and fresh `host-ops` evidence outrank chat memory.

Then read:

1. `AGENTS.md`
2. `docs/conversation_fabric/CURRENT_PLAN.md`
3. `docs/DEVELOPMENT_PLAN.md`
4. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

## Repository state

Production remains unchanged:

- `main`: `979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent: v4.19.12
- Chat Bridge: 0.6.2

Conversation Fabric development:

- canonical branch: `develop/conversation-fabric`
- accepted CODE checkpoint: `e76dc4a114f750cc0beabdbb2ad626d41ff2e986`
- accepted commit: `Add durable child adoption and retirement`
- exact-SHA canonical CI run: `37054505079`
- all jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`
- Mac DEV checkout: `/Users/michal/local-agent-dev`
- production checkout: `/Users/michal/local-agent`

Documentation-only commits may advance the canonical branch beyond the accepted CODE checkpoint. Always distinguish runtime CODE from later docs-only heads before effects.

The preserved Stage 8 evidence root/profile remains:

- root: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096`
- browser profile: `/Users/michal/Library/Application Support/local-agent-dev-stage8-proof12-auth-gate-3096/browser-profile/live-slice`
- production Chrome profile is protected: `/Users/michal/Library/Application Support/Google/Chrome`

## Stage 8 remains closed

Proof22 is still the automatic one-child proof. Do not start another Stage 8 campaign or create another child for that milestone.

- workflow: `stage8-live-slice`
- request: `stage8-live-child-001`
- request digest: `sha256:460bb68b76a73350718a9f091bf3b071cfa8762f3222030e52af58e8b392a79d`
- transaction: `spawn-92f4107c2bf0bdd6abd122c5ddcfaa6417691c576d811efc6a1973f59c676615`
- plan digest: `sha256:43581f5fc966859b7339ddbdb0cc24de26fbe3ec30841784bc851ebd322dc61a`
- canonical child: `https://chatgpt.com/c/6abfcdf9-8438-83eb-86da-1c4b209afc47`
- spawn attempt: `1`
- durable `SpawnTransaction=done`
- matching durable `ChildRegistration`
- bounded completion evidence: matching
- manual attach/recovery: not used
- production mutation: none

## Completed terminal-record milestone

Accepted CODE checkpoint:

- `a16918d32bc366dbc9d8a8793669baa214d13620` — `Add durable child terminal records`
- canonical exact-SHA CI: `37036591713`, all five jobs passed

Accepted lifecycle:

```text
active
  -> terminal_pending_evidence
  -> terminal_recorded
```

The terminal record is bounded and schema-validated, binds the exact request and canonical registration, persists before terminal state, is idempotent for the same semantic evidence, fails closed on conflicts, uses the workflow execution lock, and is revalidated on reload/restart.

## Completed adoption and retirement milestone

Accepted CODE checkpoint:

- `e76dc4a114f750cc0beabdbb2ad626d41ff2e986` — `Add durable child adoption and retirement`
- canonical exact-SHA CI: `37054505079`, all five jobs passed

Preimplementation evidence:

- `conversation-adoption-retirement-preimplementation-audit-20261002-v1`: `done`, read-only
- `conversation-adoption-retirement-audit-summary-20261002-v1`: `done`, read-only

The audit found no pre-existing Conversation Fabric adoption subsystem. The existing contracts already supplied the two required state transitions:

```text
workflow reasoning node: waiting_conversation -> succeeded
child lifecycle:        terminal_recorded -> retired
```

The accepted bounded contract adds a durable adoption record between them.

Implementation surfaces:

- `local_agent/conversation/adoption.py`
- `local_agent/conversation/store.py`
- `tests/test_conversation_adoption.py`

Accepted properties:

- adoption requires an admitted request, durable canonical registration, durable terminal record and child state `terminal_recorded`;
- the adoption record binds the exact child request digest, exact terminal-record digest, workflow ID and workflow node ID;
- the adoption record is bounded and schema-validated;
- the adoption record is persisted before the workflow node moves from `waiting_conversation` to `succeeded`;
- a crash after adoption persistence but before workflow-state advancement is restart-recoverable by an idempotent retry;
- semantically identical adoption retries are idempotent; conflicting identities/digests fail closed;
- `retired` is allowed only after durable adoption exists and the bound workflow node is `succeeded`;
- reload/restart validation fails closed if a retired child loses its adoption record, terminal evidence, or succeeded workflow-node state;
- mutations reuse the existing workflow execution lock;
- no browser effect was added.

Verification ledger:

- first integration task `conversation-adoption-retirement-implementation-20261002-v1` failed before source mutation because its transported patch script had invalid UTF-8; DEV remained clean;
- retry `conversation-adoption-retirement-implementation-20261002-v2`: `done`, focused suite 47 tests passed;
- squashed accepted candidate verification `conversation-adoption-retirement-candidate-verify-20261002-v1`: `done`;
- exact squashed SHA verification: compile passed, Ruff passed, 56 focused/workflow tests passed, `git diff --check` passed;
- DEV synchronized clean to accepted CODE SHA;
- production remained clean at `979ef080ddb69d6e18aaf81510e3175bac2f33d2`.

## Current milestone — restart/recovery proof across external-effect boundaries

This milestone is next. No new implementation or live campaign is accepted yet.

Start with a bounded read-only boundary inventory/audit on the accepted CODE checkpoint. The audit must identify every Conversation Fabric external-effect boundary that can be interrupted after durable intent but before durable completion, and map the already-existing recovery evidence/state for each boundary.

At minimum inspect the proven single-child lifecycle surfaces around:

- child spawn intent/transaction versus browser submit/canonical identity;
- registration and durable completion evidence;
- terminal evidence/state ordering;
- adoption record versus workflow-node success;
- retirement and any later cleanup effect, if one exists;
- existing workflow publication/checkpoint/evidence patterns that participate in those boundaries.

For each boundary record:

- durable pre-effect intent/checkpoint;
- the external effect itself;
- durable post-effect evidence/completion;
- what a restart can observe;
- whether retry is safe, prohibited, or requires recovery/attach;
- exact fail-closed behavior when evidence is ambiguous or conflicting;
- existing tests/proofs and the smallest missing proof.

Do not launch a new browser campaign merely to perform the audit. Do not broaden into multi-child scheduling, fleet control or rollout. Implement or run live recovery proof only after the audit identifies the smallest missing boundary proof.

## Exact continuation sequence

1. Fetch fresh `main`, `develop/conversation-fabric`, `host-ops:agent-control` and daemon state.
2. Verify DEV is clean and distinguish the accepted CODE checkpoint from docs-only commits.
3. Verify production remains clean and unchanged.
4. Read this handoff, `CURRENT_PLAN.md`, `DEVELOPMENT_PLAN.md`, then re-open spawn/store/terminal/adoption/workflow recovery surfaces.
5. Run one bounded read-only external-effect boundary inventory through `host-ops`; persist the result durably.
6. Build a boundary matrix from repository evidence, not chat memory.
7. Select only the smallest missing restart/recovery proof.
8. Add focused failure-injection/restart tests before changing behavior.
9. Use live browser evidence only if the selected missing proof genuinely crosses the browser boundary.
10. Use direct GitHub operations for repository changes and `host-ops` for all Mac-local operations.
11. Accept another CODE checkpoint only after focused verification and exact-SHA CI.
12. Update durable docs only after that checkpoint is accepted.

## Safety invariants

- GitHub is the durable control/evidence plane.
- Local Agent remains deterministic and model-free.
- Chat Bridge remains a bounded browser actuator, not workflow authority.
- child chats have no independent machine execution authority.
- `local-agent` remains `execution_enabled=false` for reasoning-child browser work.
- no production Chrome/profile mutation.
- no Native Messaging control plane.
- no blind replay after a potentially submitted ambiguous effect.
- never mutate production `main`, `chat-bridge-state` or `operator-control` as part of Conversation Fabric development.
- machine-generated source, tests, docs, prompts, task metadata, logs and commit messages remain English-only.

## Later milestones

After restart/recovery proof:

1. manual lifecycle parity as a first-class fallback;
2. narrow Browser Driver promotion for child-chat lifecycle effects;
3. normalize the persistent DEV browser profile into a reusable root-independent location if still useful;
4. Superchat fleet/control layer;
5. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and broad Superchat automation remain out of scope.
