# Conversation Fabric source asset map

Status: donor-branch inventory for `feature/conversation-fabric-superchat`.

Rule: current `main` is authoritative. Historical development branches are donor/evidence branches, not merge targets.

Canonical preimplementation audit: `docs/conversation_fabric/PREIMPLEMENTATION_REAUDIT.md`.

## 1. Production baseline that wins every conflict

```text
main@474000b5d4b015958fe92be491968dc4625b4a84
Local Agent 4.18.24
Chat Bridge 0.5.10
```

Preserve especially:

- current hard binding behavior;
- current content/delivery path;
- v4.18.24 assistant delivery-timeout recovery;
- preferred-tab + generation/binding revalidation;
- current repository execution lease semantics;
- one active Local Agent task per registered repository;
- self-update/restart guarantees;
- current operator/global disable controls.

Do not replace central current-main files with older feature-branch copies.

## 2. Donor: `feature/chat-bridge-event-wake`

Purpose: low-latency exact wake after authoritative Local Agent result publication.

### High-value isolated Local Agent modules

```text
local_agent/foundation/result_events.py
local_agent/platform/chrome_native_host.py
scripts/chat_bridge_native_host.py
```

### High-value isolated Bridge modules

```text
chat_bridge/event_wake_state.js
chat_bridge/native_events.js
chat_bridge/worker_event_wake.js
chat_bridge/worker_event_diagnostics.js
```

### Tests worth transplanting/adapting

```text
tests/test_result_events.py
tests/test_chrome_native_host.py
tests/test_chat_bridge_native_host_installer.py
chat_bridge/event_wake*.test.js
```

### Useful design/evidence docs

```text
docs/chat_bridge/EVENT_WAKE_ARCHITECTURE.md
docs/chat_bridge/PLANNER_RUNTIME_CONTRACT.md
docs/chat_bridge/PREMERGE_AUDIT.md
docs/chat_bridge/LIVE_EVIDENCE_2026-09-16.md
docs/chat_bridge/TODO.md
```

### Preserve conceptually

- event only after authoritative result push;
- bounded metadata only;
- durable outbox/replay/ACK;
- exact repository/binding/task matching;
- event-before-watch recovery;
- MV3 restart persistence;
- pending wake survives transient send failure;
- scheduled reconciliation remains fallback;
- compact planner pacing.

### Critical donor limitation

`chrome_native_host.py` is intentionally notification-only. Inbound authority is handshake + ACK for events already emitted by Local Agent.

Do **not** reuse it as if it already supported browser-to-Local-Agent child registration. Conversation Fabric should preserve this host and later add a separate narrowly-scoped registration protocol/host.

### Do not port blindly

These overlap current main and must be behaviorally reimplemented/adapted:

```text
chat_bridge/content.js
chat_bridge/content_retry.js
chat_bridge/control_protocol.js
chat_bridge/dom_contract.js
chat_bridge/manifest.json
chat_bridge/service_worker.js
chat_bridge/worker_binding.js
chat_bridge/worker_controls.js
chat_bridge/worker_conversations.js
chat_bridge/worker_delivery.js
chat_bridge/worker_events.js
chat_bridge/worker_lab_commands.js
chat_bridge/worker_schedule.js
chat_bridge/worker_test_harness.js
local_agent/foundation/core.py
```

Current-main timeout recovery wins on conflict.

### Reliability findings to carry forward

- stale historical conversation-limit detection;
- inactive-tab interval wake defect;
- manual `Ctrl+R` recovery cases.

These are reliability prerequisites, not reasons to merge the old branch.

## 3. Donor: `feature/openworker-governance`

This branch contains two independent donor tracks.

### 3.1 Execution Fabric donor

High-value package/modules:

```text
local_agent/workflow/contract.py
local_agent/workflow/state.py
local_agent/workflow/store.py
local_agent/workflow/revisions.py
local_agent/workflow/revision_store.py
local_agent/workflow/effective_state.py
local_agent/workflow/activation.py
local_agent/workflow/continuation.py
local_agent/workflow/evidence.py
local_agent/workflow/coordinator.py
local_agent/workflow/lineage_*.py
local_agent/workflow/git_control_plane.py
local_agent/workflow/git_cancellation.py
local_agent/workflow/publishing.py
local_agent/workflow/methods.py
local_agent/workflow/method_specs/
local_agent/cli/workflow.py
local_agent/foundation/control_git_lock.py
```

Bring the donor tests with the corresponding modules rather than rewriting coverage from scratch.

### Strong behaviors to preserve

