# Event-driven Chat Bridge pre-merge audit

Branch: `feature/chat-bridge-event-wake`
PR: `#77` (must remain draft during this audit)
Candidate extension: `0.5.11`

> [!IMPORTANT]
> Do not merge this branch to `main` during pre-merge validation. In this repository a `main` update may trigger the installed Local Agent self-update path. Release/merge requires an explicit operator decision after the remaining real-machine gates below.

## Intended property

A Local Agent task that reaches authoritative terminal-result publication can wake the exact hard-bound ChatGPT conversation without periodic no-change polling. The notification is a continuation hint only; `.agent/results/<task-id>.json` remains authoritative.

The scheduler is deliberately hybrid, not event-only:

- exact Local Agent tasks use `WAIT_TASK`, combining action-driven Native Messaging wake with scheduled reconciliation fallback;
- explicit `NEXT` remains for genuinely time-based or external rechecks;
- manual/operator wake controls remain available.

## Authority audit

The event path adds no execution authority:

- Local Agent emits bounded event metadata only after successful result publication;
- event payload contains identity/status metadata, not command output;
- Native Messaging host accepts handshake + ACK only;
- no shell, terminal, generic dispatch, arbitrary filesystem/log access, task create/cancel or repository rebind exists in the native transport;
- host registration is restricted to one exact Chrome extension origin;
- Bridge requires exact repository id, repository name, `agent_binding` and task id before routing;
- assistant controls cannot mutate repository binding or global Master;
- `task_result_ready` never substitutes for exact result inspection.

Result: no new repository-write/executor capability found in the event transport.

## Publication-order audit

Required ordering:

```text
task terminal outcome
  -> durable .agent/results/<task-id>.json commit
  -> successful control-branch push
  -> local task_result_ready outbox event
  -> Native Messaging
  -> Bridge persisted event/pending wake
  -> host ACK
  -> ChatGPT wake
  -> planner reads exact remote result
```

`core.publish_result()` records the local event only after the authoritative push succeeds. Event enqueue failure is diagnostic-only and cannot rewrite the authoritative task outcome.

## Durable outbox and identity audit

Outbox entries are bounded by count, age and serialized size and are replayed only when all identity/schema checks pass. Validation includes:

- regular non-symlink bounded file;
- schema v1 and exact `task_result_ready` type;
- bounded repository/task/status/digest fields;
- canonical lowercase binding UUID;
- timezone-aware timestamp;
- filename/event-id match;
- deterministic event id derived from repository/binding/task/digest identity.

Corrupt/tampered entries are pruned rather than replayed forever. Automated tests cover append, ACK, idempotent re-publication, collision, TTL pruning, tamper and identity mismatch.

## Native host audit

The host uses bounded Chrome Native Messaging framing, validates the exact Chrome extension caller origin and requires protocol-v1 handshake before events. ACK is session-scoped: only an event actually emitted by the current host session can be acknowledged/deleted.

On disconnect the extension reconnects with bounded exponential backoff starting at 5 seconds. Native transport is on-demand rather than a permanent MV3 keepalive and suspends while PAUSE/operator-disable/Master-off prevents delivery.

Installer/status diagnostics verify host name/type/path/origin, wrapper executable and restrictive modes.

## Golden-standard structure audit

Ownership remains separated across layers:

```text
control_protocol.js / bridge_state.js
            |
            v
event_wake_state.js        pure validation + identity + retention
            |
            v
worker_event_wake.js       persisted watches/recent/pending routing
            |
            +------> worker_schedule.js
            |
            +------> native_events.js
                        |
                        v
                 controls / delivery
```

Key enforced invariants:

- `event_wake_state.js` has no Chrome dependency;
- persistence/routing does not call Native Messaging, scheduling or prompt construction;
- import order follows dependencies;
- `worker_binding.js` owns event/planner prompt policy;
- scheduling guidance derives from the formal LAB command catalog;
- Native Messaging has handshake timeout and incompatible-state diagnostics;
- persisted diagnostics are bounded/allowlisted;
- malformed/far-future cached timestamps fail closed.

## Bridge routing audit

One conversation owns at most one exact watch. Event/watch matching requires:

```text
repository_id
repository
agent_binding
task_id
```

Persisted ownership also stores `bindingRevision` + `bindingSetAt`, preventing old events from crossing a rebind epoch after MV3 restart.

A second conversation cannot take the same exact task tuple while the original watch or pending wake owns it. Fast-task race is closed by durable Local Agent outbox plus Bridge recent-event cache: event-before-watch is promoted when the exact watch is later registered.

## Delivery/restart audit

Pending events are consumed only after successful ChatGPT delivery. Tests cover missing tab, transient delivery failure, MV3 worker restart before event and before delivery, stale-owner cleanup, duplicate replay and cross-binding isolation.

