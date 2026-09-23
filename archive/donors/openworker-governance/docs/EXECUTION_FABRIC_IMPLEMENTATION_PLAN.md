# Local Agent Execution Fabric — implementation plan

Status: implementation design only. No runtime behavior changed yet.

Base production: `main@224046066b0df92544337db0ee623e372629e726` (`v4.18.22`).
Design branch: `feature/openworker-governance`.

## 1. Goal

Evolve Local Agent from a bounded multi-repository command executor into an **execution fabric for ChatGPT** without moving planning or an LLM into the executor.

The target user experience is:

```text
User / ChatGPT
      |
      v
Method / workflow goal
      |
      v
Workflow graph
  |       |       |
  v       v       v
repo A  repo B  repo C
  |       |       |
 existing Local Agent workers
  |       |       |
 results / evidence
      |
      v
planner checkpoint / next graph phase / completion
```

A request such as:

> Change protocol v2 in backend, Android and firmware, run the correct tests in parallel, then verify integration and prepare release evidence.

should become one durable workflow with several repository-scoped task nodes, not a loose collection of unrelated chats/tasks.

The existing execution model remains authoritative:

- ChatGPT plans.
- Local Agent validates and executes deterministic payloads.
- Every executable project task still has one exact repository id and `agent_binding`.
- Existing repository workers, claims, task digests, watchdogs, resource leases and terminal results remain the execution primitive.
- Interrupted claimed work is never automatically replayed.

The new layer coordinates **existing tasks**; it does not replace their safety/recovery model.

---

# 2. What this adds

Four capabilities are the core scope.

## A. Methods

Reusable, versioned workflow recipes such as:

- `deep-refactor`
- `security-audit`
- `release-candidate`
- `dependency-upgrade`
- `firmware-validation`
- `cross-repo-api-change`
- `repo-cleanup`

A method describes the shape and requirements of good work. ChatGPT still supplies the concrete plan/commands for the actual repository and goal.

This removes repeated prompt boilerplate and makes proven workflows reusable.

## B. Task graph

A workflow becomes a DAG rather than a flat task list.

Example:

```text
               +--> backend implementation --> backend verify --+
contract audit |                                            |
               +--> firmware implementation -> firmware verify -+--> integration
               |                                            |
               +--> Android implementation --> Android verify --+
                                                                  |
                                                               release check
```

Independent nodes can become ready together. Dependencies prevent downstream work from starting before exact predecessor evidence exists.

## C. Multi-repository orchestration

A workflow may target several registered repositories.

The orchestration layer validates each node against the registry and then materializes a normal Local Agent task into that repository's existing `agent-control` plane.

No cross-repository shell is invented. Each node is still executed by the normal worker for its own repository.

## D. Durable waiting / planner checkpoints

A workflow can intentionally stop in states such as:

- `waiting_user`
- `waiting_planner`
- `waiting_external`

without losing completed node evidence.

Examples:

```text
Audit complete.
Need decision: preserve API compatibility or permit breaking v2?
```

or:

```text
Backend + Android + firmware implementation complete.
Planner must inspect exact results before generating integration phase.
```

This is the key to long-lived workflows: a workflow may take hours or days without pretending that one immutable shell task should remain alive for that entire time.

---

# 3. Non-goals

Do not turn Local Agent into another OpenWorker/Codex-style model host.

Specifically, v1 must not:

- embed an LLM or API model;
- infer plans from natural language inside Local Agent;
- weaken `agent_binding`;
- let a normal project conversation silently switch repositories;
- resume an interrupted claimed shell task;
- auto-retry failed command payloads under the same task identity;
- introduce generic desktop automation/connectors;
- replace existing repository workers or resource leases;
- require all current single-repository workflows to migrate immediately.

Existing task JSON remains supported throughout rollout.

---

# 4. Architectural rule: keep ordinary chat binding unchanged

Current hard invariant remains for ordinary executable conversations:

```text
one ChatGPT conversation
    == one agent_binding
    == one repository id
    == one GitHub repository
```

Do **not** weaken this to make multi-repo easier.

