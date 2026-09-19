# Execution Fabric — handoff for next chat

Branch: `feature/openworker-governance`
Status: **parked after a clean manual-execution milestone**
Production base: `main@224046066b0df92544337db0ee623e372629e726` (`v4.18.22`)
Verified code freeze: `09210f66972158a13da8646cce4db11f35d341c8`
Validation PR: `#81` — draft, `DO NOT MERGE`
Canonical current status: `docs/EXECUTION_FABRIC_IMPLEMENTATION_STATUS.md`
Historical design: `docs/EXECUTION_FABRIC_IMPLEMENTATION_PLAN.md`

## Start here next time

Do not continue from memory alone.

Read fresh, in this order:

```text
AGENTS.md
docs/EXECUTION_FABRIC_HANDOFF_NEXT_CHAT.md
docs/EXECUTION_FABRIC_IMPLEMENTATION_STATUS.md
docs/EXECUTION_FABRIC_IMPLEMENTATION_PLAN.md
```

Use the older `EXECUTION_FABRIC_PHASE6*_HANDOFF.md` documents only as decision history when a specific earlier rationale is needed. They are not the current continuation instructions.

Before any write, refresh:

```text
main
feature/openworker-governance
PR #81 status/checks
```

Do not assume the SHAs in this document are still branch heads. They describe the clean stop point only.

The `local-agent` GitHub repository did not expose an `agent-control` ref during this stage. Do not invent one or treat its absence as a reason to modify production configuration.

## Why this stage was stopped here

The goal of this session shifted from further feature growth to leaving the work in a clean, resumable state.

That goal is met:

- the workflow engine has a real Git-backed transport;
- exact cancellation transport exists;
- control-Git ownership is serialized with the ordinary Local Agent runtime;
- append-only revisions/effective state are implemented;
- there is an explicit one-cycle runner;
- there is a complete manual operator surface for activated lineage graphs;
- the full repository CI matrix is green on the exact code-freeze SHA;
- there is still no automatic production scheduler or Chat Bridge orchestration wiring.

This is a useful boundary because the next change is no longer “finish the isolated engine”. It is a product/architecture decision about **how and when the isolated engine becomes an automatically owned production subsystem**.

## Exact verified baseline

Code SHA:

```text
09210f66972158a13da8646cce4db11f35d341c8
```

GitHub Actions:

```text
local-agent CI #891
run id: 35454026351
```

All jobs succeeded:

```text
test            success
coverage        success
python-314      success
macos-smoke     success
bridge-browser  success
```

The `test` job includes compile, lint, Chat Bridge validation and unit/integration tests.

Earlier immediately relevant green baseline:

```text
e16f9c9424d5d3a47298241ab344ab344e053c2a
CI #887 — success
```

The final code-freeze SHA supersedes it.

## Current feature boundary

### Implemented

Execution Fabric currently includes:

```text
workflow contracts
DAG state machine
versioned methods
workflow durable store
user gates
planner checkpoints
child task materialization
multi-repository exact binding validation
append-only revisions
activation ledger
effective-state ledger
lineage coordinator
exact evidence reconciliation
no-replay interrupted handling
Git-backed child publication
Git-backed exact cancel_task transport
shared control-Git lock
one explicit lineage cycle
manual lineage activation/control CLI
```

### Explicit manual commands added near the stop point

```text
activate-next
resolve-effective-checkpoint
resolve-effective-gate
cancel-effective
run-cycle
```

`run-cycle` performs exactly one lineage execution/cancellation cycle and exits.

It is not a scheduler.

### Still deliberately absent

```text
supervisor-owned workflow scheduler
daemon-owned workflow scheduler
launchd workflow service
automatic periodic ticks
Chat Bridge orchestration identity
automatic wake on planner/user/failure/completion events
production migration/release path
multi-machine runner placement
```

## Important architecture invariants

Do not weaken these to make future integration easier.

### ChatGPT remains the planner

Local Agent stays model-free.

Do not add:

- embedded LLM providers;
- hidden planner/reviewer models;
- natural-language planning inside the executor.

### Repository binding remains exact

