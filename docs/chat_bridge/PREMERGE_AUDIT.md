# Event-driven Chat Bridge pre-merge audit

Branch: `feature/chat-bridge-event-wake`
PR: `#77` (must remain draft during this audit)
Candidate extension: `0.5.12`

> [!IMPORTANT]
> Do not merge this branch to `main` during pre-merge validation. In this repository a `main` update may trigger the installed Local Agent self-update path. Release/merge requires an explicit operator decision.

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

Every Local Agent task JSON must use the exact bound `agent_binding` when execution is enabled. A `bridge/operator-only` conversation does not create Local Agent project task files. Never infer, substitute, inspect, queue, cancel, or execute work for another repository.

Result: no new repository-write/executor capability was introduced by the event transport.

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

Final operator-Mac installer status reported `healthy = true`, `problems = []`, manifest mode `0o600`, executable wrapper mode `0o700`, expected wrapper match, and exact registered extension origin.

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

## Delivery and restart audit

Pending events are consumed only after successful ChatGPT delivery. Missing tab, content readiness failures and retryable renderer states such as `assistant_busy` retain the exact pending event. `assistant_busy` is explicitly in the retry set and uses the configured busy retry interval rather than consuming the event.

0.5.12 adds bounded browser-startup reconciliation for a gap found in live 0.5.11 testing. A session-restored ChatGPT tab can appear after `onStartup` and may already be complete, so waiting only for `tabs.onUpdated(status=complete)` is insufficient. Browser startup therefore arms three one-shot reconciliation passes at approximately 1 s, 3 s and 8 s. Each pass refreshes configured content scripts and re-arms exact pending wakes. This is bounded recovery, not permanent polling.

Scheduled reconciliation remains armed when Native Messaging is absent or broken. `WAIT_TASK` therefore uses Native Messaging as a latency optimization, not as the sole correctness mechanism.

## Prompt payload budget audit

The compact runtime separates one-time bootstrap from repeated wakes without weakening fail-closed safety text.

Measured worst-case prompt sizes:

```text
bootstrap: 1556 characters
wake:      1041 characters
event:      661 characters
```

The event prompt is intentionally smallest: hard-bound identity/safety context + exact event/task + instruction to read authoritative result evidence.

## Automated CI evidence

Exact final live-loaded 0.5.12 code candidate:

- commit `8da2dd576fd2d5e076961886492f59c0164fdbf2`;
- GitHub Actions run #801 (`35117866465`);
- `test`, `bridge-browser`, `coverage`, `python-314` and `macos-smoke` all green.

The browser regression suite includes the restored-tab startup case that was missing from the earlier 0.5.11 test harness.

Evidence-only documentation commits after this code candidate move the PR head. The final documentation-synchronized head is therefore verified separately and recorded in the PR conversation/final review rather than by another self-invalidating documentation edit.

## Real Mac / live ChatGPT evidence

### Existing end-to-end delivery gates — PASSED

Earlier real-Chrome tests proved:

- exact watch-before-event live delivery;
- exact event-before-watch durable replay and live delivery;
- native-host kill -> durable outbox -> reconnect -> replay -> ACK -> live ChatGPT delivery;
- accepted event id equals delivered event id;
- pending/watch state is consumed only after successful delivery;
- Native Messaging returns to idle after delivery.

For the host restart test, accepted and delivered event id was `evt-4174b0dd4c6e6142746e5d32146474ed`, accepted at `2026-09-16T15:04:27.252Z` and delivered at `2026-09-16T15:04:28.972Z`.

### Full Chrome restart 0.5.11 — gap reproduced

Task `e2e-chrome-restart-0511-20260916` produced event `evt-b1ca5559ea7bc25620a7fe3407cbd291`. The event was accepted at `2026-09-16T15:22:05.726Z` but not delivered until `2026-09-16T15:35:15.850Z`, after later page activity. This exposed the restored-tab readiness gap addressed by 0.5.12.

### Full Chrome restart 0.5.12 — replay/retention PASSED; immediate send not claimed

Final live task: `e2e-chrome-restart-final-0512-20260916`.

After full Chrome quit, creation of the matching synthetic event while Chrome was closed, and browser restart, fresh DEBUG on exact 0.5.12 proved:

- extension `0.5.12`, content protocol `7/7`;
- exact repository/chat/binding retained;
- event `evt-5a518b7b5f2d3a5d5f5506a33d39ea33` accepted at `2026-09-16T15:56:27.716Z`;
- `currentWatch = null` after exact event acceptance;
- the same event remained as `pendingWake`;
- Native Messaging connected at `2026-09-16T15:56:27.714Z`, ACK/replay completed and transport returned to idle with no error;
- delivery attempt reported `assistant_busy`;
- one-minute retry remained scheduled;
- the event was not consumed and was not falsely marked delivered.

This is strong evidence that the 0.5.12 browser-startup recovery closes the lost/readiness side of the cold-start path: the durable event is replayed, accepted, persisted and retained safely across a renderer-busy attempt. It is **not** evidence of a successful immediate ChatGPT injection after full Chrome restart, because that final UI send was not observed in the operator run.

The branch is intentionally frozen at this point rather than extending operator testing indefinitely.

Full timestamps and event ids are recorded in `docs/chat_bridge/LIVE_EVIDENCE_2026-09-16.md`.

## Remaining release evidence

Still open, but not grounds for further manual testing in this audit session:

1. a real short Local Agent task whose authoritative result publication precedes the wake;
2. real multi-minute task with no repeated healthy polling spam;
3. real done/failed/rejected/cancelled result wakes;
4. real deferred result publication wake only after successful publication;
5. Local Agent restart around result publication;
6. polling-only fallback with Native Messaging intentionally absent;
7. an observed successful immediate ChatGPT send after full Chrome restart while the renderer is not busy.

The semantic real-task gates cannot be manufactured inside this `local-agent` conversation because its catalog binding is deliberately execution-disabled and `bridge/operator-only`.

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

The implementation/audit branch may be frozen when exact-head CI is green and the evidence above is recorded. Release readiness is a separate decision because some semantic real-task evidence remains open. Merge is always a separate explicit operator action because it may activate Local Agent autoupdate.