Instead add a distinct infrastructure orchestration capability.

Conceptually:

```text
project conversation
  binding = repo A
  may queue repo A task only

orchestration conversation
  binding = local-agent infrastructure identity
  execution_enabled = false
  orchestration_enabled = true
  may submit a workflow manifest
  may NOT directly queue a project shell task
```

The workflow coordinator is then the deterministic authority that validates every target node against the current repository registry and publishes the exact immutable child task to the correct repository.

This preserves the existing hard binding instead of replacing it with planner trust.

The remote orchestration transport is a later phase. The first workflow engine can be exercised locally by CLI so the graph semantics are proven before changing Chat Bridge/catalog contracts.

---

# 5. Core data model

## 5.1 Workflow manifest

A workflow manifest is immutable after admission.

Illustrative schema:

```json
{
  "schema_version": 1,
  "id": "protocol-v2-rollout-20260919",
  "method": {
    "name": "cross-repo-api-change",
    "version": 1
  },
  "created_at": "2026-09-19T12:00:00Z",
  "nodes": [
    {
      "id": "backend-implement",
      "kind": "task",
      "repository_id": "backend",
      "agent_binding": "<exact UUID>",
      "depends_on": [],
      "task": {
        "work_branch": "agent/protocol-v2",
        "allow_write": true,
        "resources": [],
        "workflow_policy": "efficient-verification-v1",
        "steps": [],
        "verify_steps": []
      }
    },
    {
      "id": "integration-checkpoint",
      "kind": "planner_checkpoint",
      "depends_on": [
        "backend-implement",
        "android-implement",
        "firmware-implement"
      ]
    }
  ]
}
```

The coordinator assigns/validates deterministic child task ids. The child task written into a project repository includes workflow metadata only as provenance; its execution semantics remain the ordinary task contract.

Suggested child metadata:

```json
{
  "workflow": {
    "id": "protocol-v2-rollout-20260919",
    "node_id": "backend-implement",
    "manifest_digest": "sha256:..."
  }
}
```

This metadata must not be able to loosen task-contract validation.

## 5.2 Node kinds

Initial v1 should keep node kinds deliberately small:

- `task` — materialize one ordinary repository task;
- `user_gate` — durable explicit user decision;
- `planner_checkpoint` — completed evidence must be inspected by ChatGPT before a continuation phase is submitted;
- `barrier` — pure dependency join, no execution.

Do not add arbitrary plugin node types in v1.

## 5.3 Node state

Canonical states:

```text
pending
blocked_dependency
ready
dispatched
running
succeeded
failed
cancelled
waiting_user
waiting_planner
blocked_interrupted
```

Only `task` nodes use `dispatched/running`.

A dependency becomes satisfied only from exact terminal evidence matching the expected child task id **and task digest**.

## 5.4 Workflow state

Canonical workflow states:

```text
pending
running
waiting_user
waiting_planner
failed
cancelled
completed
```

A failed task does not silently become a new task. The workflow either terminates or waits for a planner continuation according to explicit workflow policy.

---

# 6. Methods design

Methods are **declarative planner/workflow recipes**, not Python code execution hooks.

Suggested built-in layout:

```text
local_agent/workflow/methods/
  deep-refactor.json
  security-audit.json
  release-candidate.json
  dependency-upgrade.json
  firmware-validation.json
  cross-repo-api-change.json
```

Example method concept:

```json
{
  "schema_version": 1,
  "name": "deep-refactor",
  "version": 1,
  "description": "Audit, implement incrementally, verify focused/full, then review final diff.",
  "required_phases": [
    "audit",
    "implementation",
    "focused_verification",
    "full_verification",
    "final_review"
  ],
  "requirements": {
    "final_full_verification": true,
    "planner_checkpoint_after_audit": true
  }
}
```

The method does not decide commands. ChatGPT instantiates a workflow that satisfies the method contract.

### Why this split matters

A method can say:

> there must be an audit before implementation and a full verification before completion

but Local Agent should not invent:

> run `pytest tests/foo.py` and edit `src/bar.py`

That remains planner work.

### Method identity

Every workflow references exact:

