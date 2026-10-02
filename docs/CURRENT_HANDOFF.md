# Current handoff — Conversation Fabric after restart/recovery proof

Date: 2026-10-02
Status: Stage 8, terminal recording, adoption/retirement, and restart/recovery boundary proof are complete. Manual lifecycle parity is next.

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
- accepted CODE checkpoint: `2557f9477ff34ebb5b8502a15747e5d78f29bd5a`
- accepted commit: `Add restart recovery boundary proofs`
- exact-SHA canonical CI run: `37056289262`
- all jobs passed: `test`, `python-314`, `coverage`, `macos-smoke`, `bridge-browser`
- Mac DEV checkout: `/Users/michal/local-agent-dev`
- production checkout: `/Users/michal/local-agent`

The accepted restart/recovery checkpoint is test-only relative to the prior adoption/retirement runtime checkpoint: no runtime behavior changed.

Documentation-only commits may advance the canonical branch beyond the accepted CODE checkpoint. Always distinguish runtime/test CODE from later docs-only heads before effects.

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

Accepted path:

```text
terminal_recorded
  -> durable adoption record
  -> workflow reasoning node succeeded
  -> retired
```

Accepted properties:

- adoption requires the exact admitted request, canonical registration and durable terminal record;
- the adoption record binds the exact child request digest, terminal-record digest, workflow ID and workflow node ID;
- adoption persists before workflow-node success and interrupted ordering is restart-recoverable by idempotent retry;
- identical semantic adoption retries are idempotent; conflicts fail closed;
- retirement requires durable adoption plus the bound workflow node in `succeeded`;
- reload/restart validation fails closed if retired state loses adoption, terminal evidence or succeeded workflow-node state;
- no browser effect was added.

## Completed restart/recovery boundary proof

Accepted CODE checkpoint:

- `2557f9477ff34ebb5b8502a15747e5d78f29bd5a` — `Add restart recovery boundary proofs`
- exact-SHA canonical CI: `37056289262`, all five jobs passed

Durable audit evidence:

- `conversation-restart-recovery-boundary-audit-20261002-v1`: read-only audit, completed
- `conversation-restart-recovery-boundary-summary-20261002-v2`: `done`, read-only authoritative boundary summary

The boundary inventory found no missing runtime recovery contract. The smallest missing evidence was three explicit runner restart proofs:

- B4: restart from durable `identity_discovered` before registration intent is advanced;
- B5: restart from `registration_submitting` before durable `ChildRegistration` is written;
- B6: restart from durable registration plus `done` before completion evidence/cleanup is written.

Implementation scope:

- new test-only file: `tests/test_conversation_restart_recovery.py`
- no runtime source changed
- no new browser effect was introduced

Existing browser/runtime evidence already covered the external-effect boundaries:

- lost browser-create acknowledgement recovers the same transaction/tab and never creates a replacement;
- pre-submit restart uses strict recovery or one bounded reattach while no submit has happened;
- `bootstrap_submitting` restart reconciles instead of resubmitting;
- Chromium/MV3 smoke terminates the extension worker during submit and recovers the same canonical child without a second submit;
- ambiguous submit remains fail-closed and requires manual attach rather than blind replay;
- terminal recording and adoption already had failure-injection/restart proofs.

Verification ledger:

- `conversation-restart-recovery-boundary-summary-20261002-v2`: `done` and identified B4+B5+B6 as the smallest missing proof;
- `conversation-restart-recovery-proof-verify-20261002-v1`: compile passed, Ruff passed, 49 focused restart/spawn/terminal/adoption tests passed, diff check passed;
- a local `bridge-browser` verification attempt failed only because the DEV checkout did not expose the `playwright` Node module; it made no source changes and is non-authoritative;
- exact-SHA GitHub CI installed isolated browser tooling and passed `bridge-browser` plus all other jobs on `2557f947...`;
- production remained clean and unchanged at `979ef080ddb69d6e18aaf81510e3175bac2f33d2`.

## Current milestone — manual lifecycle parity

Start with a preimplementation read-only ownership/contract audit. Do not change behavior in the first step.

The goal is to make the manual fallback path a first-class lifecycle path with the same durable authority and fail-closed guarantees as the automatic path, not to create a second scheduler or alternate state machine.

Audit the current manual/attach/recovery surfaces and identify semantic owners for:

- attaching an already-created or ambiguous child to the exact admitted request/transaction;
- canonical `ChildRegistration` creation and idempotency/conflict behavior;
- progression from registered/active child through terminal evidence;
- adoption into the exact reasoning node and retirement;
- operator-visible/manual evidence and how it is resumed after restart;
- which automatic-only browser assumptions must not leak into the manual path;
- which existing APIs can be reused unchanged versus the smallest actual parity gap.

At minimum reopen:

- `local_agent/development/live_runner.py` manual attach/recovery entrypoints;
- `local_agent/conversation/store.py`;
- `local_agent/conversation/spawn_store.py`;
- `local_agent/conversation/terminal.py`;
- `local_agent/conversation/adoption.py`;
- workflow node/state/store contracts and focused tests.

For every manual lifecycle operation record:

- durable authority/precondition;
- exact state transition;
- evidence written before/after the transition;
- idempotency and conflict behavior;
- restart/recovery behavior;
- whether browser access is actually required;
- existing test coverage and smallest missing parity proof.

Do not launch a new child or broad browser campaign merely for this audit. Do not broaden into Browser Driver promotion, multi-child scheduling, fleet control or rollout.

## Exact continuation sequence

1. Fetch fresh `main`, `develop/conversation-fabric`, `host-ops:agent-control` and daemon state.
2. Verify DEV is clean and distinguish accepted CODE `2557f947...` from later docs-only commits.
3. Verify production remains clean and unchanged.
4. Read this handoff, `CURRENT_PLAN.md`, `DEVELOPMENT_PLAN.md`, then reopen manual attach/store/terminal/adoption/workflow surfaces.
5. Run one bounded read-only manual-lifecycle parity audit through `host-ops`; persist the result durably.
6. Build the ownership/state-transition matrix from repository evidence, not chat memory.
7. Select only the smallest real parity gap.
8. Add focused positive/negative/idempotency/restart tests before changing behavior.
9. Implement only the smallest gap; reuse existing durable contracts instead of duplicating lifecycle logic.
10. Use live browser evidence only if the selected gap genuinely requires a browser effect.
11. Use direct GitHub operations for repository changes and `host-ops` for all Mac-local operations.
12. Accept another CODE checkpoint only after focused verification and exact-SHA CI.
13. Update durable docs only after that checkpoint is accepted.

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

After manual lifecycle parity:

1. narrow Browser Driver promotion for child-chat lifecycle effects;
2. normalize the persistent DEV browser profile into a reusable root-independent location if still useful;
3. Superchat fleet/control layer;
4. broader automatic scheduling only after the single-child lifecycle is proven stable.

Multi-child fan-out, fleet scheduling, rollover and broad Superchat automation remain out of scope.