# Event-driven Chat Bridge pre-merge audit

Branch: `feature/chat-bridge-event-wake`
PR: `#77` (must remain draft during this audit)

> [!IMPORTANT]
> Do not merge this branch to `main` during pre-merge validation. In this repository a `main` update may trigger the installed Local Agent self-update path. Release/merge requires an explicit operator decision after the real-Mac gates below.

## Intended property

A Local Agent task that reaches authoritative terminal-result publication can wake the exact hard-bound ChatGPT conversation without periodic no-change polling. The notification is a continuation hint only; `.agent/results/<task-id>.json` remains authoritative.

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

A duplex integration test proves:

```text
connect -> hello -> empty outbox -> create event -> host emits event -> ACK -> outbox removal -> browser EOF -> host exits
```

Installer/status diagnostics verify exact host name/type/path/origin, regular files, executable wrapper and restrictive file modes. An optional expected extension id detects registration drift.

## Bridge routing audit

`WAIT_TASK` is bounded by the Local Agent-compatible task-id grammar. One conversation stores at most one current watch. Event/watch matching requires all of:

```text
repository_id
repository
agent_binding
task_id
```

A second conversation attempting to own the same exact tuple is rejected and retains scheduled fallback. Events for another repository/binding/task cannot wake the conversation.

Fast-task race is closed by durable outbox + Bridge recent-event cache: event-before-watch is promoted when the exact watch is later registered.

## MV3/restart audit

Event state is separate from bridge schema v3 and persisted in `chrome.storage.local`:

- exact watches;
- bounded recent events;
- pending event wakes;
- bounded transport/delivery diagnostics.

Regression coverage replaces the service-worker harness:

1. after `WAIT_TASK` but before terminal event;
2. again after native receive but before ChatGPT delivery.

Startup reconciliation recreates a pending wake alarm and the exact event is delivered once.

## Delivery-loss audit

A pending event is consumed only after `chrome.tabs.sendMessage` returns a successful delivery response. Regression tests verify pending event retention when:

- the exact ChatGPT tab is missing;
- the send button is not ready/transient delivery fails.

Normal retry/reconciliation alarm remains armed. A later successful attempt consumes the event.

## Pause/Master/operator lifecycle audit

Native Messaging is on-demand rather than a permanent MV3 keepalive. It is wanted only for a watch whose exact conversation is:

- present and hard-bound;
- enabled;
- allowed by Bridge Master.

`PAUSE`, operator disable and Master-off retain the durable watch but disconnect/suppress the native process. `RESUME`, operator re-enable and Master-on reconnect and allow outbox replay. `STOP`, removal and rebind clear the old watch.

This avoids keeping Chrome's worker and the Python native host alive while event delivery is disabled.

## Fallback/liveness audit

`WAIT_TASK` does not remove scheduled reconciliation. The normal/default alarm remains a bounded fallback when:

- Native Messaging is not installed;
- extension id registration is wrong;
- host crashes/disconnects;
- Chrome/service worker restarts;
- delivery is paused/disabled;
- an event arrives but immediate scheduling races/fails.

Pending event state is durable and schedule reconciliation prioritizes it after startup.

Planner prompts now prefer exact `WAIT_TASK` after queueing and reserve `NEXT` for genuinely time-based checks. This contract is covered by `planner_pacing_contract.test.js`.

## Security-sensitive negative cases covered

Automated coverage now includes:

- invalid caller origin;
- oversized Native Messaging frame;
- invalid/tampered outbox event;
- event identity mismatch;
- cross-repository/binding route;
- duplicate exact task ownership attempt;
- fast event-before-watch race;
- MV3 restart before event and before delivery;
- missing tab/transient send failure retention;
- pause/resume/Master/operator lifecycle;
- wrong native-host extension id/path/executable mode;
- native transport absent in Node harness with alarm fallback.

## CI evidence

An earlier implementation candidate, `098df38bf7f630cd28b6d56b42da8ea16f130673`, passed the repository's full GitHub Actions matrix including Linux tests/lint/compile/Bridge validation, Python 3.14, coverage, macOS smoke and disposable Chromium Bridge browser smoke.

That evidence is not sufficient for release after subsequent hardening. The exact final branch SHA must independently pass the full matrix before the PR is considered ready.

## Remaining real-machine release gates

These deliberately remain open because CI cannot prove the operator's installed Chrome/native-host state:

1. final exact SHA full CI green;
2. exact SHA disposable Chromium profile green;
3. install the host on the real Mac with the exact currently loaded extension id;
4. native-host `status --extension-id <id>` reports healthy;
5. real short task finishing before watch registration wakes correctly;
6. real multi-minute task produces no periodic no-change polling spam;
7. real done/failed/rejected/cancelled result wakes;
8. real deferred result publication wakes only after remote publication succeeds;
9. kill/restart host and verify durable replay + alarm fallback;
10. restart Chrome with pending/outbox state and verify recovery;
11. verify fallback with host intentionally absent.

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