```text
method name + version + method digest
```

so changing a method later cannot rewrite the meaning of an already-admitted workflow.

### Future repository methods

After built-ins are stable, allow repository-owned method profiles, but pin them to an exact source commit/digest. Do not let mutable project files silently redefine a running method.

---

# 7. Workflow coordinator

Introduce a narrow new package rather than expanding `supervisor/orchestrator.py` into a second monolith.

Proposed structure:

```text
local_agent/workflow/
  __init__.py
  contract.py       # manifest/node validation + canonical digest
  methods.py        # method catalog loading/validation
  state.py          # pure workflow/node state transitions
  store.py          # durable atomic local persistence
  coordinator.py    # side effects: inspect evidence, dispatch ready nodes
  publishing.py     # project task publication + later remote workflow status
```

Potential CLI:

```text
local_agent/cli/workflow.py
```

Tests:

```text
tests/test_workflow_contract.py
tests/test_workflow_state.py
tests/test_workflow_store.py
tests/test_workflow_coordinator.py
tests/test_workflow_multirepo_integration.py
tests/test_workflow_recovery.py
```

## Ownership boundaries

`workflow/contract.py`
- pure schema validation;
- DAG validation;
- canonical digest;
- repository/binding fields syntactically valid;
- bounded node count/dependency fan-out;
- no side effects.

`workflow/methods.py`
- load built-in method specs;
- validate name/version/digest;
- verify workflow satisfies structural method requirements.

`workflow/state.py`
- pure deterministic transition logic;
- dependency readiness;
- terminal workflow classification;
- gate/checkpoint transitions.

`workflow/store.py`
- atomic/fsync-safe workflow manifest/state/events;
- never executes commands;
- restart reconstruction.

`workflow/coordinator.py`
- resolve registry identities;
- inspect exact project status/result evidence;
- choose currently ready dispatches using pure state helpers;
- materialize existing task payloads;
- never plan or rewrite commands.

`supervisor/orchestrator.py`
- only call coordinator tick at bounded points;
- retain process scheduling/global control ownership;
- do not absorb graph logic.

---

# 8. Durable local workflow storage

Use the existing Local Agent application state root, not a second database in v1.

Suggested layout:

```text
~/Library/Application Support/local-agent/workflows/
  <workflow-id>/
    manifest.json
    state.json
    events.ndjson
```

Properties:

- manifest written once and digest-pinned;
- state written atomically;
- event log append-only and bounded/rotatable later;
- restart reconstructs from manifest + state + exact repository evidence;
- state corruption fails closed for that workflow, not for unrelated repositories;
- no command output duplication: task output remains owned by repository run/result evidence.

The workflow state stores references such as task id, expected digest and result location, not copies of every task log.

---

# 9. Dispatch model

## 9.1 Ready node selection

A task node becomes `ready` only when:

1. all dependencies succeeded;
2. target repository exists and binding matches the manifest;
3. no terminal node evidence already exists for this node;
4. no conflicting workflow node is already active/pending in that repository under coordinator ownership;
5. global Local Agent disable is not active.

## 9.2 Materialization

For a ready node:

1. derive a bounded deterministic child task id from workflow + node;
2. construct the full ordinary task JSON;
3. include exact target `agent_binding`;
4. call the existing task validator before publication;
5. compute/store expected `task_digest`;
6. publish it through the repository's normal Git-backed `.agent/tasks/` path;
7. mark node `dispatched` only after the remote publication is confirmed.

After this point the normal repository worker owns execution.

## 9.3 Result reconciliation

Coordinator reads the exact project result.

Accept it only when:

```text
result task id == expected child id
AND result task_digest == expected task digest
AND repository/binding identity still matches
```

Then transition the graph.

A result for a different digest is a workflow integrity failure, never "close enough" evidence.

---

# 10. Parallelism

The workflow engine does **not** create a new worker pool.

Existing production already supports up to four parallel repository workers and resource-aware admission. Reuse it.

Workflow coordinator may publish several independent ready nodes for **different repositories** in one tick. Existing supervisor scheduling then decides actual execution slots/resources.

