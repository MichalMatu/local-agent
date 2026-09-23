# Superchat / Conversation Fabric implementation plan

Status: implementation planning only. No production behavior change is authorized by this document.

Branch: `feature/conversation-fabric-superchat`
Base: `main@474000b5d4b015958fe92be491968dc4625b4a84` (`v4.18.24`).

Canonical preimplementation audit: `docs/conversation_fabric/PREIMPLEMENTATION_REAUDIT.md`.

## 1. Strategy

Build Superchat as a sequence of narrow, independently verifiable capabilities on top of current `main`.

Do not merge historical `feature/chat-bridge-event-wake` or `feature/openworker-governance` wholesale. They are donor implementations/test libraries.

The implementation must preserve current authority boundaries:

- ChatGPT plans;
- Local Agent stays model-free and deterministic;
- existing project conversations remain hard-bound for Local Agent execution;
- current repository execution leases remain unchanged in v1;
- one registered repository still executes at most one Local Agent task at a time;
- GitHub/control evidence is durable; browser/tab state is recoverable cache;
- child creation never becomes execution authority.

## 2. Phase 0A — freeze corrected contracts

No behavior change.

Define exact schemas/state for:

- workflow/superchat identity;
- immutable `ChildRequest` id + canonical digest;
- child roles (`research`, `implementation`, `verification`, `integration`);
- durable logical child lifecycle;
- separate browser spawn transaction lifecycle;
- child registration record;
- planner checkpoint / terminal record;
- parent/child generation rules;
- exact canonical conversation URL identity after registration;
- manual attach/recovery path;
- one-level delegation rule;
- record authority: GitHub input vs local derived state vs project evidence vs Chrome cache.

Important contract decisions:

- `chat-<fnv32>` may remain a UI/cache key but is not a durable child identity;
- tab id is never durable identity;
- child request/digest exists before browser actuation;
- browser registration may only satisfy an existing exact request;
- large context is referenced by exact Git/commit/artifact references, not copied into bootstrap prompts;
- planner progress is not executor `[AGENT_PROGRESS]`.

Pure negative tests must later cover malformed ids, oversized payloads, invalid transitions, stale generation, duplicate/conflicting registration, cross-binding mismatch and canonical-digest stability.

Exit gate: two independent implementations could produce the same accepted/rejected state transitions from the written contract.

## 3. Phase 0B — browser feasibility spike before large implementation

Prove the most fragile assumption early: a Chrome extension can deterministically create and identify one new ChatGPT conversation without pretending the existing exact-URL delivery path already supports it.

### Synthetic browser fixture

Extend the disposable Chromium harness with a synthetic ChatGPT origin supporting:

```text
new-chat route without /c/<id>
-> composer ready
-> first user prompt accepted
-> route transition to /c/<generated-id>
-> first user message retained in DOM
```

Prototype only a lab spawn transaction:

```text
persist exact spawn request
-> create/open tab
-> inject one deterministic bootstrap marker
-> submit once
-> detect accepted first user turn
-> capture transitioned exact /c/<id> URL
-> persist provisional mapping
```

Required restart/race tests:

- service-worker restart after tab creation;
- restart after first prompt accepted but before URL persisted;
- delivery timeout where the prompt was actually accepted;
- unrelated user edit in the new tab;
- tab closed before identity exists;
- duplicate spawn command;
- route changes to an unexpected origin/path;
- two requests queued while only one spawn is allowed to actuate.

### Live feasibility gate

Only after the synthetic harness is strong, perform one explicit real-ChatGPT lab experiment with no Local Agent project execution attached.

The live test must prove either:

- automatic new-chat creation + first prompt + exact URL discovery works; or
- the manual attach fallback is operationally acceptable.

Do not build the large workflow transplant before this gate.

## 4. Phase 1 — pure Conversation Fabric core

Add inert code with no Chrome/native/Local Agent scheduling side effects.

Suggested ownership:

```text
local_agent/conversation/contract.py    # schemas/bounds/digests
local_agent/conversation/state.py       # pure logical lifecycle
local_agent/conversation/identity.py    # request/registration identity
local_agent/conversation/store.py       # local durable materialization/cache
```

