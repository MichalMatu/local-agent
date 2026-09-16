# Event-driven Chat Bridge pre-merge audit

Branch: `feature/chat-bridge-event-wake`
PR: `#77` (must remain draft during this audit)
Candidate extension: `0.5.11`

> [!IMPORTANT]
> Do not merge this branch to `main` during pre-merge validation. In this repository a `main` update may trigger the installed Local Agent self-update path. Release/merge requires an explicit operator decision after the real-Mac gates below.

## Intended property

A Local Agent task that reaches authoritative terminal-result publication can wake the exact hard-bound ChatGPT conversation without periodic no-change polling. The notification is a continuation hint only; `.agent/results/<task-id>.json` remains authoritative.

The target scheduler is deliberately hybrid, not event-only. Exact Local Agent tasks use `WAIT_TASK`, which combines event-driven Native Messaging wake with durable scheduled reconciliation. Explicit `NEXT` remains available for genuinely time-based or external rechecks that are not represented by one exact Local Agent terminal task.

## Authority audit

The event path adds no execution authority:

- Local Agent emits event metadata only after successful result push.
- Event payload contains bounded identity/status metadata, not command output.
- Native host accepts handshake + ACK only.
- No shell, terminal, generic command dispatch, arbitrary file read, task create/cancel or log stream exists.
- Host registration is restricted to one exact Chrome extension origin.
- Bridge still requires exact stored repository id, repository name, `agent_binding` and task id before routing.
- Assistant controls still cannot mutate repository binding or Bridge Master.
- A result-ready event never substitutes for exact result inspection.

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

`core.publish_result()` records the local event only after the push succeeds. Event enqueue exceptions are logged and do not change the authoritative result status. A later/recovered successful publication uses the same result-publication path and deterministic event identity.

Result: no early-success notification path identified.

## Outbox integrity audit

The Local Agent outbox is bounded by count, age and serialized event size. Event files are accepted for replay only when all of the following validate:

- regular non-symlink bounded file;
- schema v1 and exact `task_result_ready` type;
- bounded repository id/name, task id, status and optional digest;
- canonical lowercase binding UUID;
- timezone-aware bounded emission timestamp;
- filename matches event id;
- event id is derived from repository/binding/task/digest identity.

Tampered/corrupt entries are pruned instead of being replayed forever.

Test evidence includes append/ACK, idempotent re-publication, collision, TTL pruning, tampered payload pruning and derived-id mismatch rejection.

## Native host audit

The host uses Chrome Native Messaging length-prefixed JSON with bounded inbound size. It validates a concrete Chrome extension caller origin and a protocol-v1 handshake. While connected it polls the durable outbox, so events created after connection are observed; delivery is not limited to startup replay.

ACK is session-scoped: the host accepts an event id only when that exact host process previously emitted it. A syntactically valid ACK for an unknown event fails closed instead of deleting arbitrary outbox state. Selector resources are context-managed and close deterministically on every return path.

A duplex integration test proves:

```text
connect -> hello -> empty outbox -> create event -> host emits event -> ACK -> outbox removal -> browser EOF -> host exits
```

Installer/status diagnostics verify exact host name/type/path/origin, regular files, executable wrapper and restrictive file modes. An optional expected extension id detects registration drift.

## Golden-standard structure audit

The final quality pass explicitly separates model, persistence/routing and orchestration instead of growing one event helper into a cross-layer state machine:

```text
control_protocol.js / bridge_state.js
            |
            v
event_wake_state.js        pure validation + identity + retention model
            |
            v
worker_event_wake.js       serialized persisted watches/recent/pending routing
            |
            +------> worker_schedule.js       alarms/reconciliation
            |
            +------> native_events.js         Native Messaging lifecycle + event orchestration
                        |
                        v
                 controls / delivery
```

Invariants enforced by tests:

- `event_wake_state.js` has no Chrome API dependency;
- persisted routing does not call Native Messaging, `scheduleAt()` or prompt construction;
- service-worker imports follow dependency order rather than relying on circular globals;
- `worker_binding.js` owns event/planner prompt policy;
- assistant scheduling guidance is derived from `control_protocol.js::COMMAND_CATALOG`, not a duplicated hard-coded list;
- test harness extension version comes from `manifest.json` rather than a second literal;
- Native Messaging has an explicit handshake timeout and visible `incompatible` state for protocol mismatch;
- persisted diagnostics use an explicit bounded allowlist;
- corrupt/far-future cached timestamps fail closed rather than being silently replaced with the current time.