For v1, publish at most one coordinator-owned pending/active node per repository at once. This avoids ambiguous ordering inside a single repo and preserves current single-repository worker semantics.

Example:

```text
backend node  -----------+
Android node  -----------+--> can run in parallel
firmware node -----------+
```

while:

```text
backend migrate -> backend verify
```

remains ordered by graph dependency.

Named resource and `machine` locks continue to work unchanged across workflow and ordinary tasks.

---

# 11. Coexistence with ordinary tasks

Workflow orchestration must not take over a repository merely because a graph references it.

V1 rule:

> workflow dispatch yields while the target repository has unrelated active/pending project work.

This provides a safe incremental rollout.

Later, if needed, add explicit priorities/queue ownership. Do not invent priority preemption in v1.

A normal single-repository ChatGPT conversation can continue creating existing standalone tasks exactly as today.

---

# 12. Failure semantics

Keep the current Local Agent philosophy: exact evidence, no magical recovery.

## Task failure

When a child task returns terminal failure:

- node becomes `failed`;
- downstream dependent nodes do not dispatch;
- workflow becomes `failed` or `waiting_planner` according to an explicit manifest/method policy;
- Local Agent does not synthesize a repair command.

ChatGPT may create a continuation/revision with a new node/task identity after inspecting evidence.

## Interrupted claimed task

If existing recovery says the task was interrupted and must not replay:

- node becomes `blocked_interrupted`;
- workflow becomes `waiting_planner` or `failed`;
- no automatic requeue of the old child payload.

## Coordinator restart

If coordinator/supervisor restarts while a child worker keeps running:

- repository/task leases continue providing execution ownership;
- workflow state is reconciled from exact task/run/result evidence;
- coordinator must not publish a duplicate child task.

---

# 13. Planner checkpoints and append-only continuation

Static graphs are useful, but serious refactors are adaptive. After an audit, ChatGPT often needs to inspect findings before it can know the correct implementation commands.

Therefore design workflow continuation from the start, but implement it after the static graph MVP.

## V1

A `planner_checkpoint` stops the workflow in `waiting_planner`.

Completed evidence stays durable. ChatGPT creates a **continuation manifest** instead of mutating completed nodes.

## V2 continuation model

Use append-only workflow revisions:

```text
revision 1 digest A
    audit nodes
    planner checkpoint

revision 2 parent_digest=A
    implementation nodes
    verification nodes
```

Rules:

- earlier nodes are immutable;
- a revision may add nodes/edges that originate from existing terminal/checkpoint nodes;
- it may not rewrite task payloads or results of earlier revisions;
- every revision has its own canonical digest;
- workflow status exposes current revision and lineage.

This lets ChatGPT adapt intelligently while Local Agent retains immutable execution history.

---

# 14. Durable user gates

A `user_gate` is a durable workflow node, not a sleeping process.

Illustrative manifest node:

```json
{
  "id": "breaking-api-choice",
  "kind": "user_gate",
  "depends_on": ["audit"],
  "prompt": "Permit breaking API v2?",
  "choices": ["preserve_compat", "allow_breaking"]
}
```

Runtime:

```text
pending -> waiting_user -> resolved
```

Decision record is immutable and bound to:

- workflow id;
- manifest/revision digest;
- node id;
- decision;
- resolver identity when available;
- timestamp.

First resolver wins; repeated resolution is idempotent.

No repository worker remains alive while waiting.

A later Bridge UI/command can expose pending gates, but the initial implementation can resolve them through the local workflow CLI for deterministic testing.

---

# 15. Remote orchestration control plane

Implement only after local workflow semantics are proven.

The preferred model is a dedicated **infrastructure orchestration control identity**, not a project conversation with cross-repo superpowers.

Catalog concept:

```json
{
  "repository_id": "local-agent",
  "repository": "MichalMatu/local-agent",
  "agent_binding": "<infra binding>",
  "execution_enabled": false,
  "orchestration_enabled": true
}
```

An orchestration-bound ChatGPT conversation may:

- inspect global workflow/repository evidence;
- submit an immutable workflow request;
- resolve/continue planner checkpoints through the defined protocol;