The logical child state is separate from browser spawn state.

Conceptual durable lifecycle:

```text
requested
-> registration_pending
-> active
-> terminal_pending_evidence
-> terminal_recorded
-> retired
```

Conceptual browser spawn lifecycle:

```text
pending
-> tab_created
-> bootstrap_submitting
-> identity_discovered
-> registration_submitting
-> done
```

with explicit `failed` / `ambiguous` outcomes.

Exit gate: request, registration, terminal record, retirement and restart reconstruction work without any Chrome API.

## 5. Phase 2 — current-main reliability prerequisites

Before unattended orchestration, close known current Bridge/Local Agent reliability gaps.

Priority:

1. latest/current-turn-only conversation exhaustion detection;
2. deterministic reproduction and repair of inactive-tab ordinary interval wake;
3. deterministic reproduction and repair of remaining manual-`Ctrl+R` content/runtime transition dependency;
4. retain all v4.18.24 assistant-timeout recovery tests;
5. repair orphan-descendant/resource-lease recovery before long-lived autonomous concurrency is trusted.

These do not block pure Phase 0/1 work, but they block a production reliability claim.

Exit gate: one ordinary project chat survives background-tab, reload, stale content and assistant-error cases without manual intervention.

## 6. Phase 3 — Attention Fabric task events on current main

Port the proven event-wake donor in isolated slices.

### 3.1 Durable result-event outbox

Port/adapt `local_agent/foundation/result_events.py` after authoritative result publication.

Properties:

- event only after successful authoritative result publication;
- deterministic bounded identity;
- atomic persistence;
- replay/ACK;
- bounded count/age/size;
- enqueue failure never rewrites task result.

### 3.2 Notification-only native host

Port/adapt the donor event host and installer/health checks.

Preserve its authority boundary:

```text
Local Agent -> bounded event -> Native Messaging -> Bridge
Bridge -> hello/ACK only
```

Do not add child registration to this host.

### 3.3 Exact `WAIT_TASK`

Port/adapt exact watch ownership and pending event wake into current-main Bridge owners.

Retain scheduled reconciliation as correctness fallback.

Exit gate: real Local Agent terminal result wakes the exact existing hard-bound chat; native transport loss/restart cannot lose correctness.

## 7. Phase 4 — lab child spawn transaction + manual attach

Turn the Phase 0B spike into a bounded disabled-by-default Conversation Fabric capability.

### 4.1 Separate persistent namespace

Do not overload production `bridgeState` schema v3 with workflow/spawn truth.

Use a separate `conversationFabricState` schema for:

- child request cache/reference;
- spawn transaction state;
- provisional tab id;
- discovered child exact URL;
- registration generation;
- retry/ambiguity diagnostics.

### 4.2 Spawn authorization

An exact pre-existing child request/digest is required before `SPAWN_CHILD` can actuate the browser.

No generic "open a new chat and decide later" flow.

### 4.3 One spawn at a time

v1 serializes browser creation transactions. Registered children may work concurrently afterward.

### 4.4 Bootstrap marker

The first message includes machine-readable request id/digest markers plus the bounded human bootstrap.

On uncertain delivery, the Bridge first reconciles the original tab/URL/latest user marker before retrying. It never opens a second child merely because one send timed out.

### 4.5 Manual attach

Provide an operator/popup flow that attaches one pending exact child request to a user-opened fresh ChatGPT conversation.

Exit gate: automatic or manual creation can establish one exact provisional child identity; Chrome/service-worker restart does not create a duplicate.

## 8. Phase 5 — durable child registration through separate bounded native protocol

Do **not** broaden the notification event host.

Add a separate conversation-registration native host/protocol only for bounded child identity operations.

Allowed conceptual operations:

```text
hello
register_child
query_registration
retire_child
```

A registration request may carry browser-discovered identity only:

```text
child_request_id
child_request_digest
parent_exact_url
child_exact_url
lifecycle_generation
```

Local side loads all authority fields (workflow/node/repository/binding/role/branch) from the already-admitted request.

Forbidden:

- task creation;
- shell execution;
- arbitrary Git path writes;
- repository rebind;
- workflow node creation;
- branch selection from browser input.