Scheduled reconciliation remains armed even when Native Messaging is absent or broken. `WAIT_TASK` therefore uses Native Messaging as latency optimization, not as correctness dependency.

## Prompt payload budget audit

0.5.11 separates one-time bootstrap from compact repeated wakes without weakening fail-closed safety text.

Measured worst-case prompt sizes:

```text
bootstrap: 1556 characters
wake:      1041 characters
event:      661 characters
```

The event prompt is intentionally smallest: hard-bound identity/safety context + exact event/task + instruction to read authoritative result evidence. It does not repeat the full bootstrap/control catalog.

## Automated CI evidence

The final live-loaded code/docs candidate `c69ebeb5bd3fe56ae385ef4b5c0aedbc1596a5f4` passed GitHub Actions run #791 (`35111409415`) with all jobs green:

- `test`, including compile, lint, Chat Bridge validation, unit and integration tests;
- `bridge-browser` disposable Chromium delivery/restart smoke;
- `coverage`;
- `python-314`;
- `macos-smoke`.

The earlier pre-evidence 0.5.11 candidate `adfc62d8754ae57e96eb7892041de6b566a3d20a` also passed full CI #789 (`35110618291`).

Evidence-only documentation commits after live validation move the PR head, so the final PR head must independently return green CI before release. These documentation commits do not change runtime behavior.

## Real Mac / live ChatGPT evidence

Exact candidate `c69ebeb5bd3fe56ae385ef4b5c0aedbc1596a5f4` was loaded from the dedicated candidate worktree and verified live with:

- extension `0.5.11`;
- content protocol `7/7`;
- exact `local-agent` repository/chat/binding retained;
- Native Messaging protocol v1 connected on demand;
- live compact wake payload path active.

Previous 0.5.10 live tests proved both exact watch-before-event and event-before-watch durable replay through the current Chrome/ChatGPT renderer.

### 0.5.11 host kill/restart durable replay — PASSED

Task/watch: `e2e-host-restart-0510-20260916`.

The exact native host PID `97585` was identified as the expected `local_agent.platform.chrome_native_host` process for extension `emgnoogeajmnkpijlaedlooabdgbblgb`, then killed with SIGTERM. The matching event was immediately queued through production `record_published_result()` into the real default outbox, before the 5-second minimum reconnect window elapsed.

Post-test DEBUG proved:

- `lastStatus = event_sent:e2e-host-restart-0510-20260916`;
- accepted and delivered event id both `evt-4174b0dd4c6e6142746e5d32146474ed`;
- `lastAcceptedTaskId = e2e-host-restart-0510-20260916`;
- new Native Messaging connection recorded at `2026-09-16T15:04:27.252Z`;
- event delivered at `2026-09-16T15:04:28.972Z`;
- final `currentWatch = null`;
- final `pendingWake = null`;
- final native transport `idle`, `lastError = null`.

This closes the real-Mac transport gate for:

```text
active WAIT_TASK
 -> host crash/kill
 -> durable event queued during outage
 -> native reconnect/restart
 -> replay + ACK
 -> live ChatGPT delivery confirmation
 -> watch/pending consumption
 -> transport idle
```

This is transport/recovery proof, not semantic real-task publication proof: the event was synthetic and no authoritative real `.agent/results/<task-id>.json` was manufactured in this bridge/operator-only repository.

Full timestamps/event ids and previous 0.5.10 evidence are recorded in `docs/chat_bridge/LIVE_EVIDENCE_2026-09-16.md`.

## Remaining real-machine release gates

Still open:

1. final PR-head full CI green after the evidence-only documentation commits;
2. explicit native-host installer `status --extension-id <id>` health output on the final loaded candidate path;
3. real short Local Agent task finishing before watch registration wakes correctly;
4. real multi-minute task produces no periodic no-change polling spam;
5. real done/failed/rejected/cancelled result wakes;
6. real deferred result publication wakes only after remote publication succeeds;
7. restart Chrome with pending/outbox state and verify recovery;
8. restart Local Agent around result publication and verify no lost authoritative result/event;
9. verify polling-only fallback with host intentionally absent.

Closed live gate:

- [x] kill/restart native host and verify durable replay to the exact live conversation.

The semantic real-task gates cannot be manufactured inside this `local-agent` conversation because its catalog binding is deliberately `execution_enabled: false` and bridge/operator-only.

## Explicit non-goals for v1

Do not add before release without a new security/design review:

- arbitrary terminal access;
- raw daemon log streaming;
- arbitrary filesystem reads;
- task creation/cancellation through Native Messaging;
- automatic ChatGPT tab creation;
- removal of scheduled reconciliation;
- repository rebind through event transport;
- continuous command-output streaming.

## Merge gate

The branch is pre-merge ready only when automated checks are green and the required real-machine gates are recorded. Even then, merge is a separate explicit operator action because it may activate Local Agent autoupdate.
