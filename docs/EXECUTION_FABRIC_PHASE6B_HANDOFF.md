# Execution Fabric Phase 6B handoff

Branch: `feature/openworker-governance`

This handoff continues `docs/EXECUTION_FABRIC_PHASE6_HANDOFF.md`.

## Safety boundary

The implementation remains deliberately inert with respect to the installed/running Local Agent.

- no production supervisor imports `local_agent.workflow`;
- no daemon/worker/entrypoint/launchd integration exists;
- no production `WorkflowControlPlane` adapter exists;
- no real project control checkout is read/written by production workflow code;
- no task is pushed to a real `.agent/tasks/` directory;
- no service is restarted or reconfigured;
- all coordinator execution remains explicitly invoked from tests or library callers;
- disposable Git work exists only inside `TemporaryDirectory` tests and never pushes a remote.

`tests/test_workflow_inert_boundary.py` now enforces this boundary by failing if production runtime entrypoints import Execution Fabric.

## Activation provenance hardening

`local_agent/workflow/activation.py` now validates:

- exact lowercase `sha256:<64 hex>` digests;
- bounded canonical workflow/checkpoint/new-node ids;
- bounded resolver identity;
- RFC3339 UTC `resolved_at` provenance;
- RFC3339 UTC activation timestamps.

Activation files remain a separate create-only ledger and are not authoritative workflow execution state.

## Isolated effective-state ledger

New module: `local_agent/workflow/effective_state.py`.

Purpose: prove execution semantics for activated revisions without migrating or replacing the existing `WorkflowStore.state.json`.

Persistence:

```text
<state>/workflows/<workflow-id>/effective_state.json
```

Properties:

- initialization requires activation revision 1;
- activation 1 must pin the exact base `node_states` digest;
- activation 1 must pin the exact resolved planner-checkpoint provenance from base state;
- base manifest digest, lineage tip and activation digest are pinned in the effective state;
- base `state.json` remains unchanged;
- task transitions use the existing workflow state machine;
- non-task nodes cannot be advanced through the task transition API;
- planner checkpoints inside revision graphs have durable resolver/note/time provenance in effective state;
- restart reload validates active revision, lineage tip, activation digest, graph node set, dependency normalization and workflow-state classification;
- the next revision can be attached only if its activation pins the exact current effective `node_states` digest, exact checkpoint resolution digest and exact prior lineage tip;
- appending a revision never changes existing node states.

This ledger is still experimental and is not consumed by the production/static coordinator.

## Stable child identity across revisions

A critical identity issue was fixed in `local_agent/workflow/publishing.py`.

Old static identity remains unchanged:

```text
child id = H(workflow id, node id, base manifest digest)
```

For append-only revisions, identity is now pinned to the immutable layer that introduced the node:

```text
base node  -> base manifest digest
rev1 node  -> rev1 digest
rev2 node  -> rev2 digest
...
```

Consequences:

- adding rev2 cannot change a child id introduced in rev1;
- adding any revision cannot change a base child payload/digest;
- a revision child contains exact revision number/digest provenance;
- changing the revision payload changes identities only for nodes introduced by that revision;
- no-replay semantics remain stable as the effective graph grows.

New helpers:

- `node_introduction_identity(...)`
- `materialize_lineage_child_task(...)`
- `materialized_lineage_task_digest(...)`

## Isolated lineage coordinator

New module: `local_agent/workflow/lineage_coordinator.py`.

`tick_lineage_workflow(...)` is a separate, unwired coordinator for activated revision graphs.

It reuses the existing isolated coordinator's deterministic policies:

- exact repository id and agent binding;
- exact evidence digest checks;
- no replay after missing dispatched/running child;
- same-repository serialization;
- unrelated-work yielding;
- deterministic reconciliation;
- publish-before-local-state crash recovery model.

Difference: child tasks are materialized with stable node-introduction identity rather than the current effective-manifest digest.

It is not imported by supervisor/daemon/worker code.

## New tests in Phase 6B

- `tests/test_workflow_activation_validation.py`
- `tests/test_workflow_effective_state.py`
- `tests/test_workflow_lineage_publishing.py`
- `tests/test_workflow_lineage_coordinator.py`
- `tests/test_workflow_inert_boundary.py`

Important scenarios authored:

- malformed/non-lowercase activation digest rejected;
- malformed activation/checkpoint timestamps rejected;
- effective rev1 initialization leaves base state untouched;
- effective task/checkpoint progress survives reconstruction;
- rev2 activation requires the exact state and checkpoint provenance approved by the planner;
- state drift after activation authorization is rejected;
- rev1 child identity remains identical after rev2 is appended;
- base child task is byte-for-byte unchanged by revision lineage;
- rev1 executes, planner resolves checkpoint, rev2 activates and executes through the isolated lineage coordinator;
- restart with an already-published revision child reconciles instead of publishing again;
- production runtime files remain free of workflow imports.

## Validation status

These tests are authored but are not claimed green yet.

The working branch does not receive normal push CI, and the assistant sandbox cannot resolve GitHub DNS. The running Local Agent was deliberately not used as a test executor because the user requested that it remain untouched.

Before any production adapter or runtime wiring, the exact branch SHA must run at minimum:

```bash
python scripts/verify.py --only compile
python scripts/verify.py --only lint
python -m unittest \
  tests.test_workflow_activation \
  tests.test_workflow_activation_validation \
  tests.test_workflow_effective_state \
  tests.test_workflow_lineage_publishing \
  tests.test_workflow_lineage_coordinator \
  tests.test_workflow_inert_boundary \
  tests.test_workflow_revisions \
  tests.test_workflow_revision_store \
  tests.test_workflow_continuation \
  tests.test_workflow_adaptive_methods \
  tests.test_workflow_temporary_git_integration
```

Then run the complete repository verification before any release decision:

```bash
python scripts/verify.py
```

## Still deliberately not wired

- production Git-backed workflow control plane;
- supervisor/daemon tick integration;
- remote repository fetch/push for workflow orchestration;
- active-child workflow cancellation transport;
- Chat Bridge orchestration transport;
- remote user/planner wait transport;
- migration of revision execution state into the existing authoritative `state.json`;
- service lifecycle/update integration.

## Recommended next safe work

Without touching the running Local Agent:

1. add durable user-gate resolution to the isolated effective-state ledger;
2. add cancellation semantics to the isolated lineage coordinator/effective state;
3. add a test-only temporary-Git lineage coordinator scenario spanning rev1 -> rev2;
4. add read-only CLI inspection for activations/effective state;
5. perform another branch-only architecture audit;
6. stop before creating any production Git adapter unless exact-SHA tests are green and the safety boundary is explicitly lifted.
