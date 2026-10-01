# Consolidated Local Agent development roadmap

Status: planning branch only. No production runtime behavior is changed by this document.

Production baseline: `main@474000b5d4b015958fe92be491968dc4625b4a84` (`v4.18.24`).
Planning branch: `plan/consolidated-development-roadmap`.

This document consolidates the currently active development directions without treating the old feature branches as merge-ready release branches.

## 1. Current branch inventory

### Production / operational branches

- `main` — production source of truth, currently v4.18.24.
- `chat-bridge-state` — live Bridge runtime/configuration state; not a source-development branch.
- `operator-control` — operator control plane; not a source-development branch.

### Active development candidates

#### `feature/chat-bridge-event-wake`

Purpose: replace most healthy-task polling with exact event-driven continuation.

Important assets to preserve:

- durable `task_result_ready` outbox after authoritative result publication;
- notification-only Chrome Native Messaging host;
- exact task watch routing with `[LAB:WAIT_TASK=<task-id>]`;
- persisted recent-event/pending-wake state;
- hard-binding-preserving event routing;
- scheduled reconciliation fallback;
- planner prompt compaction and event-driven pacing;
- real Mac / real Chrome evidence.

Do not merge this branch wholesale. It is substantially behind current `main` and overlaps the central Chat Bridge files changed by v4.18.21-v4.18.24.

#### `feature/openworker-governance`

This branch contains two logically separate bodies of work.

1. OpenWorker-inspired governance research:
   - deterministic Local Agent self-protection floors;
   - command/admission security corpus;
   - compact policy provenance;
   - possible future digest-bound operator approval.

2. Execution Fabric implementation:
   - durable workflow DAGs;
   - versioned methods;
   - planner checkpoints and user gates;
   - append-only workflow revisions;
   - exact multi-repository child-task publication;
   - Git-backed cancellation;
   - shared control-Git locking;
   - explicit manual `run-cycle` and lineage controls.

The workflow engine is intentionally not wired into the production supervisor, daemon, launchd or Chat Bridge.

Do not merge this branch wholesale. Reuse the isolated workflow package and tests selectively on top of current `main`.

### Already-consumed / stale work branches

- `work/chat-delivery-timeout-detection` — implementation is already in production v4.18.24; only a post-merge documentation delta remains.
- `audit/pre-restart-contract-hardening` — no unique commits over its old production base.
- `docs/pre-restart-drift-cleanup` — no unique commits over its old production base.
- `release/4.18.23-host-ops-onboarding` — old release bookmark, no unique development delta.

These branches are not separate future product directions.

## 2. One target architecture

The two major feature branches are complementary, not competing.

The event-wake branch solves **when ChatGPT should be woken**.

The Execution Fabric solves **what durable multi-step work Local Agent should coordinate between planner turns**.

They should meet through one small common concept: a durable, non-authoritative **attention event**.

```text
ChatGPT planner
    |
    | immutable task / workflow intent
    v
Chat Bridge
    |
    +---------------- project conversation ----------------+
    |                                                       |
    | exact repository binding                              |
    | WAIT_TASK(task-id)                                    |
    |                                                       v
    |                                              normal repository task
    |                                                       |
    |                                                       v
    |                                              Local Agent worker
    |                                                       |
    |                                  authoritative terminal result
    |                                                       |
    |                                                       v
    |                                          durable attention event
    |                                                       |
    +---------------------- Native Messaging <--------------+
    |
    v
exact project conversation wake


Infrastructure orchestration conversation
    |
    | immutable workflow manifest / continuation
    v
Execution Fabric
    |
    +--> repo A child task
    +--> repo B child task
    +--> repo C child task
    |
    v
waiting_planner / waiting_user / failed / completed
    |
    v
durable attention event
    |
    v
same notification transport
    |
    v
infrastructure orchestration conversation wake
```

The event is never success evidence. The planner must still read exact task/workflow evidence before acting.

## 3. Non-negotiable architecture rules

1. ChatGPT remains the planner. Local Agent stays model-free.
2. Ordinary project conversations remain exactly hard-bound to one repository and one immutable `agent_binding`.
3. Multi-repository orchestration uses a distinct infrastructure orchestration identity; it does not give ordinary project chats cross-repository shell authority.
4. Existing repository tasks remain the only execution primitive. Execution Fabric coordinates them; it does not replace task digest, claims, watchdogs, resources, cancellation or terminal results.
5. No automatic replay of interrupted claimed work.
6. Native Messaging remains notification-only. No shell, task creation, cancellation, rebind or arbitrary filesystem/log API is added to the native host.
7. Event delivery is an optimization. Durable evidence + bounded reconciliation remain the correctness path.
8. Workflow graph logic does not move into `supervisor/orchestrator.py`; the supervisor may only invoke a narrowly-owned workflow scheduler/coordinator boundary.
9. Project command authority must not be allowed to rewrite Local Agent's own authority/control state. OpenWorker-inspired self-protection should be implemented before broad automatic orchestration is enabled.
10. Old feature branch version numbers are candidate history, not release numbering requirements. New integrated releases are versioned from the current production baseline.