but may not directly queue an arbitrary child project task.

The deterministic coordinator performs the fan-out only after validating every target repository/binding.

Suggested remote namespace on the orchestration control branch:

```text
.agent/workflows/requests/<workflow-id>.json
.agent/workflows/status/<workflow-id>.json
.agent/workflows/results/<workflow-id>.json
.agent/workflows/decisions/<workflow-id>/<gate-id>.json
```

Do not add this namespace to each project repository.

A dedicated orchestration control repository/id may be introduced if using the `local-agent` infrastructure checkout creates lifecycle coupling. Make this an implementation-time decision after inspecting deployment constraints; the workflow contract should not depend on the Git transport choice.

---

# 16. Chat Bridge integration

Do not begin here. Bridge is Phase 5, after coordinator semantics are stable.

Potential additions for an orchestration-enabled conversation:

```text
[LAB:WORKFLOWS]
[LAB:WORKFLOW=<id>]
[LAB:NEXT=...]
```

The Bridge should wake the same infrastructure orchestration conversation when:

- a workflow reaches `waiting_planner`;
- a `user_gate` is resolved;
- the workflow fails;
- the workflow completes.

It should not wake on every low-level node heartbeat.

Ordinary project chats retain their current repository-bound behavior.

---

# 17. Structured outputs between nodes

Do not block MVP on a general artifact bus.

V1 dependencies mean:

> predecessor terminal success is required.

Cross-repo data exchange should initially use explicit durable mechanisms already natural to the project: Git commits/branches, generated files committed by the task, known artifact locations, or planner checkpoints.

After real use identifies needs, add small structured node exports.

Potential future shape:

```json
{
  "exports": {
    "commit_sha": "...",
    "schema_version": "2"
  }
}
```

A successor may reference only declared exports, not scrape arbitrary predecessor stdout.

Do not build an artifact DSL before there is a concrete use case.

---

# 18. Cancellation

Two levels are required.

## Cancel workflow

Stops dispatch of new nodes and marks remaining non-running nodes cancelled.

## Cancel active child

For any currently running child, use the existing repository-scoped exact `cancel_task` mechanism.

Workflow cancellation waits for terminal evidence from active children before declaring itself fully cancelled.

It never kills unrelated standalone tasks in the same repository.

---

# 19. Method examples and value

## `deep-refactor`

```text
audit
  |
planner checkpoint
  |
implementation slice(s)
  |
focused verify
  |
full verify
  |
final diff review
```

Benefit: repeatable large-refactor discipline without restating the process in every chat.

## `cross-repo-api-change`

```text
contract definition
  +--> backend
  +--> firmware
  +--> Android
       |
       +--> barrier
              |
          integration
              |
          planner checkpoint
```

Benefit: one durable goal/evidence chain across repos.

## `release-candidate`

```text
source freeze -> full tests -> build/package -> smoke -> release evidence -> user gate -> release action
```

Benefit: release workflow can stop before consequential publication without losing completed verification.

## `firmware-validation`

```text
host tests -> build -> device availability gate -> flash -> hardware smoke -> evidence
```

Benefit: hardware availability becomes a durable wait instead of a failed long-running task.

---

# 20. Implementation phases

## Phase 0 — contract audit and fixtures

No runtime behavior.

Deliver:

- final workflow schema v1;
- node state table;
- method schema v1;
- fixtures for single-repo, parallel multi-repo, failed dependency, user gate, planner checkpoint;
- exact ownership map.

Files:

```text
local_agent/workflow/contract.py
local_agent/workflow/methods.py
local_agent/workflow/state.py
tests/fixtures/workflows/
tests/test_workflow_contract.py
tests/test_workflow_state.py
```

Exit gate: pure tests only, no supervisor integration.

## Phase 1 — methods catalog

Deliver:

- built-in method schema/loader;
- exact name/version/digest identity;
- initial methods: `deep-refactor`, `cross-repo-api-change`, `release-candidate`;
- CLI/diagnostic method listing;
- validation that an instantiated workflow satisfies required method structure.