- bounded schemas;
- canonical deterministic digests;
- explicit DAG validation;
- explicit waiting/failure/interrupted states;
- append-only revisions;
- fsync/locking discipline;
- exact child task id/digest evidence matching;
- create-only publication;
- ambiguous push recovery/fail-closed behavior;
- exact cancellation;
- temporary-Git integration tests.

### Critical donor limitations

1. Workflow state/revisions are primarily stored under Local Agent application state; they are not already a central GitHub workflow database.
2. Git control code publishes/inspects project tasks; it does not solve Conversation Fabric registration.
3. Coordinator policy intentionally avoids concurrent coordinator-owned children in the same repository.
4. Production Local Agent repository execution leases also prevent two simultaneous tasks in one registered repository.
5. The workflow package is deliberately not wired into supervisor/daemon/launchd/Chat Bridge.

Therefore transplant the semantics, but add the corrected orchestration-input/status-projection layer and keep same-repository executor concurrency out of v1.

### 3.2 OpenWorker/governance donor

Useful ideas:

- narrow deterministic self-protection floors;
- command/admission security corpus methodology;
- exact-action/digest-bound approval patterns where a real user gate needs them;
- compact authorization provenance.

Do not import:

- generic permission engine;
- embedded/reviewer model;
- broad standing shell grants;
- connector/desktop automation framework.

## 4. Current-main Bridge owners to extend carefully

### `bridge_state.js` / `worker_state.js`

Current schema v3 is production-critical. Do not put spawn/workflow truth directly into the existing conversation record during the first implementation.

Preferred new namespace:

```text
conversationFabricState
```

with independent schema/version/migration.

### `control_protocol.js`

Current controls assume concrete `/c/<id>` conversation identity. New `SPAWN_CHILD`/attach commands require explicit semantics and may only actuate an already-existing child request.

Do not use existing `chat-<fnv32>` as durable child identity.

### `worker_delivery.js`

Reuse only after registration. It correctly requires an exact known conversation URL and should not be weakened to accommodate new-chat creation.

### `worker_transport.js`

Existing exact URL/content authorization is a feature. New-chat bootstrap needs a separate spawn capability rather than weakening `conversationForSender`/delivery authorization.

### `content.js`

Current sender verifies exact known URL before ordinary Bridge delivery. Add a separate pre-registration message type/state for spawn only; do not make normal delivery accept generic ChatGPT pages.

### `manifest.json`

Current permissions already include `tabs` and `scripting`, but `nativeMessaging` is not present on production 0.5.10. Attention Fabric/registration work must add permissions deliberately and preserve install/update behavior.

## 5. Current Local Agent owners that constrain same-repository parallelism

### `docs/MULTI_REPOSITORY.md` + supervisor/repository worker model

Repository execution leases guarantee that two tasks for the same configured repository do not execute concurrently.

### `work_branch`

Task-scoped branch selection does not create a second repository scheduler identity.

### Implication

Conversation Fabric v1 may create parallel same-repository reasoning contexts, but Local Agent execution for those contexts remains serialized unless a future separately-audited workspace-lane feature changes the repository model.

## 6. Current `runtime/progress.py` is not a donor for planner reasoning checkpoints

`[AGENT_PROGRESS]` is executor-command progress with bounded queueing. It should remain that.

Conversation Fabric needs separate bounded `child_checkpoint` / `child_terminal` records referencing exact commits/task/results.

## 7. Current runtime catalog limitation

Current runtime/catalog entries carry `execution_enabled` only. `local-agent` is execution-disabled infrastructure, but no `orchestration_enabled` field exists.

Superchat capability therefore requires a later runtime schema/protocol migration. Do not treat it as config-only work.

## 8. New code that should be authored fresh

Do not search donor branches for these as if they already exist:

```text
local_agent/conversation/contract.py
local_agent/conversation/state.py
local_agent/conversation/identity.py
local_agent/conversation/store.py
chat_bridge/conversation_fabric_state.js        # provisional naming
chat_bridge/worker_child_spawn.js               # provisional naming
chat_bridge/child_spawn_contract.js             # pure helpers if useful
conversation registration native host/protocol
synthetic new-chat browser fixture/smoke
```

Names remain provisional until Phase 0A freezes ownership.

## 9. Donor import rule

For every transplanted unit:

1. identify current-main owner/invariant;
2. copy/adapt the smallest coherent donor module;
3. port its focused tests first;
4. re-run against exact current-main-derived head;
5. preserve current timeout/binding/repository lease behavior;
6. document any authority expansion;
7. never use old donor CI as release proof for the new head.
