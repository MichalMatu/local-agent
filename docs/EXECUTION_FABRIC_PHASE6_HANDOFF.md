# Execution Fabric Phase 6 handoff

Branch: `feature/openworker-governance`

Safety boundary: all work in this document is branch-only and inert with respect to the installed/running Local Agent. No supervisor/worker/daemon wiring was changed. No production Git-backed workflow adapter exists. No project control branch was read or mutated by the workflow engine during this work.

## Implemented in this slice

### Append-only workflow revisions

New module: `local_agent/workflow/revisions.py`.

A continuation record contains:

- `schema_version`;
- exact `workflow_id`;
- contiguous positive `revision` number;
- `created_at`;
- exact `parent_digest`;
- `checkpoint_node_id` from the prior effective graph;
- append-only `nodes`.

Properties:

- revision 1 pins the immutable base manifest digest;
- revision N pins the digest of revision N-1;
- skipped/reordered revisions are rejected;
- existing node ids cannot be replaced;
- new dependencies are checked by the normal workflow DAG validator;
- the referenced checkpoint must already exist in the prior graph and be a `planner_checkpoint`;
- every newly appended node must be a descendant of that checkpoint, so a continuation cannot create an independent side path that bypasses planner review;
- effective manifests are built by copying the base and appending revision nodes; inputs are never mutated;
- lineage tip digest is explicit.

### Durable revision store

New module: `local_agent/workflow/revision_store.py`.

Persistence layout:

```text
<state>/workflows/<workflow-id>/
  manifest.json
  state.json
  revisions/
    000001.json
    000002.json
    ...
```

Properties:

- create-only files with `O_EXCL`;
- identical repeated append is idempotent;
- conflicting retry for an existing revision fails closed;
- revision numbering must be contiguous;
- every read revalidates the complete lineage;
- tampering with a parent digest breaks reload;
- state is reconstructable after restart from immutable files;
- no repository dispatch occurs from this store.

### Adaptive Methods across revisions

Workflow contract now supports explicit:

```json
"method_mode": "adaptive"
```

Rules:

- absence of `method_mode` preserves the existing static behavior;
- static workflow Methods still require all phases at normal manifest admission;
- `method_mode` without a pinned Method reference is rejected;
- adaptive workflows keep exact Method name/version/digest identity;
- adaptive base graph must contain the first required Method phase;
- structural requirements are enforced as soon as their phase appears;
- e.g. a present `full_verification` phase must already use `efficient-verification-v1`;
- missing future phases are allowed while the planner is between checkpoints;
- `validate_complete_workflow_manifest()` / `validate_effective_method_complete()` require the full Method contract on the final effective graph.

This lets a `deep-refactor` lineage be expressed as:

```text
rev0: audit -> planner checkpoint
rev1: implementation -> focused verification -> ...
rev2: full verification -> final review
```

without weakening ordinary static workflows.

### Pure continuation activation semantics

New module: `local_agent/workflow/continuation.py`.

`project_next_revision_states(...)` defines the activation contract without persistence or dispatch:

- caller must provide exact state keys for the prior effective graph;
- prior state must already be dependency-normalized;
- referenced checkpoint must be `succeeded`;
- existing node states are immutable and cannot regress/change;
- only new revision nodes begin as `pending`;
- readiness of new nodes is calculated by the existing workflow state machine.

This is intentionally a pure projection. It does not yet modify `WorkflowStore.state.json` and is not consumed by the coordinator.

### Local CLI for revision inspection

New commands:

```bash
python -m local_agent.cli.workflow --state-dir <dir> \
  append-revision <workflow-id> <revision.json>

python -m local_agent.cli.workflow --state-dir <dir> \
  revisions <workflow-id>

python -m local_agent.cli.workflow --state-dir <dir> \
  preview-effective <workflow-id>
```

These commands only operate on local workflow persistence. They do not dispatch child tasks or contact repository control branches.

### End-to-end in-memory scenario

`tests/test_workflow_end_to_end_in_memory.py` models:

```text
audit
  -> planner checkpoint
  -> simulated restart
  -> backend || android || firmware
  -> barrier
  -> user gate
  -> release
  -> completed
```

All repository execution evidence is in-memory/fake. It exercises durable planner/user decisions and restart reconstruction without the production Local Agent.

### Disposable temporary-Git integration harness

`tests/test_workflow_temporary_git_integration.py` adds a test-only `DisposableGitControlPlane`.

It uses only `TemporaryDirectory` Git repositories with local `agent-control` branches. It never pushes and is not imported by production code.

The test covers:

- three independent control checkouts;
- child task JSON written to the correct repository only;
- real local Git commits of `.agent/tasks/<id>.json`;
- result JSON reconciliation through the real evidence classifier;
- barrier completion;
- unrelated standalone task causing only the affected repository to yield.

This is the intended bridge toward a future production Git adapter while preserving the current safety boundary.

## Tests authored in this slice

- `tests/test_workflow_revisions.py`
- `tests/test_workflow_revision_store.py`
- `tests/test_workflow_revision_cli.py`
- `tests/test_workflow_adaptive_methods.py`
- `tests/test_workflow_continuation.py`
- `tests/test_workflow_end_to_end_in_memory.py`
- `tests/test_workflow_temporary_git_integration.py`

The branch still does not receive automatic push CI. The assistant sandbox cannot resolve GitHub DNS, so these tests have not been executed on the exact branch SHA. Do not claim green validation yet.

## Still deliberately not implemented

- no persistence/activation of revision node states into authoritative `WorkflowStore.state.json`;
- no coordinator consumption of an effective base+revision manifest;
- no production `WorkflowControlPlane` implementation;
- no remote fetch/push of project control branches;
- no workflow tick in supervisor/daemon;
- no service restart/update;
- no active-child cancellation transport;
- no Chat Bridge orchestration transport;
- no remote user-gate or planner-checkpoint transport.

## Recommended next safe slice

Continue without touching the running Local Agent:

1. define a durable **revision activation record** that pins:
   - revision number/digest;
   - checkpoint resolution provenance;
   - prior lineage tip;
   - projected new node states;
2. keep activation state separate from the base `state.json` until migration semantics are proven;
3. add restart/tamper/idempotency tests for activation records;
4. extend the disposable Git harness with crash-after-local-commit recovery and digest mismatch cases;
5. only after exact-SHA compile/lint/unit verification, consider a production Git adapter that is still not wired into supervisor.

Do not modify the production supervisor/worker/daemon path while this handoff remains the active safety boundary.