No automatic execution yet.

Exit gate: method changes cannot alter admitted workflow meaning because digest/version are pinned.

## Phase 2 — local static graph coordinator MVP

Deliver:

- durable workflow store;
- local submit/list/show/cancel CLI;
- DAG readiness;
- child task materialization;
- exact task digest reconciliation;
- cross-repository dispatch to existing task control planes;
- reuse existing workers/resources;
- at most one coordinator-owned pending/active child per repo.

Supported node kinds initially:

```text
task
barrier
```

Exit demo:

```text
workflow with 3 independent repositories
-> dispatch 3 ready nodes
-> at least 2 overlap when scheduler capacity/resources permit
-> exact results reconcile
-> barrier becomes ready
-> final node runs
-> workflow completes
```

## Phase 3 — recovery and planner checkpoints

Deliver:

- restart-safe reconciliation;
- `planner_checkpoint` node;
- `waiting_planner` state;
- explicit continuation submission;
- no duplicate task publication after restart;
- interrupted child -> `blocked_interrupted`, never replay.

Exit demo:

```text
audit node succeeds
-> planner checkpoint
-> restart supervisor
-> checkpoint still waiting with exact audit evidence
-> submit continuation
-> implementation proceeds
```

## Phase 4 — durable user gates

Deliver:

- `user_gate` nodes;
- exactly-once resolution;
- local CLI resolve path;
- workflow cancellation semantics;
- durable decision provenance.

Exit demo:

```text
release verification succeeds
-> waiting_user
-> service restarts
-> decision remains pending
-> approve
-> exact downstream node becomes ready
```

## Phase 5 — remote orchestration transport + Chat Bridge

Deliver:

- `orchestration_enabled` catalog capability or equivalent dedicated identity;
- Git-backed workflow request/status/result transport;
- infrastructure conversation can submit/inspect workflows;
- ordinary repository chats cannot submit cross-repo workflows;
- bridge wakes orchestration chat on checkpoint/failure/completion;
- compact workflow status commands.

Exit demo:

User gives one cross-repo goal in orchestration chat; ChatGPT submits one workflow; Local Agent fans out nodes to several project repos; ChatGPT is woken only when planning/decision evidence is needed.

## Phase 6 — append-only workflow revisions

Deliver:

- revision lineage/digests;
- planner can add next phase after checkpoint;
- no rewriting completed nodes;
- method contract can span revisions;
- clear final evidence chain across adaptive work.

This phase turns the static graph engine into a genuinely useful long-running AI workflow substrate.

## Phase 7 — structured exports / remote runners only if demanded

Possible later work:

- declared node exports;
- artifact references;
- multiple Local Agent machines/runners (`runner_id`);
- capability/resource-based placement;
- RPi/Android/remote Mac execution.

Do not mix this into the first workflow release.

---

# 21. Tests

## Pure contract tests

Must cover:

- duplicate node ids;
- cycles;
- unknown dependencies;
- invalid repository/binding;
- excessive node/dependency counts;
- invalid node kind/state;
- method name/version/digest mismatch;
- deterministic manifest digest independent of JSON formatting.

## State-machine tests

Must cover:

- dependency transitions;
- barrier join;
- failure propagation;
- cancellation;
- waiting planner/user transitions;
- idempotent repeated reconciliation;
- terminal states cannot regress to running.

## Real temporary-Git integration

At least:

- two/three repositories with real `agent-control` branches;
- child task publication to correct repo only;
- wrong binding is rejected before publication/execution;
- parallel independent nodes overlap;
- same-repository nodes do not overlap;
- named resources still serialize as today;
- unrelated standalone task causes workflow dispatch to yield;
- exact task digest mismatch does not satisfy a node;
- coordinator restart produces no duplicate child.

## Recovery

- coordinator dies after publication but before local state update;
- coordinator dies after local state update but before next tick;
- worker dies while child command survives;
- child interrupted under existing no-replay semantics;
- state file corruption isolates only affected workflow;
- workflow cancel during active child execution.

## Bridge/remote transport

Only Phase 5:

- ordinary project chat cannot cross repo;
- orchestration identity cannot directly queue project task;
- workflow manifest target binding mismatch fails closed;
- checkpoint wake is deduplicated;
- old workflow/revision controls cannot mutate a newer revision.

---

# 22. Boundedness

Suggested initial limits:

```text
max workflow nodes: 64
max dependencies per node: 16
max active workflows: 16
max workflow manifest size: 2 MiB
max method spec size: 256 KiB
```

Actual values should be aligned with existing task limits during implementation.

Do not allow graph size or event history to become an unbounded new memory/disk surface.

---

# 23. Observability

Add workflow-level status without replacing repository status.

Example:

```json
{
  "workflow_id": "protocol-v2-rollout-20260919",
  "state": "running",
  "revision": 1,
  "nodes": {
    "succeeded": 2,
    "running": 2,
    "ready": 0,
    "blocked": 3,
    "failed": 0
  },
  "active": [
    {"node_id": "android-implement", "repository_id": "android"},
    {"node_id": "firmware-implement", "repository_id": "firmware"}
  ],
  "updated_at": "..."
}
```

Keep node output in existing repository results; workflow status should remain compact.

CLI goals:

```text
local-agent workflow list
local-agent workflow show <id>
local-agent workflow graph <id>
local-agent workflow cancel <id>
local-agent workflow resolve <id> <gate> <decision>
local-agent method list
local-agent method show <name>
```

Exact CLI integration should follow the repository's existing command layout rather than creating a second top-level executable unnecessarily.

---

# 24. What not to change in the first release

Do not modify:

- command execution semantics;
- normal task schema fields except optional workflow provenance;
- repository worker claim/result semantics;
- task watchdogs;
- resource lease implementation;
- self-update/restart path;
- ordinary Chat Bridge binding rules;
- serial fallback behavior beyond recognizing workflow-generated ordinary tasks identically to manual tasks.

The first release should be easy to roll back because workflow orchestration is additive.

---

# 25. Suggested first implementation slice

The first coding branch after this design should be deliberately boring internally but visibly useful externally.

Implement only:

1. `workflow/contract.py`;
2. `workflow/state.py`;
3. `workflow/methods.py`;
4. three built-in methods;
5. fixtures/tests;
6. local CLI that validates and prints the ready-node plan — **no task publication yet**.

Then a second commit/phase adds durable store + publication.

Why split here:

- schema mistakes are cheapest to fix before they become persistent state;
- method semantics can be exercised immediately;
- DAG/state logic becomes stable before Git/process side effects;
- existing production Local Agent remains untouched until the contract is proven.

---

# 26. Concrete acceptance target

The feature is successful when this scenario works from one orchestration conversation:

```text
Goal:
"Change API protocol in backend, Android and ESP32 firmware and verify compatibility."

1. ChatGPT chooses `cross-repo-api-change`.
2. It submits one workflow manifest.
3. Local Agent validates all target repo bindings.
4. Backend, Android and firmware implementation/verification nodes run concurrently where independent.
5. Each uses the current repository worker, branch policy, watchdogs and resource locks.
6. Integration waits for all required exact terminal task digests.
7. Workflow reaches `waiting_planner` with compact evidence references.
8. ChatGPT inspects the three exact results and appends the integration/release continuation.
9. Local Agent runs the continuation.
10. Workflow finishes with one global result linking all child task/result evidence.
```

That is the intended **execution fabric**: ChatGPT remains the intelligence, while Local Agent becomes the durable, multi-repository workflow substrate underneath it.

---

# 27. Priority relative to OpenWorker hardening

Capability work should now be the main development track on this candidate branch.

Recommended order:

```text
P0  workflow contract + methods
P1  static task graph + multi-repo coordinator
P2  restart-safe planner checkpoints
P3  durable user gates
P4  remote orchestration / Bridge integration
P5  append-only adaptive revisions

secondary:
     narrow command self-protection hardening from OPENWORKER_CODE_AUDIT.md
```

The OpenWorker audit remains valuable, especially for durable gates and provenance, but it should support this execution-fabric direction rather than become the main product goal.