# Conversation Fabric source asset map

Status: donor-branch inventory for `feature/conversation-fabric-superchat`.

Rule: current `main` is authoritative. Old development branches are **donor branches**, not merge targets.

## 1. Production baseline to keep intact

Current production base:

```text
main@474000b5d4b015958fe92be491968dc4625b4a84
Local Agent 4.18.24
Chat Bridge 0.5.10
```

Keep current-main behavior as the starting point, especially:

- exact hard binding;
- current content/delivery path;
- v4.18.24 assistant delivery-timeout recovery;
- preferred-tab and generation/binding revalidation;
- scheduled/manual wake semantics;
- self-update/restart guarantees;
- current repository/supervisor execution model.

Do not replace central current-main Chat Bridge files with older feature-branch copies.

## 2. Donor: `feature/chat-bridge-event-wake`

Purpose of donor branch: low-latency exact conversation wake after authoritative Local Agent result publication.

### High-value isolated modules to port/adapt

Local Agent:

```text
local_agent/foundation/result_events.py
local_agent/platform/chrome_native_host.py
scripts/chat_bridge_native_host.py
```

Chat Bridge:

```text
chat_bridge/event_wake_state.js
chat_bridge/native_events.js
chat_bridge/worker_event_wake.js
chat_bridge/worker_event_diagnostics.js
```

Supporting tests:

```text
tests/test_result_events.py
tests/test_chrome_native_host.py
tests/test_chat_bridge_native_host_installer.py
chat_bridge/event_wake*.test.js
```

Useful design/evidence docs:

```text
docs/chat_bridge/EVENT_WAKE_ARCHITECTURE.md
docs/chat_bridge/PLANNER_RUNTIME_CONTRACT.md
docs/chat_bridge/PREMERGE_AUDIT.md
docs/chat_bridge/LIVE_EVIDENCE_2026-09-16.md
docs/chat_bridge/TODO.md
```

### Behaviors to preserve conceptually

- event is emitted only after authoritative terminal-result publication;
- event payload is bounded metadata, never command/result body;
- durable outbox + replay + ACK;
- Native Messaging is notification transport, not generic host authority;
- exact repository/binding/task ownership;
- event-before-watch race closure;
- MV3 restart persistence;
- pending wake survives transient delivery failure;
- scheduled reconciliation remains fallback;
- real Mac installer/transport evidence;
- prompt compaction and event-driven pacing.

### Do not port blindly

These files overlap heavily with current main and must be reimplemented/merged behaviorally rather than copied wholesale:

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

Current-main timeout recovery wins where behavior conflicts.

### Additional defects/evidence worth carrying forward

The branch records three useful Bridge reliability items:

- stale historical conversation-limit detection;
- ordinary interval wake failure in inactive ChatGPT tab;
- some reload/content transitions requiring manual `Ctrl+R`.

Those are inputs to current-main reliability work, not reasons to merge the old branch.

## 3. Donor: `feature/openworker-governance`

This branch contains two separate donor tracks.

### 3A. Execution Fabric donor

Verified isolated workflow implementation baseline recorded by that branch:

```text
09210f66972158a13da8646cce4db11f35d341c8
```

High-value package:

```text
local_agent/workflow/
```

including:

- immutable workflow contracts;
- DAG/state machine;
- methods and method identity;
- durable store;
- evidence reconciliation;
- planner checkpoints;
- user gates;
- append-only revisions;
- activation/effective state;
- Git child publication;
- exact cancellation;
- lineage coordinator/cycle;
- manual operator controls.

Also preserve/adapt:

```text
local_agent/cli/workflow.py
local_agent/foundation/control_git_lock.py
tests/test_workflow_*.py
tests/fixtures/workflows/
```

Important architecture property:

> Execution Fabric coordinates existing Local Agent tasks. It does not become a second executor.

The donor deliberately contains no automatic supervisor/daemon/launchd/Chat Bridge scheduling integration. Keep that separation when transplanting the core.

### 3B. OpenWorker-inspired governance donor

Docs:

```text
docs/OPENWORKER_CODE_AUDIT.md
docs/OPENWORKER_GOVERNANCE_PLAN.md
```

High-value ideas:

- deterministic project-command self-protection floors;
- table-driven command/admission security corpus;
- compact policy/admission provenance;
- exact-digest/idempotent approval ideas for later consequential gates.

Explicitly reject as product direction:

- embedded reviewer LLM;
- generic permission engine copied from OpenWorker;
- broad desktop-agent permissions;
- standing shell grants;
- connector/provider framework;
- duplicate audit database;
- durable mid-command shell resume.

## 4. Already consumed donor: `work/chat-delivery-timeout-detection`

The functional code is already in production `main`/v4.18.24.

Do not re-import it from the branch. Treat current main as the only source of truth for:

- assistant timeout recognition;
- native Retry click;
- bounded durable retry budget;
- latest-turn checks;
- preferred-tab authorization;
- binding revision/generation checks;
- wake overlap protection;
- reload/restart recovery.

## 5. Stale/non-development branches

These are not product directions:

```text
audit/pre-restart-contract-hardening
docs/pre-restart-drift-cleanup
release/4.18.23-host-ops-onboarding
```

They are old bookmarks/bases with no unique future subsystem to port.

Operational branches are also not source-development donors:

```text
chat-bridge-state
operator-control
```

## 6. New code ownership map

Conversation Fabric should introduce new narrowly-owned modules instead of growing existing monoliths.

Candidate Local Agent/workflow owners:

```text
local_agent/conversation/contract.py
local_agent/conversation/state.py
local_agent/conversation/store.py
local_agent/conversation/registration.py
```

Candidate Chat Bridge owners:

```text
chat_bridge/child_chat_state.js
chat_bridge/worker_child_chats.js
chat_bridge/worker_child_diagnostics.js
```

The exact names are provisional. Responsibilities are not:

- pure schema/state separate from browser side effects;
- browser creation separate from workflow planning;
- Git/workflow publication separate from ChatGPT DOM handling;
- exact registration/dedup separate from prompt construction.

## 7. Porting rule

For every donor slice:

1. start from fresh current `main`;
2. write/port the focused tests first;
3. port the smallest isolated module;
4. adapt integration points to current owners;
5. prove no regression of v4.18.24 behavior;
6. record exact donor commit/path for traceability;
7. run focused tests, then full CI;
8. merge one coherent slice before beginning the next.

Do not solve historical divergence by rebasing 100+ old commits into one giant conflict resolution.

## 8. Initial reuse order

Recommended order:

```text
1. current-main reliability fixes
2. event outbox
3. native notification transport
4. exact task watch/event wake
5. Conversation Fabric contracts/state only
6. browser child creation in lab mode
7. durable child registration/progress
8. Execution Fabric core transplant
9. shared attention events for task + workflow transitions
10. bounded automatic workflow scheduler
11. Superchat production orchestration
```

This keeps each old branch valuable without inheriting its obsolete base state.