Every executable child still belongs to exactly one registered repository and exact `agent_binding`.

Cross-repository workflow orchestration means several separately bound child tasks. It does **not** mean one project task receives permission to mutate arbitrary other repository control planes.

### Existing task execution remains authoritative

Keep:

- existing task contract;
- immutable task digest;
- claims;
- watchdogs/timeouts;
- resource leases;
- checkpoints;
- no automatic replay after ambiguous/interrupted execution;
- exact terminal result evidence.

Execution Fabric coordinates those primitives; it must not replace them.

### Git control ownership remains shared

Normal runtime control writes and workflow Git transport must continue using the same canonical control-Git locking primitive.

Do not introduce a second independent lock namespace for the same checkout.

### Cancellation ACK is not terminal evidence

An accepted/completed repository `cancel_task` ACK proves only that the control request was handled.

Workflow node state must still reconcile from exact child task/result/status evidence.

### Production runtime import boundary remains frozen until explicitly reopened

Do not casually import workflow scheduling into:

```text
local_agent/entrypoint.py
local_agent/daemon/service.py
local_agent/supervisor/orchestrator.py
local_agent/supervisor/serial.py
local_agent/supervisor/worker.py
local_agent/repository/worker.py
local_agent/platform/macos_launchd.py
```

The inert-boundary test exists specifically to prevent accidental integration.

## Recent stop-point implementation

### Shared Git ownership

The feature introduced one shared control-Git lock used by both normal runtime control writes and workflow transport.

The daemon test fixture regression caused by requiring a normal `.git/` checkout was fixed by restoring the complete previous fixture and adding exactly one `.git` setup line. The net change against the known-good parent was verified as one addition and zero deletions.

### Explicit `run-cycle`

The CLI now builds:

```text
existing repository registry
WorkflowStore
WorkflowRevisionStore
WorkflowRevisionActivationStore
WorkflowEffectiveStateStore
GitWorkflowControlPlane
GitWorkflowCancellationTransport
```

and invokes exactly one `run_lineage_cycle(...)`.

An explicitly supplied missing `--registry` fails closed before Git transport construction rather than silently falling back to the legacy repository.

### Manual activated-lineage controls

`local_agent/workflow/lineage_operator.py` provides explicit revision activation.

It handles:

- first activation from base state;
- later activation from effective state;
- append-only activation records;
- effective-state application;
- a separate inter-process operator activation lock preventing two manual activators from accidentally advancing two revisions concurrently.

The CLI keeps base-state and effective-state mutations visibly separate instead of silently changing old command semantics.

## Files most relevant when resuming

Core workflow model:

```text
local_agent/workflow/contract.py
local_agent/workflow/state.py
local_agent/workflow/methods.py
local_agent/workflow/store.py
local_agent/workflow/revisions.py
local_agent/workflow/revision_store.py
local_agent/workflow/activation.py
local_agent/workflow/effective_state.py
```

Execution/evidence path:

```text
local_agent/workflow/publishing.py
local_agent/workflow/evidence.py
local_agent/workflow/coordinator.py
local_agent/workflow/lineage_coordinator.py
local_agent/workflow/lineage_cancellation.py
local_agent/workflow/lineage_cycle.py
```

Git side effects:

```text
local_agent/workflow/git_control_plane.py
local_agent/workflow/git_cancellation.py
local_agent/foundation/control_git_lock.py
```

Manual operator boundary:

```text
local_agent/workflow/lineage_operator.py
local_agent/cli/workflow.py
```

Architecture guard:

```text
tests/test_workflow_inert_boundary.py
```

Newest operator tests:

```text
tests/test_workflow_cli.py
tests/test_workflow_operator_cli.py
```

## Recommended next stage

Do **not** start by wiring a scheduler.

Start with a pre-integration audit.

### Step 1 — refresh and re-prove the stop point

Check fresh:

```text
main SHA
feature branch SHA
PR #81 CI
branch diff against main
```

Re-read the status/handoff and inspect changes after the code-freeze SHA. If only documentation moved, treat `09210f...` as the last verified implementation baseline.

### Step 2 — public-CLI disposable end-to-end scenario