## 4. Consolidated development phases

### Phase A — production reliability cleanup

Goal: remove known current-runtime defects before importing larger subsystems.

First actions:

- port the stale-conversation-exhaustion fix from the event-wake branch so only the current/latest assistant turn can disable a chat;
- reproduce/fix the ordinary interval wake failure in an inactive ChatGPT tab because scheduled reconciliation remains the safety net even after event wake ships;
- isolate the remaining cases that still require manual `Ctrl+R` after Bridge/content transitions;
- keep timeout-recovery v4.18.24 behavior and its race coverage intact;
- separately address the confirmed orphan-descendant/resource-lease recovery defect before more automatic workflow concurrency depends on long-lived resources.

Exit gate: current single-task Chat Bridge + Local Agent path is boring and reliable before new orchestration is layered on top.

### Phase B — land the event/notification substrate on current `main`

Do not rebase/merge the entire old branch mechanically.

Port the feature in slices:

1. `result_events` durable bounded outbox;
2. notification-only Native Messaging host + installer/health checks;
3. Bridge native connection lifecycle and durable ingestion;
4. exact `WAIT_TASK` ownership/routing;
5. pending event delivery using the existing current-main delivery path;
6. planner pacing changes only after transport/recovery is proven.

While porting, current-main assistant-timeout recovery and the latest exhaustion fix remain authoritative and must be retained.

Initial event schema can remain task-specific (`task_result_ready`) even though the transport should be designed so a later workflow attention event can reuse it without introducing a second Native Messaging stack.

Exit gate:

- real short task -> authoritative result -> exact conversation wake;
- failed/rejected/cancelled terminal results also wake correctly;
- deferred result publication emits only after successful authoritative publication;
- Local Agent restart, Chrome restart and Native Messaging absence all preserve correctness;
- inactive-tab scheduled fallback works;
- no duplicate user prompt or duplicate logical wake.

### Phase C — governance P0 before automatic orchestration

Implement only the narrow high-value OpenWorker adaptations:

- deterministic project-command self-protection floors in the existing task-contract boundary;
- table-driven security/admission corpus with benign controls;
- protect Local Agent state/runtime/control surfaces and other repositories' control/checkpoint infrastructure from obvious direct project-task mutation;
- record compact admission-policy provenance in existing evidence if useful.

Do not add a generic permission engine, embedded reviewer model, standing shell grants or desktop-agent framework.

Treat command text protection honestly as defense in depth, not as an OS sandbox.

Exit gate: an ordinary project task cannot directly use obvious command paths to mutate Local Agent authority or another repository's Local Agent control plane.

### Phase D — transplant Execution Fabric core as an inert subsystem

Port from the verified workflow code baseline rather than merging the whole old branch.

Bring over:

- workflow contract/state/store;
- methods and method identity;
- evidence reconciliation;
- append-only revisions/activation/effective state;
- Git child publication and exact cancellation;
- shared control-Git lock;
- manual CLI, including `run-cycle` and explicit effective-state controls;
- the existing workflow tests and disposable-Git integrations.

Keep the production runtime import boundary inert during this phase.

Before wiring anything automatically, rerun the public-CLI disposable multi-repository scenario described in the old handoff against current `main`.

Exit gate: the same manual workflow semantics are green on the current production architecture and coexist with v4.18.24+ Local Agent behavior.

### Phase E — bounded production workflow scheduler

Preferred first ownership: supervisor-owned scheduling trigger with workflow logic remaining in dedicated `local_agent/workflow/` owners.

Do not create a second executor pool or a second daemon.

The supervisor integration should do only this:

```text
bounded workflow discovery
-> choose due/runnable workflow(s)
-> invoke one exact lineage cycle
-> return to normal supervisor scheduling
```

Requirements:

- adaptive/bounded cadence;
- zero busy polling for `waiting_user`/`waiting_planner` states;
- global disable is authoritative;
- exact repository binding revalidated at dispatch;
- ordinary standalone repository tasks coexist and retain priority/ownership semantics;
- workflow Git transport uses the same control-Git lock as normal runtime;
- no automatic replay after ambiguous/interrupted child execution;
- self-update/restart can reconstruct workflow state from durable state + exact child evidence.

Event-triggered local scheduler nudges may be added later for latency, but bounded reconciliation remains the correctness fallback.

