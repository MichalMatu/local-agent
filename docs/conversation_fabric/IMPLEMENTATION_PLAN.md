# Superchat / Conversation Fabric implementation plan

Status: implementation planning only. No production behavior change is authorized by this document.

Branch: `feature/conversation-fabric-superchat`
Base: `main@474000b5d4b015958fe92be491968dc4625b4a84` (`v4.18.24`).

## 1. Strategy

Build Superchat as a sequence of narrow, independently verifiable capabilities on top of current `main`.

Do not merge the historical `feature/chat-bridge-event-wake` or `feature/openworker-governance` branches wholesale. Treat them as donor implementations and test libraries.

The implementation order is chosen to avoid making browser automation or automatic workflow scheduling authoritative before the durable contracts exist.

## 2. Phase 0 — freeze contracts before behavior

Deliver docs + pure schemas/state only.

Define:

- workflow/superchat identity;
- child request identity/digest;
- child roles;
- child lifecycle state table;
- child registration record;
- progress checkpoint schema;
- terminal child record;
- browser mapping schema;
- parent/child generation semantics;
- same-repository branch/worktree rules;
- logical retirement semantics;
- one-level delegation limit;
- event types needed by parent and child.

Required pure negative tests later must cover malformed ids, oversized payloads, invalid transitions, stale generation, duplicate registration and cross-binding mismatch.

Exit gate: two independent implementations could read the docs and produce the same state transitions.

## 3. Phase 1 — current-main reliability prerequisites

Before adding child creation, close current Bridge problems that would make orchestration unreliable.

Priority:

1. latest/current-turn-only conversation exhaustion detection;
2. deterministic reproduction and repair of inactive-tab ordinary interval wake;
3. deterministic reproduction and repair of remaining manual-`Ctrl+R` content/worker refresh dependency;
4. retain all v4.18.24 assistant-timeout recovery tests;
5. address Local Agent orphan-descendant/resource-lease recovery before workflow concurrency relies heavily on long-running resource leases.

Exit gate: one existing project chat survives background-tab, reload and assistant-error scenarios without manual intervention.

## 4. Phase 2 — Attention Fabric task events on current main

Port the proven event-wake donor in isolated slices.

### 2.1 Durable result event outbox

Port/adapt `result_events` after current authoritative result publication.

Properties:

- event only after successful remote result publication;
- deterministic bounded identity;
- atomic persistence;
- replay/ACK;
- bounded count/age/size;
- event write failure never rewrites task outcome.

### 2.2 Native Messaging transport

Port/adapt:

- minimal host;
- handshake/protocol version;
- exact extension origin;
- bounded frame size;
- replay + ACK;
- installer/health diagnostics.

Keep it notification-only in this phase.

### 2.3 Exact `WAIT_TASK`

Port/adapt task-watch ownership and pending event wake into current-main Bridge owners.

Retain scheduled reconciliation as fallback.

Exit gate: real Local Agent task publishes exact result and wakes exact bound chat; native transport loss cannot stall correctness.

## 5. Phase 3 — Conversation Fabric pure core

Add an inert local package/state model with no browser creation yet.

Provisional responsibilities:

```text
conversation/contract   bounded child request + progress/terminal schemas
conversation/state      pure lifecycle transitions
conversation/store      durable local/orchestration references
conversation/identity   deterministic digest/id helpers
```

Support:

- create child request from exact workflow/node;
- exactly-once registration against request digest;
- terminal retirement;
- stale-generation rejection;
- no duplicate active child for one exact request;
- one-level parent rule;
- exact repository/binding ownership.

Exit gate: complete lifecycle can be exercised in memory/files without Chrome.

## 6. Phase 4 — browser child creation in explicit LAB mode

Add Chat Bridge browser actuation behind an explicit disabled-by-default lab capability.

First browser flow:

```text
durable child request exists
-> explicit SPAWN_CHILD command
-> open new ChatGPT tab
-> wait for composer readiness
-> inject deterministic bootstrap
-> confirm accepted message
-> discover exact child conversation URL/id
-> persist browser mapping
```

