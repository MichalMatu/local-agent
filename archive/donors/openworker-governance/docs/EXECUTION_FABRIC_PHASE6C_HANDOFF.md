# Execution Fabric Phase 6C handoff

Branch: `feature/openworker-governance`

This handoff continues `docs/EXECUTION_FABRIC_PHASE6B_HANDOFF.md`.

## Safety boundary remains active

All changes in this slice remain branch-only and inert with respect to the installed/running Local Agent.

- no production supervisor/daemon/worker/entrypoint/launchd integration;
- no production `WorkflowControlPlane` implementation;
- no remote control-branch fetch/push;
- no service restart or reconfiguration;
- no CLI command that ticks or dispatches revision workflows;
- disposable Git tests use only `TemporaryDirectory` repositories and never push;
- `tests/test_workflow_inert_boundary.py` remains the architectural guard against accidental runtime imports.

A branch comparison from `155cb8693d4415933b2f8ccdc699914a1c9825b1` through this slice showed changes only under:

```text
local_agent/workflow/*
local_agent/cli/workflow.py
tests/test_workflow_*.py
docs/EXECUTION_FABRIC_*.md
```

No production runtime owner was modified.

## Effective user gates

`WorkflowEffectiveStateStore` now supports durable revision-graph user gates.

`resolve_user_gate(...)` provides:

- exact active effective graph lookup;
- node-kind check (`user_gate` only);
- allowed-choice validation from the immutable effective graph;
- bounded resolver identity;
- RFC3339 UTC decision timestamp;
- lineage-tip provenance;
- first resolver wins;
- repeated identical decision is idempotent;
- conflicting second decision is rejected;
- decision record and `waiting_user -> succeeded` are written atomically to the isolated `effective_state.json`;
- dependency readiness is recalculated through the existing workflow state machine.

Effective-state reload validates persisted gate decisions against the active graph and requires the gate node to remain `succeeded`.

Base-manifest gate decisions remain compatible: effective-state validation accepts either base `manifest_digest` provenance or revision `lineage_tip_digest` provenance.

## Effective cancellation semantics

Effective state schema is now version 2 and includes:

```json
"cancel_requested": false
```

`WorkflowEffectiveStateStore.cancel(...)` mirrors the existing Local Agent workflow cancellation principle:

- `pending`, `blocked_dependency`, `ready`, `waiting_user`, and `waiting_planner` nodes become `cancelled`;
- `dispatched` and `running` tasks are deliberately left active;
- cancellation does not claim a process stopped when there is no terminal evidence;
- repeated cancellation is idempotent;
- the base `WorkflowStore.state.json` remains untouched;
- a cancelled effective workflow cannot activate another revision.

Operator-like effective mutations (`resolve_user_gate`, `resolve_planner_checkpoint`, `cancel`, `activate_next_revision`) now serialize against lineage dispatch using the existing workflow execution lock. Task reconciliation still uses only the effective-state file lock because the lineage coordinator already holds the execution lock around a tick; this avoids re-entrant flock/deadlock.

## Lineage coordinator cancellation

`tick_lineage_workflow(...)` now understands `cancel_requested`.

Tick order is deliberately:

```text
load active graph
-> reconcile exact evidence for ready/dispatched/running children
-> if cancel_requested: stop
-> otherwise consider new publication
```

Consequences:

- cancellation never publishes a new child;
- an already-running child can still transition from exact terminal evidence;
- `cancelled_by_operator` evidence maps to node `cancelled` through the existing evidence/reconciliation policy;
- once the final active child becomes terminal-cancelled, the workflow becomes terminal `cancelled`;
- active-child cancellation transport itself is still not implemented here.

## Disposable Git lineage integration

New test: `tests/test_workflow_temporary_git_lineage.py`.

The test-only `DisposableGitLineageControlPlane` uses real local Git repositories created under `TemporaryDirectory`.

Scenario:

```text
base audit already reviewed
-> activate rev1
-> lineage coordinator commits rev1 implement child into repo A .agent/tasks/
-> write exact success result
-> planner checkpoint waits and is resolved
-> append + activate rev2
-> reconstruct effective store (restart simulation)
-> lineage coordinator commits rev2 verify child into repo B .agent/tasks/
-> rev1 child identity remains byte-for-byte unchanged
-> repo A receives no second child commit
-> write exact rev2 success result
-> workflow completes
```

The test checks real local Git commit counts and task file locations. No remote exists and nothing is pushed.

## Read-only observability CLI

Two commands were added without adding any dispatch path:

```bash
python -m local_agent.cli.workflow --state-dir <dir> \
  activations <workflow-id>

python -m local_agent.cli.workflow --state-dir <dir> \
  effective-state <workflow-id>
```

`activations` reports compact activation provenance:

- revision number;
- activation digest;
- revision digest;
- parent lineage tip;
- checkpoint id;
- projected new node states;
- activation timestamp.

`effective-state` prints the isolated effective revision state as validated from disk.

`tests/test_workflow_observability_cli.py` snapshots manifest/state/revision/activation/effective-state bytes before and after these commands and requires them to remain unchanged.

## Tests authored in this slice

- `tests/test_workflow_effective_controls.py`
- `tests/test_workflow_lineage_cancellation.py`
- `tests/test_workflow_temporary_git_lineage.py`
- `tests/test_workflow_observability_cli.py`

Additional existing tests affected by the schema/locking behavior:

- `tests/test_workflow_effective_state.py`
- `tests/test_workflow_lineage_coordinator.py`
- `tests/test_workflow_inert_boundary.py`

## Validation status

The new tests are authored but are **not claimed green**.

The branch still does not receive the normal push CI matrix. The assistant sandbox cannot resolve GitHub DNS, and the installed/running Local Agent has deliberately not been used as a test executor.

Before any production adapter is created, the exact branch SHA must execute at minimum:

```bash
python scripts/verify.py --only compile
python scripts/verify.py --only lint
python -m unittest \
  tests.test_workflow_contract \
  tests.test_workflow_state \
  tests.test_workflow_methods \
  tests.test_workflow_store \
  tests.test_workflow_store_audit \
  tests.test_workflow_publishing \
  tests.test_workflow_coordinator \
  tests.test_workflow_coordinator_cancel \
  tests.test_workflow_evidence \
  tests.test_workflow_gates \
  tests.test_workflow_checkpoints \
  tests.test_workflow_revisions \
  tests.test_workflow_revision_store \
  tests.test_workflow_continuation \
  tests.test_workflow_activation \
  tests.test_workflow_activation_validation \
  tests.test_workflow_effective_state \
  tests.test_workflow_effective_controls \
  tests.test_workflow_lineage_publishing \
  tests.test_workflow_lineage_coordinator \
  tests.test_workflow_lineage_cancellation \
  tests.test_workflow_temporary_git_integration \
  tests.test_workflow_temporary_git_lineage \
  tests.test_workflow_observability_cli \
  tests.test_workflow_inert_boundary
```

Then run:

```bash
python scripts/verify.py
```

before any release/integration decision.

## Stop gate before production wiring

The isolated design is now far enough along that further branch-only feature growth has diminishing value compared with actually executing the authored verification suite.

Do **not** create or wire a production Git-backed `WorkflowControlPlane` yet.

The next meaningful milestone is exact-SHA validation in an isolated checkout/environment. Only after compile/lint/unit verification is genuinely green should the next implementation slice design a production adapter, and even then it should remain unwired from supervisor/daemon until disposable-real-Git integration and recovery tests pass on the verified SHA.
