# Execution Fabric implementation status

Branch: `feature/openworker-governance`
Production base: `main@224046066b0df92544337db0ee623e372629e726` (`v4.18.22`)
Design: `docs/EXECUTION_FABRIC_IMPLEMENTATION_PLAN.md`
Latest fully verified code SHA: `b5c5b447ea6d7a414d17f85b4aad745e72a14de5`
Validation PR: `#81` (`Execution Fabric validation (DO NOT MERGE)`)

## Current boundary

Execution Fabric is now a real, Git-backed workflow engine on this feature branch, but it is still **not automatically wired into the installed/running Local Agent**.

Implemented branch capabilities include:

- immutable workflow manifests and deterministic graph state;
- reusable versioned methods with historical-version compatibility;
- adaptive planner-checkpoint continuations and append-only revision lineage;
- durable effective state across revisions;
- user gates, planner checkpoints and cancellation semantics;
- deterministic child-task identity and existing Local Agent task-contract reuse;
- Git-backed child publication, exact evidence reconciliation and push-ambiguity recovery;
- Git-backed exact `cancel_task` transport;
- one combined lineage execution/cancellation cycle;
- a shared reentrant inter-process control-Git lock used by both normal runtime control writes and workflow transport;
- disposable real-Git/bare-remote integration, race and recovery tests.

Still deliberately absent:

- no supervisor/daemon/worker imports or automatic workflow ticks;
- no launchd/service startup integration for workflow scheduling;
- no background workflow scheduler;
- no Chat Bridge automatic workflow orchestration transport;
- no automatic planner decisions;
- no merge/release integration into `main`.

The distinction is important: **the transport exists; production scheduling does not**.

## Safety invariants retained

Execution Fabric reuses rather than bypasses Local Agent's existing execution model:

- exact repository id and immutable `agent_binding` remain mandatory at dispatch boundaries;
- child tasks are ordinary validated Local Agent tasks with ordinary `task_digest` identities;
- ambiguous/interrupted execution is never automatically replayed;
- exact result/status evidence drives reconciliation;
- cancellation ACK evidence never pretends a task has terminated;
- unrelated standalone repository work makes workflow dispatch yield;
- at most one workflow-owned pending/active child is admitted per repository;
- workflow state/gates/cancellation use durable locks and fail closed on incompatible evidence;
- cross-repository work is represented as separately bound nodes, not one repository task mutating another repository's control state.

## Methods

Built-in methods are immutable by `(name, version, digest)`.

`local_agent/workflow/methods.py` now exposes two different views intentionally:

- `list_builtin_methods()` returns only the latest version for each method name for the normal catalog/CLI;
- `list_builtin_method_versions()` retains the complete immutable version archive;
- `load_builtin_method(name, version=...)` can resolve historical definitions required by persisted manifests;
- omitting `version` resolves the latest definition;
- duplicate name/version identities fail closed.

This permits method evolution without invalidating old workflow manifests pinned to an older digest.

Method validation has both complete and adaptive modes. Adaptive workflows may stop at planner checkpoints before future phases exist, while structural requirements are enforced as soon as their relevant phase appears. Final workflow validation still requires the complete method contract.

Current method-oriented tests include `test_workflow_methods.py`, `test_workflow_adaptive_methods.py` and `test_workflow_cross_repo_method.py`.

## Workflow and revision model

The branch implements:

- workflow schema and DAG validation;
- deterministic manifest SHA-256 identity;
- durable `manifest.json`, authoritative atomic state and append-only audit events;
- deterministic child ids derived from workflow/node identity;
- user gates and planner checkpoints;
- append-only revision records and lineage digests;
- explicit revision activation records;
- isolated durable effective state across activated revisions;
- cancellation that leaves already-running children active until exact terminal evidence arrives;
- no-replay handling for interrupted children;
- recovery when publication succeeded before a local state write.

`local_agent/workflow/lineage_cycle.py` provides one explicit cycle:

```text
exact evidence reconciliation / possible dispatch
-> exact workflow cancellation transport
```

The cycle is intentionally a library façade only. Nothing in daemon/supervisor/worker invokes it automatically.

## Git-backed workflow control plane

`local_agent/workflow/git_control_plane.py` is implemented and remains explicitly unwired from production scheduling.

For an explicitly supplied `RepositoryContext` it can:

- validate the expected Git origin;
- require a normal clean control checkout;
- synchronize the configured control branch;
- require local HEAD to match exact remote state before mutation;
- read bounded regular JSON task/result/status evidence;
- classify child state through the shared workflow evidence model;
- detect unrelated repository work;
- create child tasks with create-only filesystem semantics;
- stage exactly the expected path;
- commit and push workflow child publication;
- reconcile failed/ambiguous pushes against freshly fetched remote evidence;
- fail closed on digest, origin, checkout or publication conflicts.

Temporary-Git tests exercise real commits and real local bare remotes rather than mocked publication only.

## Git-backed cancellation transport

`local_agent/workflow/git_cancellation.py` publishes the existing repository `cancel_task` protocol for the exact workflow child identity.

Properties include:

- deterministic cancellation control id derived from repository id, child task id and expected task digest;
- exact child evidence required before cancellation;
- digest mismatch or absent child fails closed;
- an unrelated outstanding control request causes deferral rather than overwrite;
- repeated exact requests are idempotent;
- accepted/completed/rejected ACK identity is validated;
- ACKs do not directly transition workflow task state;
- push-failure recovery distinguishes proven remote publication, conflict and ambiguity.

The lineage cancellation layer requests cancellation only for exact active workflow children after `cancel_requested` becomes durable.

## Shared control-Git ownership

The ordinary Local Agent runtime and workflow Git transport now use the same locking primitive from `local_agent/foundation/control_git_lock.py`.

The lock provides:

- process-local reentrancy with `threading.RLock`;
- cross-process serialization with `fcntl.flock`;
- one canonical process-local lock object per control checkout;
- a lock file under the checkout's `.git/` directory;
- fail-closed rejection when the target is not a normal Git checkout;
- `DynamicControlGitLock` for legacy runtime code whose `core.CONTROL` changes when a short-lived repository worker is bound;
- nested acquisitions remain attached to the same underlying checkout lock.

This is separate from the long-lived repository execution lease. That separation is required because cancellation must be able to mutate the control branch while the repository worker still owns its execution lease for an active task.

The parallel supervisor runs repository workers as separate processes, so the filesystem lock serializes those independent control-Git writers correctly.

## Current CLI surface

Current workflow CLI is still local/operator-oriented and contains no automatic scheduler.

Available commands include:

```text
methods
method
validate-manifest
preview-manifest
submit
list
show
append-revision
revisions
preview-effective
activations
effective-state
resolve-gate
resolve-checkpoint
cancel
```

There is not yet a CLI command that executes one real Git-backed lineage cycle. That is the next narrow capability slice after this verified baseline.

## Verification

Exact code SHA `b5c5b447ea6d7a414d17f85b4aad745e72a14de5` was validated through draft PR `#81` using the repository's normal PR matrix.

All jobs completed successfully:

- `test` — compile, lint, Chat Bridge validation, unit/integration suite: **success**;
- `coverage`: **success**;
- `python-314`: **success**;
- `macos-smoke`: **success**;
- `bridge-browser`: **success**.

The preceding fixture regression is closed. `tests/test_agentd.py` was restored from the complete pre-regression blob and the net change relative to `ddaf8fe237fdd54295cd6cf99c03335a59089ec2` is exactly one added setup line creating a normal `.git/` directory for the mocked control checkout, with zero deletions.

No installed/running Local Agent was used to execute this validation.

## Next implementation slice

The next narrow feature should be an **explicit operator-driven single workflow cycle**, not an automatic scheduler.

Target behavior:

```text
python -m local_agent.cli.workflow run-cycle <workflow-id>
```

The command should:

1. load the existing repository registry and preserve its exact bindings;
2. construct the existing `WorkflowStore` / revision / activation / effective-state stores;
3. construct `GitWorkflowControlPlane` and `GitWorkflowCancellationTransport`;
4. invoke exactly one `run_lineage_cycle(...)`;
5. print a bounded structured result;
6. exit.

It must not loop, daemonize, change launchd, import itself into the supervisor, or create a second repository configuration system.

Implementation should be TDD-first and preserve `tests/test_workflow_inert_boundary.py`: production daemon/supervisor/worker modules must still not import workflow scheduling code.

Only after an explicit single-cycle path is independently verified should automatic scheduling even be considered.