This pass also updates `docs/GOLDEN_STANDARD.md` with candidate-only ownership and `WAIT_TASK` invariants while preserving the explicit statement that `main` is still production.

## Bridge routing audit

`WAIT_TASK` is bounded by the Local Agent-compatible task-id grammar. One conversation stores at most one current watch. Event/watch matching requires all of:

```text
repository_id
repository
agent_binding
task_id
```

Persisted watch/pending ownership additionally records the exact conversation binding epoch:

```text
bindingRevision
bindingSetAt
```

A rebind crash therefore cannot route an old task event through the new binding after MV3 restart. Stale pre-event watches are also reconciled so they cannot retain false ownership or keep Native Messaging alive.

A second conversation attempting to own the same exact task tuple is rejected while either the original watch **or its pending wake** still owns that task. It retains scheduled fallback rather than receiving the event. Events for another repository/binding/task cannot wake the conversation.

Fast-task race is closed by durable outbox + Bridge recent-event cache: event-before-watch is promoted when the exact watch is later registered.

## MV3/restart audit

Event state is separate from bridge schema v3 and persisted in `chrome.storage.local`:

- exact watches;
- bounded recent events;
- pending event wakes;
- bounded transport/delivery diagnostics.

Regression coverage replaces the service-worker harness:

1. after `WAIT_TASK` but before terminal event;
2. again after native receive but before ChatGPT delivery;
3. after bridge binding state changes but before event-state cleanup;
4. after a stale pre-event watch survives the same crash window.

Startup reconciliation preserves valid ownership, removes obsolete binding epochs and recreates only legitimate pending wake alarms.

## Delivery-loss audit

A pending event is consumed only after `chrome.tabs.sendMessage` returns a successful delivery response. Regression tests verify pending event retention when:

- the exact ChatGPT tab is missing;
- the send button is not ready/transient delivery fails.

Normal retry/reconciliation alarm remains armed. A later successful attempt consumes the event and delivery orchestration explicitly reconciles the now-idle native transport.

## Pause/Master/operator lifecycle audit

Native Messaging is on-demand rather than a permanent MV3 keepalive. It is wanted only for a watch whose exact conversation is:

- present and hard-bound to the same binding epoch;
- enabled;
- allowed by Bridge Master.

`PAUSE`, operator disable and Master-off retain the durable watch but disconnect/suppress the native process. `RESUME`, operator re-enable and Master-on reconnect and allow outbox replay. `STOP`, removal and rebind clear the old watch.

The extension's native state machine has a bounded handshake timeout. Protocol mismatch is recorded as `incompatible` and does not enter an automatic reconnect loop; a later explicit reconciliation can retry after the operator fixes/reloads the host.

## Fallback/liveness audit

`WAIT_TASK` does not remove scheduled reconciliation. The normal/default alarm remains a bounded fallback when:

- Native Messaging is not installed;
- extension id registration is wrong;
- host crashes/disconnects;
- Chrome/service worker restarts;
- delivery is paused/disabled;
- an event arrives but immediate scheduling races/fails.

Bridge persists the event before ACK. Immediate alarm creation is best-effort after persistence; schedule failure does not revoke durable event ownership, and the pre-existing fallback/restart reconciliation remains able to deliver it.

Planner prompts derive their schedule-command list from the formal command catalog, prefer exact `WAIT_TASK` after queueing, and reserve `NEXT` for genuinely time-based/external checks. This contract is covered by planner/protocol tests.

## Prompt payload budget audit

Chat Bridge 0.5.11 shortens the repeated wake text without weakening the hard-binding safety contract. The full fail-closed repository sentence, the bridge/operator-only restriction and the rule that chat controls cannot mutate global Master/repository binding remain explicit.

Measured worst-case prompt sizes after the 0.5.11 optimization are:

```text
bootstrap: 1556 characters
wake:      1041 characters
event:      661 characters
```