Repeated exact registration is idempotent; conflicting registration fails closed.

Exit gate: Local Agent restart and Chrome restart both reconcile the same exact request to the same exact child URL without trusting Chrome storage alone.

## 9. Phase 6 — planner checkpoint / terminal evidence

Add Conversation Fabric evidence distinct from executor progress.

Initial record families:

```text
child_checkpoint
child_terminal
```

Checkpoint stages may include:

```text
analysis_complete
implementation_started
implementation_complete
verification_complete
blocked
```

Properties:

- create-only append sequence;
- exact request/workflow/revision/node identity;
- bounded summary/findings/contract changes;
- exact commit/task/result references;
- no whole transcript;
- no raw logs/secrets;
- terminal completion requires durable terminal record;
- model-authored claim such as "tests passed" is not authoritative without exact referenced result/CI evidence.

For the first prototype, child chats may publish these records through the existing GitHub connector/control path under explicit repository policy. This dependency is documented rather than hidden.

Exit gate: Superchat can reconstruct child status after losing the tab/transcript.

## 10. Phase 7 — transplant Execution Fabric core with corrected authority split

Port verified donor components selectively:

- workflow contract/state/store;
- methods;
- evidence;
- revisions/activation/effective state;
- Git child-task publication/cancellation;
- shared control-Git lock;
- lineage cycle;
- CLI;
- disposable-Git tests.

Keep it manually driven/inert at first.

### 10.1 Authority correction

The donor local store remains restart-efficient Local Agent materialization. Add an orchestration Git input/projection layer with one owner per record type:

Git-authoritative planner inputs:

- workflow manifest/request;
- append-only revisions;
- child requests;
- planner/user continuation decisions.

Local/derived runtime state:

- effective node states;
- dispatch/reconciliation state;
- scheduler backoff.

Project-authoritative evidence:

- task/result/claim/status;
- child task execution evidence.

Central Git projection:

- bounded workflow status/evidence references for Superchat inspection;
- conversation registration records.

Do not create two independently mutable workflow truths.

Exit gate: manual workflow can be reconstructed from durable inputs + exact project evidence and produce the same effective state after restart.

## 11. Phase 8 — orchestration runtime capability / Superchat

Current runtime schema v3 has only `execution_enabled`. Add orchestration only through an explicit schema/protocol migration.

Target capability concept:

```text
execution_enabled = false
orchestration_enabled = true
```

Migration must cover:

- runtime config schema/version;
- validator/fallback behavior;
- Bridge command authorization;
- project-vs-infrastructure-vs-orchestration chat distinction;
- negative tests proving ordinary project chats cannot acquire orchestration authority from a marker.

Superchat may:

- append workflow revisions;
- create child requests;
- inspect workflow projections/evidence;
- resolve planner checkpoints;
- create integration/verification nodes;
- request child spawn/retirement.

It may not directly publish arbitrary Local Agent project shell tasks. Execution Fabric remains deterministic fan-out authority.

## 12. Phase 9A — first product slice: same-repository modular conversations

Goal: prove the reasoning-quality hypothesis without breaking repository execution invariants.

Topology:

```text
Superchat
  +-- child A: module A
  +-- child B: module B
  +-- integration child
```

One project repository, separate Git branches for A/B.

Allowed parallelism:

- child reasoning can overlap;
- GitHub branch edits may overlap when branch ownership is disjoint;
- Local Agent tasks for that repository remain serialized;
- integration consumes exact commits/evidence.

No claim of same-repository Local Agent executor parallelism.

Measure:

- unrelated file churn;
- integration conflicts;
- duplicate abstractions;
- test failures after integration;
- rework;
- manual recovery;
- context/recap overhead versus a single-chat baseline.

Exit gate: modular conversations provide useful quality/depth without unacceptable integration cost.

## 13. Phase 9B — true existing-executor parallelism across repositories

Use two different registered repositories so current Local Agent parallel scheduler can execute both children concurrently under existing safety invariants.

Topology:

```text
Superchat
  +-- project child repo A -> Local Agent task A
  +-- project child repo B -> Local Agent task B
  +-- planner/integration checkpoint
```

