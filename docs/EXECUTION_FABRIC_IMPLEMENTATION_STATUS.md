# Execution Fabric implementation status

Branch: `feature/openworker-governance`
Production base: `main@224046066b0df92544337db0ee623e372629e726` (`v4.18.22`)
Design: `docs/EXECUTION_FABRIC_IMPLEMENTATION_PLAN.md`

Status: implementation in progress. The current branch adds workflow contracts, methods, durable local state and deterministic child-task materialization. It does **not** yet dispatch workflow child tasks to repository control branches and does not change the production supervisor/worker execution path.

## Implemented

### Phase 0 — workflow contract and state machine

Implemented under `local_agent/workflow/`:

- `contract.py`
  - workflow schema v1;
  - canonical SHA-256 manifest identity;
  - bounded workflow/node/dependency sizes;
  - strict node kinds;
  - canonical repository binding validation;
  - cycle, duplicate and unknown-dependency rejection;
  - task nodes reuse the existing Local Agent task contract;
  - coordinator-owned task id/binding/provenance fields cannot be supplied by a task template;
  - optional method references are exact name/version/digest identities.
- `state.py`
  - explicit node-state transition table;
  - dependency readiness;
  - barrier completion;
  - `waiting_user` and `waiting_planner` states;
  - terminal-state non-regression;
  - interrupted child state maps to planner intervention rather than replay.

Fixtures cover:

- single-repository task;
- parallel multi-repository graph;
- failed dependency;
- user gate;
- planner checkpoint.

### Phase 1 — built-in methods

Implemented:

- `local_agent/workflow/methods.py`
- `local_agent/workflow/method_specs/deep-refactor.json`
- `local_agent/workflow/method_specs/cross-repo-api-change.json`
- `local_agent/workflow/method_specs/release-candidate.json`

Properties:

- method specs are versioned and digest-pinned;
- changing a method without changing its pinned identity is detected;
- method references are checked at workflow manifest admission;
- required phases must be present;
- `deep-refactor` requires a planner checkpoint after the audit phase;
- methods that require full verification reuse the existing `efficient-verification-v1` task policy rather than inventing a second verifier.

Local inspection CLI:

```bash
python -m local_agent.cli.workflow methods
python -m local_agent.cli.workflow method deep-refactor
python -m local_agent.cli.workflow validate-manifest <manifest.json>
```

### Phase 2 slice A — durable local workflow lifecycle

Implemented in `local_agent/workflow/store.py`:

- local state root under `~/Library/Application Support/local-agent/workflows/` by default;
- immutable `manifest.json`;
- atomic authoritative `state.json`;
- bounded append-only `events.ndjson` audit stream;
- exact manifest-digest idempotency on submit;
- same workflow id with different manifest is rejected;
- per-workflow mutation lock prevents lost local updates;
- corruption is isolated to the affected workflow;
- `cancel_requested` does not pretend an already dispatched/running child has stopped;
- active child state must later be reconciled from exact terminal repository evidence.

Local lifecycle CLI:

```bash
python -m local_agent.cli.workflow submit <manifest.json>
python -m local_agent.cli.workflow list
python -m local_agent.cli.workflow show <workflow-id>
python -m local_agent.cli.workflow cancel <workflow-id>
```

`--state-dir <path>` is available for isolated tests/diagnostics.

### Phase 2 slice B — deterministic child-task materialization

Implemented in `local_agent/workflow/publishing.py`:

- one task node deterministically materializes to one existing Local Agent task payload;
- child task id is `wf-<sha256>` derived from exact workflow id, node id and manifest digest;
- exact node `agent_binding` is injected by the coordinator boundary;
- child workflow provenance contains workflow id, node id and manifest digest;
- the materialized payload is revalidated by the existing task contract;
- ordinary runtime `task_digest` remains the child execution identity.

No Git publication exists yet. `publishing.py` currently owns only pure materialization helpers.

## Tests added

- `tests/test_workflow_contract.py`
- `tests/test_workflow_state.py`
- `tests/test_workflow_methods.py`
- `tests/test_workflow_store.py`
- `tests/test_workflow_publishing.py`
- `tests/test_workflow_cli.py`
- `tests/fixtures/workflows/*.json`

The tests cover contract bounds, cycles, bindings, method digests/structure, state transitions, barriers, wait states, terminal non-regression, durable-store idempotency/corruption/cancellation, CLI lifecycle and deterministic child-task materialization.

## Deliberately not implemented yet

The following remain outside the current slice:

- writing child tasks into a target repository `.agent/tasks/` path;
- Git commit/push of workflow-owned child tasks;
- target repository registry/binding reconciliation at publication time;
- exact repository result/run reconciliation back into workflow node state;
- coordinator restart recovery after publication;
- unrelated pending/active task yield policy;
- exact `cancel_task` publication for active workflow children;
- supervisor integration/tick scheduling;
- remote workflow transport;
- Chat Bridge orchestration identity;
- append-only workflow revisions/continuations;
- user-gate resolution transport.

This boundary is intentional: Git publication is the first part of the feature that can cause real repository execution side effects, so it should start only after the pure/durable foundation is verified.

## Validation status

No production claim is made for this branch yet.

Repository CI currently runs on pushes to `main`, `v*-staging`, `work/**`, and on pull requests. Direct pushes to `feature/openworker-governance` therefore do not automatically produce the normal CI matrix.

Before adding real workflow dispatch, run on the exact branch SHA at minimum:

```bash
python scripts/verify.py --only compile
python scripts/verify.py --only lint
python -m unittest \
  tests.test_workflow_contract \
  tests.test_workflow_state \
  tests.test_workflow_methods \
  tests.test_workflow_store \
  tests.test_workflow_publishing \
  tests.test_workflow_cli
```

Then run the normal full repository verification before release integration:

```bash
python scripts/verify.py
```

The eventual release candidate still requires the repository's normal full CI matrix and exact-SHA macOS smoke.

## Next implementation slice

The next slice should implement a local coordinator around the existing repository registry/control-plane primitives, in this order:

1. validate a ready task node against the currently enabled exact repository id/binding;
2. derive expected child task id and task digest;
3. inspect target repository control evidence to prove the child is absent/pending/running/terminal;
4. publish the immutable child task once, using the existing Git control-plane conventions;
5. persist the expected child id/digest in workflow state;
6. reconcile only an exact matching result back into the node;
7. yield rather than competing with unrelated repository work;
8. prove restart after publication cannot create a duplicate child task.

Do not modify the production supervisor loop until these coordinator semantics pass isolated real temporary-Git integration tests.
