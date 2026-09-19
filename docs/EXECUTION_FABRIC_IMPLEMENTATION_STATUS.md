# Execution Fabric implementation status

Branch: `feature/openworker-governance`
Production base: `main@224046066b0df92544337db0ee623e372629e726` (`v4.18.22`)
Code-freeze SHA for this stage: `09210f66972158a13da8646cce4db11f35d341c8`
Validation PR: `#81` — `Execution Fabric validation (DO NOT MERGE)`
Canonical continuation handoff: `docs/EXECUTION_FABRIC_HANDOFF_NEXT_CHAT.md`

## Stage status

**Parked cleanly. No further code work is planned in this stage.**

Execution Fabric is implemented far enough on this feature branch to provide a real manual, Git-backed workflow substrate, while remaining deliberately disconnected from automatic production scheduling.

The installed/running Local Agent was not modified or used as the execution mechanism for this branch work. `main` remains unchanged.

The branch now has a deliberate split:

```text
ChatGPT / operator
        |
        v
explicit workflow CLI
        |
        v
Execution Fabric stores + lineage coordinator
        |
        v
Git-backed repository task/control planes
        |
        v
existing Local Agent repository workers
```

What is **not** present is equally important:

```text
no supervisor workflow loop
no daemon workflow loop
no launchd workflow service
no automatic Chat Bridge orchestration
no embedded LLM/model provider
no production merge/release
```

## Verified code baseline

Exact code SHA:

```text
09210f66972158a13da8646cce4db11f35d341c8
```

GitHub Actions run:

```text
local-agent CI #891
run id: 35454026351
```

All jobs completed successfully:

- `test` — compile, lint, Chat Bridge validation, unit/integration tests: **success**;
- `coverage`: **success**;
- `python-314`: **success**;
- `macos-smoke`: **success**;
- `bridge-browser`: **success**.

This is the code baseline to preserve when future work resumes. Documentation-only commits after this SHA do not change that verified implementation baseline.

## Implemented capabilities

### Workflow contracts and durable state

Implemented:

- immutable workflow manifests;
- deterministic manifest/revision/task identities;
- DAG validation and dependency state transitions;
- bounded durable workflow state;
- exact child-task materialization;
- exact result/status evidence reconciliation;
- no automatic replay after ambiguous/interrupted execution;
- barriers, user gates and planner checkpoints;
- append-only revision lineage;
- durable activation records;
- isolated effective state for activated revision graphs.

### Versioned methods

Built-in methods are immutable by name/version/digest.

The catalog supports:

- latest-version discovery;
- historical version loading for persisted workflows;
- adaptive method validation across planner-checkpoint continuations;
- final full-contract validation.

Current built-in method work includes `deep-refactor`, `cross-repo-api-change` and `release-candidate`.

### Multi-repository orchestration

Workflow task nodes keep exact repository ownership:

```text
node
  -> repository_id
  -> exact agent_binding
  -> ordinary Local Agent task contract
```

A workflow does not gain a generic cross-repository shell. Each child remains an ordinary task for exactly one registered repository.

The coordinator yields instead of taking over a repository that has unrelated standalone work.

### Git-backed child publication

`local_agent/workflow/git_control_plane.py` provides a real Git-backed adapter for explicitly supplied repository contexts.

It includes:

- expected-origin validation;
- exact configured control branch synchronization;
- clean-checkout requirements;
- bounded regular-file JSON evidence reads;
- create-only child task publication;
- exact staged-path checks;
- commit/push publication;
- failed/ambiguous push recovery against freshly fetched remote evidence;
- fail-closed digest/origin/checkout/publication conflict handling.

### Git-backed cancellation

`local_agent/workflow/git_cancellation.py` implements the existing repository `cancel_task` protocol for exact workflow-owned children.

Cancellation:

- is bound to repository id, task id and expected task digest;
- refuses missing or mismatched child evidence;
- does not overwrite unrelated outstanding control requests;
- validates ACK identity/status;
- never treats an ACK as terminal child evidence;
- remains idempotent for the same exact request.

### Shared control-Git locking

`local_agent/foundation/control_git_lock.py` is shared by normal Local Agent control-Git writes and workflow Git transport.

It provides:

- process-local reentrancy;
- inter-process `flock` serialization;
- one canonical lock identity per control checkout;
- dynamic binding support for legacy runtime control checkout changes;
- fail-closed behavior for non-normal Git checkouts.