Exit gate: two exact hard-bound child chats coordinate genuinely overlapping Local Agent execution and Superchat receives only meaningful completion/checkpoint attention.

## 14. Phase 10 — unified workflow attention events

Extend the task-event transport with bounded workflow attention events; do not add a second wake stack.

Candidate event types:

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

Events remain hints, not result bodies.

Do not wake parent on every progress checkpoint/heartbeat.

## 15. Phase 11 — integration and independent verification roles

Integration is first-class.

It receives exact predecessor commits/results/checkpoints and must reconcile:

- merge/rebase conflicts;
- shared interfaces/contracts;
- duplicate or contradictory abstractions;
- isolated-test assumptions;
- architecture drift;
- final diff/verification.

Optional verification child audits the integrated candidate from a fresh context and may reject it. It does not silently repair implementation unless a new implementation/revision is created.

Exit gate: parallel modular work does not bypass whole-system review.

## 16. Phase 12 — bounded automatic workflow scheduler

Only after manual Superchat + child lifecycle works end-to-end.

Preferred integration:

```text
supervisor bounded workflow discovery
-> select due workflow
-> invoke one exact lineage cycle
-> return to ordinary repository scheduling
```

No second worker pool and no embedded model loop.

Waiting planner/user workflows produce near-zero work except bounded reconciliation.

Global disable remains authoritative.

## 17. Phase 13 — governance hardening before wider unattended use

Port only narrow OpenWorker-derived protections as needed:

- project-command self-protection floors;
- security corpus;
- compact policy provenance;
- digest-bound approvals tied to concrete workflow user gates.

Do not import a generic permission engine/reviewer model.

Move individual protections earlier whenever a preceding phase broadens unattended authority.

## 18. Future project — same-repository Local Agent workspace lanes

This is explicitly **not Conversation Fabric v1**.

Only pursue if Phase 9A shows enough value that serialized local execution becomes the dominant bottleneck.

A separate design/audit must address:

- repository execution lease identity;
- multiple simultaneous repository statuses/tasks;
- control branch publication races;
- work/checkpoint workspace ownership;
- branch/worktree lifecycle;
- claims/cancellation/recovery;
- resource/descendant leases;
- global control probing;
- diagnostics and backward compatibility.

Do not implement by merely weakening the current repository lease.

## 19. Test pyramid

### Pure

- schema bounds;
- canonical digests;
- lifecycle transitions;
- duplicate/conflicting registration;
- stale generations;
- parent/child ownership;
- checkpoint sequencing;
- terminal/retirement invariants.

### Local durable store

- fsync/restart reconstruction;
- ambiguous/incomplete spawn state;
- exact idempotent registration;
- local projection reconstruction from Git inputs/evidence.

### Git integration

- create-only orchestration inputs;
- child checkpoint/terminal publication;
- conflicting writers;
- exact project task/result references;
- execution-fabric publication/cancellation;
- restart after partial publication.

### Browser synthetic

- blank new-chat creation;
- bootstrap acceptance;
- URL transition discovery;
- uncertain send recovery;
- duplicate spawn;
- manual attach;
- service-worker restart;
- tab close;
- parent/child simultaneously open;
- assistant timeout during bootstrap;
- serialized spawn queue.

### Native

- notification host remains notification-only;
- conversation-registration host accepts only exact existing requests;
- wrong digest/stale generation/conflicting URL rejected;
- restart/reconnect idempotency.

### Live

Only after synthetic/native coverage:

- one real child creation;
- Chrome restart/reconciliation;
- manual attach fallback;
- same-repo two-child modular slice with serialized Local Agent execution;
- multi-repo true parallel executor slice;
- integration child;
- logical retirement + optional tab close.

## 20. Release discipline

No donor CI result proves a transplanted slice on current main.

Each behavior-changing release requires exact-candidate focused tests, full CI and relevant macOS/browser smoke.

Keep production merges narrow enough that child-spawn, attention transport or workflow integration can be rolled back independently.

Do not merge PR #77 or PR #81 wholesale.

Do not move `main` merely to make this design branch easier to test.