Hard rules:

- no request -> no child creation;
- request id + digest required;
- exact parent chat must match;
- duplicate command reuses/reports registered child, never creates a second active child;
- failure before identity is retryable and recorded;
- uncertain bootstrap delivery fails closed;
- Bridge never invents repository/binding/branch values.

Browser smoke must use disposable Chrome profiles and synthetic ChatGPT pages before any live test.

Exit gate: parent can intentionally create one exact child and reload/restart Chrome without creating a duplicate.

## 7. Phase 5 — durable child registration through bounded local protocol

Chrome storage alone is not enough for workflow truth.

Extend the local bridge/native boundary only as narrowly as required to durably register browser identity.

A proposed registration message contains only:

```text
pre-existing child request id/digest
workflow/revision/node
parent conversation id
child conversation id/url
repository/binding
lifecycle generation
```

Local side validates that the exact request already exists. The browser cannot use this path to create workflow nodes, tasks, branches, shell commands or repository bindings.

The local coordinator then records/publishes the registration into the orchestration evidence plane.

Exit gate: browser restart and Local Agent restart can reconcile one child request to one exact child conversation without trusting only extension memory.

## 8. Phase 6 — structured child progress/checkpoints

Define and prove the child-to-parent evidence loop without transcript forwarding.

A project child publishes progress only inside its permitted repository/control plane.

Progress stages initially:

```text
analysis_complete
implementation_started
implementation_complete
verification_complete
blocked
terminal
```

The exact stage set may be refined by role.

Execution Fabric/local orchestration reconciles the latest valid project checkpoint and exposes bounded central workflow references to Superchat.

Rules:

- append-only sequence;
- bounded summary/findings;
- exact commit/result references;
- no whole transcript;
- no secrets/raw logs;
- parent acts only after reading referenced authoritative evidence when consequential.

Exit gate: parent can understand child state after losing the original child tab transcript context.

## 9. Phase 7 — branch/worktree isolation for modular parallel implementation

Add workflow ownership rules for same-repository parallel children.

Every implementation node receives:

- deterministic work branch;
- isolated worktree/checkout ownership;
- exact node id in branch metadata/provenance;
- no direct merge to integration/main.

Use existing Local Agent task/workspace machinery where possible; do not invent a second process executor.

Required tests:

- two nodes same repo, different branches/worktrees run independently;
- overlapping resource needs still obey existing resource locks;
- one child cannot claim another child's worktree;
- cancellation cleans only exact node-owned execution;
- integration reads exact commits rather than working-tree assumptions.

Exit gate: two parallel implementation children can safely modify different modules of one repository.

## 10. Phase 8 — transplant Execution Fabric core

Port the verified isolated workflow subsystem from the donor branch onto current main.

Bring over only after revalidation:

- contract/state/store;
- methods;
- evidence;
- revisions/activation/effective state;
- Git publication/cancellation;
- shared control-Git lock;
- lineage cycle;
- workflow CLI;
- tests/disposable-Git scenarios.

Keep it inert: no automatic supervisor tick and no Chat Bridge orchestration yet.

Then extend its node metadata so a planner checkpoint may own/require a Conversation Fabric child where appropriate.

Exit gate: manual CLI can execute a multi-node workflow whose child conversation records are durable metadata but do not yet drive production scheduling automatically.

## 11. Phase 9 — Superchat orchestration semantics

Introduce a dedicated infrastructure conversation capability.

Properties:

```text
execution_enabled = false
orchestration_enabled = true
```

Superchat may:

- submit/append workflow revisions;
- create child requests;
- inspect workflow state/evidence;
- resolve planner checkpoints;
- create integration/verification nodes;
- resolve user-gate continuation after explicit user decision.

It may not directly submit arbitrary shell tasks to project repositories.

Execution Fabric remains the deterministic fan-out authority for exact child project tasks.