### Phase F — orchestration conversation + unified attention events

Only after the local automatic workflow scheduler is stable.

Add a distinct infrastructure orchestration capability, for example:

```text
repository_id = local-agent
execution_enabled = false
orchestration_enabled = true
```

The orchestration conversation may submit/inspect workflow manifests and planner continuations, but it may not directly publish arbitrary project shell tasks.

Extend the notification substrate with workflow attention events for meaningful durable transitions only:

- `waiting_planner`;
- user decision/gate resolved when planner action is needed;
- `failed`;
- `completed`.

Do not wake on every node heartbeat.

Task events and workflow events use the same transport but different routing ownership:

- task event -> exact project conversation watch;
- workflow event -> exact infrastructure orchestration conversation/workflow ownership.

This is where the two old development approaches become one product.

### Phase G — approval/gates and higher-level methods

Reuse Execution Fabric `user_gate` for exact consequential workflow decisions.

If stronger approval provenance is needed, adapt the OpenWorker idea as digest-bound workflow/action approval rather than creating a parallel generic permission framework.

Good candidates:

- release publication;
- destructive migration;
- hardware flash/deployment when policy requires explicit operator confirmation;
- other narrowly-defined irreversible actions.

Methods such as `deep-refactor`, `cross-repo-api-change` and `release-candidate` then become the reusable high-level development model.

### Phase H — later only when demanded

Keep out of the first consolidated release path:

- remote/multi-machine runner placement;
- Android/RPi worker federation;
- generic artifact bus/DSL;
- generic connector/provider framework;
- embedded LLM/reviewer;
- priority preemption;
- arbitrary Native Messaging command APIs;
- continuous stdout/log streaming to ChatGPT;
- automatic ChatGPT tab creation.

## 5. What to salvage from each branch

### From `feature/chat-bridge-event-wake`

Salvage the architectural concepts, tests and isolated modules for:

- result event outbox;
- Native Messaging transport;
- exact task watch state;
- event wake state;
- prompt pacing contract;
- installer/health checks;
- live-evidence scenarios;
- BUG-003 stale exhaustion fix and BUG-004/BUG-005 reproductions.

Do not take its central Chat Bridge files as authoritative over current `main`; port behavior into current-main owners and keep v4.18.24 timeout recovery.

### From `feature/openworker-governance`

Salvage two separate tracks:

Governance:

- P0 self-protection floor design;
- security corpus methodology;
- exact-action approval ideas only when a concrete workflow gate needs them.

Execution Fabric:

- nearly all isolated `local_agent/workflow/` implementation and tests;
- workflow CLI;
- shared control-Git lock;
- disposable-Git integration/recovery tests.

Do not copy an OpenWorker permission/reviewer architecture and do not wire the workflow engine directly into production until the pre-integration audit is repeated on current `main`.

## 6. Branch/PR strategy

Do not try to resolve this by making PR #77 or PR #81 mergeable and merging them sequentially.

Both were validation branches built from older production states. The integrated product should be constructed from current `main` through fresh, narrow branches with explicit release boundaries.

Recommended branch sequence:

```text
fix/chat-bridge-current-turn-exhaustion
feature/attention-event-substrate
hardening/project-command-self-protection
feature/execution-fabric-core-port
feature/execution-fabric-scheduler
feature/orchestration-bridge-events
```

Each branch should start from the then-current `main`, carry one coherent ownership change, pass exact-head CI, and be released/merged independently when practical.

PR #77 and PR #81 remain source/reference PRs until their useful pieces have been transplanted and verified. After that they can be closed as superseded rather than merged.

## 7. Definition of the final product direction

The end state is not "Local Agent becomes an autonomous AI agent".

The end state is:

> ChatGPT remains the reasoning/planning layer. Local Agent becomes a durable, safe execution fabric that can coordinate exact repository-bound work over long periods and wake the correct ChatGPT planner only when new authoritative evidence or an explicit decision actually requires attention.

That combines the strongest idea from both development branches:

- event-driven continuation removes wasteful planner polling;
- Execution Fabric makes multi-step and multi-repository work durable;
- exact hard binding and existing task workers preserve execution safety;
- governance hardening protects Local Agent's own authority before orchestration becomes more automatic;
- bounded reconciliation keeps event delivery an optimization rather than a correctness dependency.

## 8. Immediate next move

Do not write more code on either old feature branch.

Start from current production `main` and execute Phase A first. In parallel, keep the two old draft PRs as read-only implementation/reference sources.

After Phase A, port the event substrate before connecting automatic workflow orchestration. The workflow core can be transplanted as an inert subsystem while event-wake is being stabilized, but the production scheduler and orchestration Chat Bridge integration should wait until both foundations are current-main clean.