This prevents independent Local Agent processes and workflow transport from concurrently corrupting the same control checkout.

### One explicit lineage cycle

`local_agent/workflow/lineage_cycle.py` combines exactly one:

```text
reconcile/dispatch cycle
-> exact workflow cancellation cycle
```

The CLI exposes it explicitly as:

```bash
python -m local_agent.cli.workflow \
  --state-dir <state-dir> \
  --registry <repositories.json> \
  run-cycle <workflow-id>
```

Important properties:

- exactly one cycle;
- no loop;
- no daemonization;
- no scheduler;
- uses the existing repository registry and exact bindings;
- an explicitly supplied missing registry fails before Git transport construction;
- bounded JSON result only.

### Manual lineage operator controls

The branch now has an explicit manual path for operating activated revision graphs without changing the semantics of older base-state CLI commands.

Commands:

```text
activate-next
resolve-effective-checkpoint
resolve-effective-gate
cancel-effective
run-cycle
```

`activate-next` uses `local_agent/workflow/lineage_operator.py` and:

- creates the first activation from authoritative base workflow state;
- creates later activations from authoritative effective state;
- preserves append-only revision semantics;
- uses a dedicated inter-process operator activation lock so concurrent manual activators cannot advance two revisions accidentally;
- keeps existing store-level create-only/idempotent behavior.

Older commands such as `resolve-gate`, `resolve-checkpoint` and `cancel` retain their existing base-state meaning. Effective-state mutation is deliberately explicit in the command name.

## Runtime boundary still frozen

Production runtime owners remain outside workflow scheduling.

The architectural guard continues to require that these paths do not import workflow scheduling code:

```text
local_agent/entrypoint.py
local_agent/daemon/service.py
local_agent/supervisor/orchestrator.py
local_agent/supervisor/serial.py
local_agent/supervisor/worker.py
local_agent/repository/worker.py
local_agent/platform/macos_launchd.py
```

No automatic workflow tick is triggered by:

- daemon startup;
- supervisor startup;
- repository worker startup;
- launchd;
- Chat Bridge.

That boundary is intentional and should survive the pause.

## Current CLI surface

The workflow CLI now contains both read-only/authoring commands and explicit manual execution controls:

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
activate-next
resolve-gate
resolve-checkpoint
cancel
resolve-effective-gate
resolve-effective-checkpoint
cancel-effective
run-cycle
```

This is enough to exercise the workflow engine manually without making it an always-on production subsystem.

## Repository cleanup / stage boundary

At code freeze:

- `main` is still `224046066b0df92544337db0ee623e372629e726`;
- feature code baseline is `09210f66972158a13da8646cce4db11f35d341c8`;
- draft PR `#81` remains validation-only and must not be merged as-is;
- no production service configuration was changed;
- no workflow scheduler was installed;
- no temporary runtime integration was added;
- historical `EXECUTION_FABRIC_PHASE6*_HANDOFF.md` files are retained as decision history, not as current instructions;
- `docs/EXECUTION_FABRIC_HANDOFF_NEXT_CHAT.md` is the canonical restart point.

## Work intentionally deferred

Do not continue these automatically just because the code exists:

1. production scheduler/supervisor ownership;
2. automatic periodic workflow ticks;
3. Chat Bridge orchestration identity/transport;
4. automatic wake-up on `waiting_planner`/failure/completion;
5. production packaging/release/migration;
6. remote multi-machine runners;
7. generic artifact/export DSL;
8. merging this feature branch into `main`.

These require a fresh decision after the pause.

## Recommended next milestone when work resumes

The next stage should start with a **pre-integration audit**, not immediate wiring.

First determine whether the manual Execution Fabric API and state model should be treated as the release candidate contract. Then choose one narrow integration target.

Preferred order:

```text
1. fresh branch/main/CI audit
2. manual end-to-end disposable multi-repo scenario using the public CLI
3. recovery/race audit of operator activation + run-cycle boundary
4. decide ownership model for automatic scheduling
5. only then implement one scheduler integration slice
6. keep Chat Bridge automation later
```

The likely first production integration, if approved, is a bounded supervisor-owned scheduler/tick mechanism that invokes the already-tested lineage cycle. It must not weaken bindings, task claims, no-replay semantics, repository leases, emergency controls or shared control-Git ownership.

See `docs/EXECUTION_FABRIC_HANDOFF_NEXT_CHAT.md` for the exact restart instructions and stop gates.