The event path is intentionally smallest because it carries only hard-bound identity/safety context, `[LA_EVENT=task_result_ready]`, the exact task id and the instruction to read authoritative result evidence. It does not repeat the full bootstrap/control catalog on every task completion.

This keeps the action-driven path materially cheaper than the old repeated wake payload while preserving scheduled fallback and manual controls.

## Security-sensitive negative cases covered

Automated coverage now includes:

- invalid caller origin;
- oversized Native Messaging frame;
- ACK before handshake, invalid ACK and ACK for an event not emitted by the current host session;
- extension/native protocol mismatch with fail-closed diagnostics;
- invalid/tampered outbox event;
- event identity mismatch;
- invalid/far-future persisted recent-event timestamps;
- unexpected/unbounded persisted diagnostics fields;
- cross-repository/binding route;
- cross-binding-epoch restart route;
- duplicate exact task ownership attempt while watched and while pending;
- stale-owner cleanup after rebind crash;
- fast event-before-watch race;
- MV3 restart before event and before delivery;
- missing tab/transient send failure retention;
- pause/resume/Master/operator lifecycle;
- wrong native-host extension id/path/executable mode;
- native transport absent in Node harness with alarm fallback.

## CI evidence

The pre-documentation 0.5.11 code candidate `adfc62d8754ae57e96eb7892041de6b566a3d20a` passed GitHub Actions run #789 (`35110618291`) with every job green:

- `test`, including compile, lint, Chat Bridge validation, unit and integration tests;
- `bridge-browser` disposable Chromium delivery/restart smoke;
- `coverage`;
- `python-314`;
- `macos-smoke`.

The preceding run #788 exposed two non-release failures: one case-sensitive documentation/prompt contract (`bridge/operator-only`) and one macOS timing/flaky integration assertion whose own log showed the unrelated late task had in fact been admitted. The prompt contract was corrected; the unchanged macOS behavior passed on #789.

Because this audit synchronization itself creates a newer documentation-only branch SHA, the final exact branch head must still receive its own green CI run before live validation is treated as final release evidence. No further source behavior change should be introduced between that run and the live 0.5.11 gates.

## Previous real-Mac evidence

Before 0.5.11 payload/documentation synchronization, real Mac Chrome + Native Messaging on 0.5.10 proved:

- protocol 7/7 and exact hard binding;
- `WAIT_TASK` watch registration with native transport connected;
- ordinary scheduled fallback delivery was confirmed and preserved the watch;
- synthetic watch-before-event wake reached ChatGPT and was accepted/delivered with the same event id, then cleared pending/watch;
- synthetic event-before-watch durable outbox replay reached ChatGPT and was accepted/delivered with the same event id, then cleared pending/watch.

These are valuable regression evidence, but synthetic events do not prove the semantic real-task publication gate and they do not replace final exact-SHA 0.5.11 live validation.

## Remaining real-machine release gates

These deliberately remain open because CI cannot prove the operator's installed Chrome/native-host state for the final exact 0.5.11 head:

1. final documentation-synchronized exact SHA full CI green;
2. load/reload that exact 0.5.11 SHA in the real Chrome profile;
3. confirm native-host status remains healthy for the exact loaded extension id;
4. real short task finishing before watch registration wakes correctly;
5. real multi-minute task produces no periodic no-change polling spam;
6. real done/failed/rejected/cancelled result wakes;
7. real deferred result publication wakes only after remote publication succeeds;
8. kill/restart host and verify durable replay + alarm fallback;
9. restart Chrome with pending/outbox state and verify recovery;
10. verify fallback with host intentionally absent.

## Explicit non-goals for v1

Do not add before release without a new security/design review:

- arbitrary terminal access;
- raw Local Agent log streaming;
- arbitrary filesystem reads;
- task creation/cancellation through Native Messaging;
- automatic ChatGPT tab creation;
- removal of scheduled reconciliation;
- repository rebind through event transport;
- continuous command-output streaming.

## Merge gate

The branch is pre-merge ready only when automated checks are green and the real-machine gates above are recorded for the exact SHA. Even then, merge is a separate explicit operator action because it may activate Local Agent autoupdate.
