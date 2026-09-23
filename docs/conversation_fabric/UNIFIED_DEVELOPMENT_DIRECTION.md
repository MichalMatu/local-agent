# Unified development direction — Conversation Fabric

Status: canonical development direction for `develop/conversation-fabric`.

Production remains `main`. Operational branches `chat-bridge-state` and `operator-control` remain separate because they are runtime/control state, not source-development lines.

The seven former development branches are now donors only. No new product work should start on them. They must not be deleted until the assets listed below are transplanted and verified on this branch.

## 1. Product problem

The concrete motivating workload is a long campaign such as a **44-node code audit**.

Today one ChatGPT conversation performs node #1, appends a long report, then #2, #3, ... #44. The parent conversation accumulates every prior detailed result, tool trace and discussion even though node #27 normally needs only:

- the campaign contract/rubric;
- exact repository/ref;
- the one node/module being audited;
- a small set of cross-cutting findings relevant to that node;
- the durable ledger state needed to allocate finding IDs;
- required output/evidence format.

The result is unnecessary context growth, slower reasoning, increasing drift, and eventual loss of useful working context.

Conversation Fabric should make this workload first-class:

```text
parent campaign chat
    |
    +--> child 01: audit node 01
    +--> child 02: audit node 02
    +--> ...
    +--> child 44: audit node 44
    |
    v
compact durable ledger + cross-cutting synthesis
```

The parent coordinates. Children do bounded work. Full child transcripts are not re-injected into the parent.

## 2. Parent/child contract for the 44-node case

### Parent owns

- immutable campaign goal and audit rubric;
- ordered work list (44 nodes);
- dependency/DAG state;
- finding-ID namespace and compact finding index;
- small cross-cutting facts that later children actually need;
- exact branch/commit/evidence references;
- integration/final synthesis.

### Each child receives only

- child request id + deterministic digest;
- parent/campaign id;
- exact repository, branch/ref and binding;
- one bounded node/module scope;
- audit rubric;
- relevant prior cross-cutting findings, selected by dependency/relevance rather than transcript history;
- expected structured result schema.

### Each child returns only bounded planner evidence

At minimum:

```text
status
scope
summary
findings[]: id, severity, title, affected paths/symbols, recurrence links
positive_guarantees[]
tests_or_checks[]
commits_or_exact_evidence[]
followups[]
context_for_later_children[]
```

The terminal record must reference exact evidence. It must not paste full logs or the full conversation transcript.

For the sample campaign, the parent should need to retain roughly one compact row per completed node plus the global finding index, not 44 complete audit reports.

## 3. Execution model

Child **reasoning** may run in parallel when safe.

Current Local Agent execution remains serialized per registered repository. A work branch is not a second executor lane. Conversation Fabric v1 must not weaken repository leases just to gain apparent parallelism.

A child may therefore analyze in parallel, prepare GitHub changes on an isolated branch when allowed, and queue exact Local Agent execution; actual same-repository Local Agent tasks remain serialized.

## 4. Durable lifecycle

The product needs these distinct concepts:

1. `ChildRequest` — immutable admitted work + digest.
2. `ChildRegistration` — exact child ChatGPT conversation identity after creation/attach.
3. Logical lifecycle — requested -> registration_pending -> active -> terminal_pending_evidence -> terminal_recorded -> retired.
4. `child_checkpoint` — bounded non-terminal reasoning progress.
5. `child_terminal` — bounded final planner evidence.
6. Workflow/campaign state — parent-visible DAG/ledger, independent of Chrome tab identity.
7. Attention event — non-authoritative notification that durable evidence changed and the correct planner may need waking.

Chrome tab id and `chat-<fnv32>` are caches/routing hints only, never durable child identity.

## 5. Context isolation rules

The core feature is not merely opening more tabs. It is **bounded context composition**.

Before each child starts, build its context from durable structured records. Never construct it by copying the whole parent transcript.

Rules:

- default-deny old child prose;
- include only declared dependencies and relevant global findings;
- cap summaries/findings/arrays by schema;
- point to exact files/commits/results instead of embedding large evidence;
- parent receives compact terminal records, not the child transcript;
- re-open detailed evidence on demand;
- if a child discovers a reusable fact, promote that fact explicitly to `context_for_later_children` / global finding state.

This is the mechanism that prevents the 44-node campaign from killing the parent context window.

## 6. One development branch

Canonical development branch:

```text
develop/conversation-fabric
```

It currently starts from the latest transient-recovery development tree:

```text
fc4cb25da4c779daff87e93dedaa906363e3b49e
```

That preserves the newest bounded Chat Bridge recovery work while keeping `main` unchanged.

No new work should continue independently on the seven donor branches.

## 7. Donor migration map

### Already absorbed by branch ancestry

From:

- `work/chat-bridge-live-chat-states`
- `maintenance/transient-recovery-patch`
- `work/transient-recovery-validation`

Preserve the final tree only. Earlier two branches are historical checkpoints of the same line.

Assets include recognition/recovery for connection interruption, extended thinking and proven no-progress stall; Bridge-owned bounded continuation/reload behavior; proactive reporting; reload reservation across MV3 restart; and the associated tests/audit.

### `feature/conversation-fabric-superchat`

Use its re-audit as design input, especially:

- same-repository Local Agent execution is serialized;
- fresh child creation requires a separate pre-registration spawn transaction;
- child identity is request+digest, then exact `/c/<id>`;
- browser spawn state must not overload normal `bridgeState`;
- manual attach is mandatory fallback;
- child reasoning checkpoints are not executor `[AGENT_PROGRESS]`;
- GitHub connector policy is not a technical capability sandbox.

The branch itself is superseded by this branch.

### `feature/chat-bridge-event-wake`

Verified donor code baseline:

```text
8da2dd576fd2d5e076961886492f59c0164fdbf2
```

Preserve/selectively port:

- durable `task_result_ready` outbox;
- notification-only Native Messaging host;
- exact WAIT_TASK ownership/routing;
- durable pending wake/restart semantics;
- scheduled reconciliation fallback;
- event/restart/tamper tests and live evidence.

Do **not** overwrite newer central Chat Bridge files wholesale. Port behavior into current owners and retain newer timeout/transient recovery.

### `feature/openworker-governance`

Verified workflow code baseline:

```text
09210f66972158a13da8646cce4db11f35d341c8
```

Preserve/selectively port:

- isolated `local_agent/workflow/` contracts/state/store/revisions/coordinator;
- deterministic workflow and child identities;
- planner checkpoints and user gates;
- exact Git-backed child publication and cancellation;
- shared control-Git lock;
- explicit one-cycle/manual workflow CLI;
- disposable Git integration/recovery tests;
- narrow self-protection/governance findings.

Do not wire an automatic production scheduler yet.

### `plan/consolidated-development-roadmap`

Its useful architecture decisions are folded into this direction. The planning branch itself is superseded.

## 8. Implementation order

### Phase A — finish branch consolidation

- transplant Conversation Fabric contracts/design decisions;
- transplant isolated verified Execution Fabric core + tests;
- transplant isolated verified Event Wake substrate + tests;
- reconcile central Chat Bridge integration against the newer transient/timeout recovery tree;
- run full CI and exact browser tests;
- only then mark old development branches safe to delete/close.

### Phase B — child contracts

Implement pure bounded `ChildRequest`, `ChildRegistration`, lifecycle, `child_checkpoint` and `child_terminal` schemas with deterministic digests and strong negative tests.

No production browser side effects yet.

### Phase C — synthetic spawn/attach

Prove on disposable Chromium fixture:

- blank ChatGPT page -> one bootstrap -> concrete `/c/<id>`;
- persisted request before UI actuation;
- uncertain-send recovery without duplicate child;
- MV3 restart recovery;
- serialized spawn;
- manual attach fallback.

### Phase D — campaign/workflow integration

Connect child conversation state to the transplanted workflow/campaign substrate while preserving exact repository bindings and per-repository execution serialization.

### Phase E — unified attention events

Use one event transport for meaningful durable transitions:

- project task terminal evidence -> exact project chat wake;
- child terminal/checkpoint requiring parent action -> exact parent campaign chat wake;
- workflow waiting_planner/failed/completed -> exact orchestration chat wake.

An event is never success evidence; the planner must read the referenced durable record.

### Phase F — live 44-node acceptance test

Use a real multi-node audit as the product acceptance workload.

Success criteria:

- parent can allocate and recover all child jobs;
- no child transcript is copied wholesale into parent;
- parent context grows primarily with compact ledger state, not detailed reports;
- one child failure/restart does not corrupt campaign state;
- duplicate/uncertain child creation fails closed;
- cross-cutting findings can be promoted once and selectively reused;
- exact evidence remains inspectable;
- final synthesis can cover all 44 nodes without replaying all 44 transcripts.

## 9. Branch deletion gate

Do not delete any donor branch until all of these are true:

1. every keep-worthy code asset is present on `develop/conversation-fabric` or explicitly rejected with a recorded reason;
2. relevant donor tests are present and green or replaced by stronger current tests;
3. important donor docs/evidence are copied or summarized into canonical current docs;
4. no open PR is the sole remaining reference for a required asset;
5. a final tree/commit comparison confirms no unaccounted unique implementation remains.

After that, the desired repository shape is:

```text
main                         # production source
chat-bridge-state            # live Bridge runtime state
operator-control             # operator control state
develop/conversation-fabric  # single coherent development direction
```

Everything else should be closed/deleted as superseded history after migration verification.