Exit gate: one Superchat can create two independent child chats and one integration child from a durable workflow graph.

## 12. Phase 10 — unified workflow attention events

Extend the proven task event transport instead of adding a second wake stack.

New bounded attention event types may include:

```text
child_terminal_recorded
workflow_waiting_planner
workflow_waiting_user
workflow_failed
workflow_completed
```

Routing:

- project task event -> exact project child/watch;
- workflow event -> exact Superchat/workflow owner.

Do not emit parent wakes for every progress line or node heartbeat.

Exit gate: Superchat remains quiet during healthy parallel child work and wakes when a decision/integration transition actually requires it.

## 13. Phase 11 — integration and independent verification nodes

Make integration first-class rather than implicit merge behavior.

Integration node inputs are exact predecessor outputs/commits.

It must:

- combine branches deliberately;
- resolve shared interface changes;
- detect contradictory implementations;
- run integration/full tests;
- produce one exact integrated commit/result.

An optional independent verification child then audits the integrated candidate without sharing the implementation chat's reasoning history.

Exit gate: parallel work demonstrably improves modular depth without reducing whole-system consistency.

## 14. Phase 12 — bounded automatic workflow scheduler

Only after manual Superchat + child lifecycle works end-to-end.

Preferred first integration:

```text
supervisor bounded discovery
-> select due workflow
-> invoke one lineage cycle
-> return to ordinary scheduling
```

No second worker pool and no second always-on model loop.

Waiting planner/user workflows should generate near-zero periodic work except bounded reconciliation.

Exit gate: workflow survives supervisor/Local Agent restart and continues from exact durable evidence without replaying ambiguous project work.

## 15. Phase 13 — governance hardening before wider unattended use

Port the narrow OpenWorker-derived protections:

- project-command self-protection floors;
- security corpus;
- compact policy provenance;
- exact digest-bound approvals only where a concrete workflow user gate requires them.

Do not import a generic reviewer/permission system.

This phase may move earlier for individual risks discovered during Phase 7-12; the principle is that more automation must not expand project-task authority over Local Agent itself.

## 16. First vertical-slice prototype

Before building the whole system, prove one deliberately small vertical slice:

```text
Superchat
  |
  +-- implementation child A
  +-- implementation child B
  |
  +-- integration child
```

Constraints:

- one repository;
- two non-overlapping modules;
- two isolated branches/worktrees;
- no recursive delegation;
- no automatic merge to main;
- no user gate;
- one parent workflow revision;
- explicit/manual spawn command allowed;
- task/event substrate active;
- progress checkpoint + terminal record required from each child.

This prototype should answer the central product question before broader automation:

> Do separate, bounded ChatGPT contexts produce better modular analysis/implementation and can the system integrate them deterministically without losing state?

## 17. Test pyramid

### Pure tests

- schemas/bounds;
- lifecycle transitions;
- digest/idempotency;
- parent/child ownership;
- stale generation;
- progress sequencing;
- integration readiness.

### Git integration

- project progress publication;
- central orchestration reconciliation;
- exact branch/worktree ownership;
- restart/recovery;
- conflicting registration/progress.

### Browser smoke

- create new chat;
- bootstrap acceptance;
- exact conversation identity discovery;
- duplicate spawn command;
- service-worker restart mid-creation;
- child tab manually closed;
- parent/child both open;
- concurrent two-child creation;
- assistant timeout during bootstrap/delivery.

### Real Mac / live ChatGPT

Only after synthetic browser tests are strong:

- one child creation;
- Chrome restart/reconciliation;
- two parallel children;
- child terminal wake to parent;
- integration child;
- logical retirement + optional tab close.

## 18. Release discipline

No phase should be treated as production-ready merely because an old donor branch previously passed CI.

Every transplanted slice must be validated on the exact current-main-derived candidate.

Large historical PRs remain reference/evidence only.

Production merges should remain small enough that one failed capability can be rolled back without removing unrelated Conversation Fabric progress.