Before automatic integration, prove the operator-facing path using disposable repositories/control branches and the public CLI only.

Target scenario:

```text
submit workflow
-> complete/reconcile base audit
-> resolve base planner checkpoint
-> append revision 1
-> activate-next
-> run-cycle publishes exact child
-> child exact success evidence appears
-> run-cycle reconciles
-> resolve-effective-checkpoint
-> append revision 2
-> activate-next
-> run-cycle publishes next-repo child
-> cancel-effective while an exact child is active
-> run-cycle emits exact cancel_task request
-> terminal child evidence reconciles
```

Do not use the installed/running Local Agent for this proof. Use disposable/local Git fixtures or an explicitly isolated test environment.

### Step 3 — recovery/race audit

Audit at least:

- concurrent `activate-next` calls;
- process death after activation record but before effective-state apply;
- process death after child Git commit but before push confirmation;
- concurrent normal runtime control write vs workflow publication;
- cancellation request collision with an unrelated control request;
- stale repository registry/binding changes between revisions;
- explicit `--registry` path replacement/symlink edge cases;
- workflow state corruption isolation.

Only fix correctness defects discovered here. Do not add broad new features in the same slice.

### Step 4 — choose production scheduler ownership

Make an explicit architecture decision between likely options such as:

```text
A. supervisor-owned bounded workflow ticker
B. separate workflow service/process
C. another explicit wake/event mechanism
```

Evaluate:

- process ownership;
- crash isolation;
- startup/restart lifecycle;
- interaction with repository workers;
- global disable/emergency controls;
- update/rollback behavior;
- control-Git lock ownership;
- CPU/wake overhead;
- how waiting workflows avoid polling aggressively.

Do not infer the answer from the existing isolated code.

### Step 5 — implement one narrow integration slice only after approval

If supervisor ownership wins, a first integration should likely be:

```text
bounded discovery of runnable workflows
-> one explicit lineage cycle per selected workflow
-> no planner inference
-> no Bridge wake integration yet
-> existing emergency disable respected
-> no new child execution primitive
```

Keep the integration reversible and guarded by tests.

### Step 6 — Chat Bridge later

Only after automatic local scheduling is independently stable should Chat Bridge gain an orchestration identity / wake protocol.

Bridge should wake on meaningful durable transitions, not every low-level heartbeat:

```text
waiting_planner
waiting_user / user decision
failed
completed
```

Ordinary project chats must retain exact repository binding.

## Work intentionally postponed

Do not mix these into the first resumed slice:

- remote/multi-machine runner scheduling;
- Android/RPi distributed runners;
- generic workflow artifact bus;
- generic connector/provider system;
- embedded model/reviewer;
- priority preemption;
- automatic retry of interrupted tasks;
- release packaging;
- branch merge into `main`.

## Validation discipline when work resumes

Use TDD for the selected narrow slice.

Minimum sequence:

```text
focused tests for changed subsystem
-> compile/lint
-> relevant integration/recovery tests
-> full repository verification / PR matrix
```

Do not claim a code SHA verified from a later documentation-only SHA. Record the exact implementation SHA actually exercised by CI.

For any production-runtime wiring change, re-run and preserve the architecture/security invariants around:

- exact bindings;
- task digests/claims;
- no replay;
- emergency disable;
- control-Git locking;
- self-update rollback;
- resource leases;
- ordinary task coexistence.

## Merge/release status

**Do not merge PR #81 as-is.**

The PR was intentionally created as a validation vehicle for this feature branch.

Before any merge decision, perform a separate release/integration review covering:

- whether the feature should be split/squashed;
- migration/backward compatibility;
- operator documentation;
- production ownership;
- security boundary review;
- release versioning;
- final full validation from the intended release commit.

## Clean stop summary

At the pause point:

```text
main unchanged
verified code freeze green
manual Execution Fabric path available
production scheduler absent
Chat Bridge orchestration absent
installed/running Local Agent untouched
feature PR remains draft / DO NOT MERGE
```

That is intentional. Resume from this boundary rather than trying to “finish” the feature by immediately wiring it into production.
