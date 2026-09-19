# Execution Fabric implementation status

Branch: `feature/openworker-governance`
Production base: `main@224046066b0df92544337db0ee623e372629e726` (`v4.18.22`)
Design: `docs/EXECUTION_FABRIC_IMPLEMENTATION_PLAN.md`

Status: implementation in progress. The current branch adds workflow contracts, methods, durable local state, deterministic child-task materialization, an isolated coordinator, pure repository-evidence classification and durable user gates. It does **not** dispatch workflow child tasks to real repository control branches and does not change or call the production supervisor/worker execution path.

## Safety boundary of the current branch

Current workflow code is deliberately inert with respect to the installed/running Local Agent:

- no workflow coordinator is called from `local_agent/supervisor/orchestrator.py` or the serial supervisor;
- no production `WorkflowControlPlane` adapter exists;
- no workflow code writes to a real project `.agent/tasks/` directory;
- no workflow code commits or pushes an `agent-control` branch;
- no workflow code starts/restarts/stops the Local Agent service;
- no workflow code reads or mutates the installed machine registry unless a future caller explicitly supplies repository contexts;
- coordinator tests use injected in-memory/fake control planes only;
- CLI workflow state can be redirected with `--state-dir` and has no command that performs repository dispatch.

This boundary must remain in place until the exact branch SHA has been verified and real temporary-Git integration tests prove publication/recovery semantics.

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
  - exact-evidence recovery transitions from local `ready` after a crash that occurred after child publication;
  - interrupted child state maps to planner intervention rather than replay;
  - cancelled workflows remain `running` only while another child is active, then become terminal `cancelled` even when dependent nodes are blocked.

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
- a separate workflow execution lock serializes coordinator dispatch/reconciliation with operator cancellation/gate resolution;
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

### Phase 2 slice C — isolated coordinator semantics

Implemented in `local_agent/workflow/coordinator.py` behind an injected `WorkflowControlPlane` protocol.

The coordinator currently proves policy without a production transport:

- exact repository id and exact `agent_binding` are required before inspection/dispatch;
- different ready repositories may be selected in one tick;
- at most one workflow-owned pending/active child is selected per repository;
- unrelated active/pending standalone work makes workflow dispatch yield;
- exact existing child evidence is reconciled before any new publication attempt;
- a local `ready` node can recover from exact remote pending/running/terminal evidence after a crash;
- local `dispatched`/`running` with a remotely absent child is an integrity error and is never replayed;
- child digest mismatch fails closed;
- terminal success/failure/interruption/cancellation transition the graph deterministically;
- publication is defined to happen before the local `dispatched` state write, so a crash in that window is recovered by deterministic child id/digest instead of duplicate publication;
- workflow cancellation is serialized against the dispatch critical section by the workflow execution lock.

The only coordinator control planes currently used are fakes inside tests. No Git-backed implementation exists or is wired.

### Phase 2 slice D — pure evidence classification

Implemented in `local_agent/workflow/evidence.py` with no I/O.

It classifies existing repository payloads as:

```text
absent
pending
running
succeeded
failed
cancelled
interrupted
digest_mismatch
```

Important mappings reuse current Local Agent semantics:

- result `status=done` -> succeeded;
- `cancelled_by_operator` -> cancelled;
- `interrupted_previous_attempt` / `corrupt_claim_state` -> interrupted/no replay;
- exact daemon `current_task_id` + `current_task_digest` -> running;
- any available child digest mismatch -> fail closed.

Repository-yield classification requires exact terminal evidence for unrelated queued work. A malformed/non-terminal result file does not make an unrelated task disappear.

### Phase 4 local slice — durable user gates

The local persistence portion of user gates was implemented early because it is independent from remote transport.

`WorkflowStore.resolve_user_gate(...)` provides:

- allowed-choice validation from the immutable manifest;
- exact workflow/manifest/node provenance;
- resolver identity and timestamp;
- first resolver wins;
- repeated identical decision is idempotent;
- conflicting second decision is rejected;
- decision provenance and `waiting_user -> succeeded` transition are persisted in the same atomic `state.json` replacement;
- execution lock serializes resolution against coordinator activity and cancellation.

CLI:

```bash
python -m local_agent.cli.workflow resolve-gate \
  <workflow-id> <node-id> <decision> --resolver <identity>
```

There is still no remote/Chat Bridge gate transport.

## Tests added

- `tests/test_workflow_contract.py`
- `tests/test_workflow_state.py`
- `tests/test_workflow_methods.py`
- `tests/test_workflow_store.py`
- `tests/test_workflow_publishing.py`
- `tests/test_workflow_coordinator.py`
- `tests/test_workflow_coordinator_cancel.py`
- `tests/test_workflow_evidence.py`
- `tests/test_workflow_gates.py`
- `tests/test_workflow_cli.py`
- `tests/fixtures/workflows/*.json`

Coverage includes contract bounds, cycles, bindings, method digests/structure, state transitions, barriers, wait states, terminal non-regression, crash-after-publication recovery policy, no-replay interruption, digest mismatch, same-repository serialization, unrelated-work yielding, cancellation reconciliation, durable-store idempotency/corruption/cancellation, atomic gate resolution, CLI lifecycle and deterministic child-task materialization.

These test files have been authored on the branch; this document does **not** claim they have executed successfully because this branch does not receive automatic push CI.

## Deliberately not implemented or wired yet

The following remain outside the current safe/inert boundary:

- a production/Git-backed `WorkflowControlPlane` adapter;
- writing child tasks into a real target repository `.agent/tasks/` path;
- Git commit/push of workflow-owned child tasks;
- live target repository control checkout synchronization;
- real result/run/status reads from project control branches by the workflow engine;
- exact `cancel_task` publication for active workflow children;
- supervisor integration/tick scheduling;
- service startup/restart integration;
- remote workflow transport;
- Chat Bridge orchestration identity;
- planner-checkpoint continuation/revision transport;
- append-only workflow revisions/continuations;
- remote user-gate resolution transport.

This boundary is intentional. Git publication is the first part of the feature that can cause real repository execution side effects and must not be enabled until isolated verification is complete.

## Validation status

No production claim is made for this branch.

Repository CI currently runs on pushes to `main`, `v*-staging`, `work/**`, and on pull requests. Direct pushes to `feature/openworker-governance` therefore do not automatically produce the normal CI matrix.

Before adding any production Git adapter or wiring coordinator ticks, run on the exact branch SHA at minimum:

```bash
python scripts/verify.py --only compile
python scripts/verify.py --only lint
python -m unittest \
  tests.test_workflow_contract \
  tests.test_workflow_state \
  tests.test_workflow_methods \
  tests.test_workflow_store \
  tests.test_workflow_publishing \
  tests.test_workflow_coordinator \
  tests.test_workflow_coordinator_cancel \
  tests.test_workflow_evidence \
  tests.test_workflow_gates \
  tests.test_workflow_cli
```

Then run the normal full repository verification before release integration:

```bash
python scripts/verify.py
```

The eventual release candidate still requires the repository's normal full CI matrix and exact-SHA macOS smoke.

## Next safe implementation slices without touching the running agent

The next work can remain completely isolated from production:

1. make the workflow audit event stream explicitly best-effort so an audit-write failure cannot report a false mutation failure after authoritative `state.json` already committed;
2. add planner-checkpoint durable metadata and explicit local continuation contracts without dispatch transport;
3. add a fake/in-memory end-to-end three-repository graph fixture that exercises audit -> parallel nodes -> barrier -> user/planner wait;
4. design, but do not wire, the Git control-plane adapter interface and temporary-Git integration harness;
5. only after exact-SHA verification, implement the adapter against disposable temporary repositories before considering any supervisor integration.

Do not modify the production supervisor loop and do not point workflow code at the installed Local Agent state/control checkouts while this safety boundary is active.
