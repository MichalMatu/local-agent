# Chat Bridge event-driven wake architecture

Status: design for `feature/chat-bridge-event-wake`; not yet a production contract.

## Goal

Replace most healthy-task polling with a local event-driven continuation path:

```text
ChatGPT queues one Local Agent task
        |
        v
Chat Bridge records that this exact conversation is waiting for task X
        |
        v
Local Agent executes task X
        |
        v
exact durable task result is pushed successfully
        |
        v
Local Agent writes one small durable local event
        |
        v
Native Messaging host -> Chat Bridge service worker
        |
        v
Bridge validates binding + task watch and wakes only the owning conversation
        |
        v
ChatGPT reads the authoritative .agent/result and continues
```

The event is only a low-latency wake hint. It is never evidence that the task succeeded.

## Problem in the current loop

The current planner has no local completion signal. After queueing a task it schedules future wake-ups, reads daemon/run/result state, and goes quiet again if execution is still healthy.

That is safe but inefficient:

- short tasks may sit completed until the next alarm;
- long tasks cause repeated no-change planner turns;
- frequent polling creates avoidable ChatGPT traffic and conversation noise;
- choosing an accurate next polling interval is inherently approximate.

The executor already knows the exact transition to terminal result publication. The bridge should use that deterministic signal instead of trying to predict completion time.

## Non-goals

The first implementation must not:

- expose arbitrary shell execution to the extension or ChatGPT;
- expose a general terminal API;
- infer completion by parsing stdout/stderr or daemon log text;
- stream command output into ChatGPT;
- make native events authoritative success evidence;
- automatically rebind a conversation or infer repository identity;
- remove the existing scheduled reconciliation path;
- automatically open arbitrary ChatGPT conversations or tabs;
- add a second task scheduler inside Chat Bridge.

Task output needed by the planner should continue to come from bounded run/result evidence. A future diagnostics feature may expose narrowly scoped read-only health data, but that is separate from event wake.

## Existing invariants that remain unchanged

The implementation must preserve all current hard-binding rules:

```text
one ChatGPT conversation
    -> one stored repository id
    -> one stored repository name
    -> one immutable agent_binding
```

Local Agent independently continues to require repository registry binding, `.agent/binding.json` binding and task `agent_binding` equality before execution.

Chat Bridge remains transport/scheduling. ChatGPT remains the planner. Local Agent remains the deterministic executor.

## Authoritative completion boundary

A task must not generate a `task_result_ready` event merely because its process exited.

The useful wake boundary is:

> the exact terminal result is durable and remotely readable by the planner.

Today `core.publish_result()` writes the result, commits it to the control branch, pulls, and successfully pushes the control branch before returning. The event publisher should run only after this publication boundary has succeeded.

Consequences:

- `publication_pending` is not yet a completion wake;
- a deferred result publication must emit the event when retry/recovery later confirms the push;
- failed, cancelled and rejected tasks should wake the planner once their terminal result is remotely available, just like successful tasks;
- duplicate publication/recovery must not create duplicate logical wake events.

The implementation audit must identify every terminal-result publication path before code is changed.

## Exact conversation routing: task watches

Repository binding alone is not enough to identify one ChatGPT conversation. Multiple conversations may legitimately be bound to the same repository and therefore share the same `agent_binding`.

Event wake therefore uses an explicit per-conversation task watch.

Proposed assistant control:

```text
[LAB:WAIT_TASK=<task-id>]
```

Semantics:

1. the control is accepted only from the latest assistant response in the already hard-bound conversation;
2. Bridge stores `waitingTaskId` in that conversation's state;
3. the watch is scoped by the conversation's stored repository id and `agent_binding`;
4. only one active conversation may own a `(repository_id, agent_binding, task_id)` watch;
5. a conflicting watch from another conversation is rejected as `task_watch_conflict`;
6. registering a watch checks the recent terminal-event cache immediately, closing the short-task race described below;
7. matching terminal event consumption clears the watch after a durable pending wake has been recorded;
8. STOP/remove/rebind clears the watch; PAUSE keeps it but prevents delivery until normal resume semantics allow it;
9. a normal scheduled reconciliation may clear a stale watch after the planner proves the task is already terminal or no longer relevant.

The task JSON does not need a ChatGPT conversation id. This avoids putting browser routing identity into the executor task contract.

### Short-task race

A task can finish between GitHub queueing and the assistant response that registers `WAIT_TASK`.

Therefore an unmatched native event must not simply be discarded. The worker keeps a bounded, persisted recent-event cache keyed by repository/binding/task id. When `WAIT_TASK` is later accepted, Bridge checks that cache and immediately creates the wake if the terminal event already exists.

The cache must have:

- a strict maximum entry count;
- a TTL;
- deterministic oldest-first eviction;
- no raw command output or result body;
- persistent storage so service-worker restart does not reopen the race.

## Local event contract

Version 1 should contain only routing and deduplication metadata.

Example:

```json
{
  "schema_version": 1,
  "event_id": "opaque-stable-event-id",
  "event_type": "task_result_ready",
  "emitted_at": "2026-09-15T21:00:00+00:00",
  "repository_id": "litegraph",
  "repository": "MichalMatu/esp32s3_LiteGraph",
  "agent_binding": "canonical-lowercase-uuid",
  "task_id": "zigbee-c6-build-017",
  "task_digest": "optional-exact-task-digest",
  "result_status": "done"
}
```

Rules:

- all strings are bounded;
- `repository_id`, repository name and `agent_binding` come from executor-owned repository context, not task prose;
- `task_id` is the exact terminal task id;
- `result_status` is informative only;
- no shell command, stdout, stderr, diff, secret, environment variable or result body is included;
- unknown schema versions or event types fail closed;
- duplicate `event_id` values are idempotent;
- logical duplicate terminal events for the same exact task/result are deduplicated.

The wake prompt should tell ChatGPT only that new exact result evidence is available, for example:

```text
[LA_EVENT=task_result_ready]
[LA_TASK=<task-id>]
```

It still carries the normal immutable `LA_AGENT`, `LA_REPO`, `LA_REPOSITORY` and `LA_CHAT` envelope. The planner must fetch/read the exact result before acting.

## Durable local outbox

Local Agent should publish events into a small durable local outbox rather than write directly to Chrome or parse its own log stream.

Properties:

- atomic file/state update;
- bounded retention;
- deterministic event id;
- survives Local Agent restart;
- survives Chrome restart;
- independent from whether the native host is currently connected;
- pruning occurs only after a durable handoff acknowledgement or expiry policy;
- no event publication failure may corrupt or invalidate the already-published task result.

The outbox is a notification side channel. Failure to write an event must be observable but must not rewrite a successful task result as failed.

Exact filesystem ownership/path is an implementation decision for Phase 0. It should use existing Local Agent state-path ownership rather than introduce a cwd-relative path.

## Native Messaging transport

The preferred browser transport is Chrome Native Messaging.

Why:

- the extension needs a narrow local-machine channel that normal web/content APIs intentionally do not provide;
- `chrome.runtime.connectNative()` provides a long-lived bidirectional port to an explicitly registered local application;
- the current minimum Chrome version is already above the version where a native messaging connection can keep an extension service worker alive;
- Chrome documents reconnecting from `Port.onDisconnect` when the native host exits.

Relevant Chrome documentation:

- https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
- https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle

### Native host responsibilities

The host is deliberately small. It may:

- perform a versioned handshake;
- read the Local Agent event outbox;
- send validated bounded event objects to the extension;
- receive ACKs for event handoff;
- expose read-only transport/outbox health for diagnostics;
- reconnect/replay unacknowledged events.

It must not:

- accept arbitrary shell commands;
- invoke Local Agent task execution;
- mutate repository bindings;
- queue/cancel tasks;
- read arbitrary filesystem paths requested by the extension;
- return arbitrary log files.

A compromised content script must not gain a generic host-command primitive through the service worker.

### Native host registration

Native Messaging registration requires an allowlist of extension origins. Development currently uses an unpacked extension, so installation must explicitly handle the extension id rather than assuming it.

Phase 0 must choose and document one supported strategy:

- generate the native-host manifest for the observed development extension id; or
- pin a stable extension identity before the feature is treated as production-ready.

Do not commit machine-specific absolute manifest paths or generated host registration files.

## Native handoff acknowledgement

The event outbox and extension storage need a clear durability boundary.

Recommended sequence:

1. native host sends an unacknowledged event;
2. service worker validates schema and hard-binding fields;
3. service worker persists the event into its bounded recent-event/pending-wake state;
4. only after the Chrome storage write succeeds does it ACK `event_id` to the native host;
5. the native host may then remove/compact that event from its durable outbox;
6. ChatGPT delivery proceeds from extension-owned durable state.

This prevents a service-worker crash between receiving an event and remembering it from losing the notification.

ACK means "Bridge durably owns this notification", not "ChatGPT processed the result".

## Bridge routing and delivery

When an event is accepted:

1. validate event schema, sizes, repository identity and canonical binding;
2. persist/dedupe it in the recent-event cache;
3. locate a conversation whose active watch matches repository id + `agent_binding` + task id;
4. reject ambiguous matches instead of guessing;
5. persist a pending event wake for the exact conversation;
6. ACK the native event after that durable state exists;
7. use the existing worker-owned ChatGPT content activation/delivery path;
8. preserve exact URL, draft-preservation, generation/busy and delivery-confirmation safeguards;
9. once wake submission is confirmed, clear pending delivery state and mark the event consumed for that conversation.

Event-driven delivery should reuse current normal wake transport rather than create a second DOM submission implementation.

If the ChatGPT tab is unavailable, the event remains pending. Version 1 should not automatically open an arbitrary tab as a side effect.

## Scheduled fallback and reconciliation

Event wake does not remove alarms.

For a healthy event transport:

- the planner uses `WAIT_TASK` instead of repeated short `NEXT` polling after queueing;
- the conversation retains a bounded normal reconciliation alarm as a safety net;
- an event normally wakes it much earlier than that alarm.

If native transport is unavailable or incompatible:

- `WAIT_TASK` must not pretend that push delivery is healthy;
- Bridge exposes the degraded state through diagnostics/capabilities;
- the planner falls back to the existing evidence-based `NEXT` policy.

The initial event-wake release should preserve the current normal/default alarm interval as the fallback rather than invent a second aggressive polling loop.

## Disconnect and restart behavior

### Native host disconnect

- worker records transport disconnected;
- reconnect uses bounded backoff;
- unacknowledged Local Agent events remain in the outbox;
- normal scheduled reconciliation remains active.

### Chrome/service-worker restart

- task watches, recent events and pending event wakes are stored in `chrome.storage`;
- connection is re-established on worker startup/activation;
- native outbox replay is deduplicated by `event_id`;
- pending ChatGPT delivery is reconciled through existing delivery guards.

### Local Agent restart

- the outbox remains durable;
- already published/acked events are not regenerated blindly;
- publication-recovery paths may emit the missing event only when exact result publication is confirmed and the logical event does not already exist.

### Bridge extension reload/update

- schema migration must preserve or intentionally invalidate watches/events with explicit version rules;
- incompatible native protocol blocks event wake but must leave ordinary scheduled bridge operation usable.

## Security model

Treat each boundary separately:

```text
Local Agent executor
  trusted to publish exact terminal metadata
        |
        v
local durable outbox
  bounded notification data only
        |
        v
Native Messaging host
  read-only event transport
        |
        v
MV3 service worker
  privileged validator/router
        |
        v
content script
  untrusted-page-adjacent delivery component
        |
        v
ChatGPT conversation
```

Required security properties:

- native host `allowed_origins` is restricted to the intended extension id;
- content scripts never call Native Messaging directly;
- all native messages are validated in the service worker;
- no native message can change repository binding;
- task events are matched against stored conversation binding, not event-controlled routing;
- unknown repository/binding combinations never cause a wake;
- conflicting task watches fail closed;
- event payload never becomes a shell command;
- event payload is rendered into a fixed bridge-owned wake template, not copied as free-form prompt text;
- bounded storage prevents native event floods from growing Chrome or Local Agent state without limit.

## Observability

Add diagnostics without turning diagnostics into authority.

`LAB:CAPABILITIES` / `LAB:DEBUG` should eventually expose at least:

- native event feature supported: yes/no;
- native host protocol version;
- native connection state;
- last native connect/disconnect time;
- recent event-cache count;
- pending event-wake count;
- active watch for the current conversation;
- last accepted event id/task id for the current conversation;
- last event-delivery outcome;
- degraded/fallback reason.

Do not expose arbitrary Local Agent log contents through these commands.

Local Agent diagnostics should expose bounded outbox health such as pending count, oldest age and last transport ACK, without needing Chrome DevTools.

## Proposed module boundaries

Names are provisional; ownership is not.

### Local Agent

`local_agent/runtime/events.py` or equivalent:

- event schema construction/validation;
- deterministic event identity;
- durable bounded outbox append/ack/compaction;
- no Chrome-specific protocol logic.

A publication integration point:

- emits `task_result_ready` only after confirmed result push;
- also covers deferred publication recovery;
- supplies repository-owned identity.

`local_agent/platform/chrome_native_host.py` or equivalent:

- Native Messaging framing;
- handshake/version negotiation;
- outbox read/replay;
- ACK handling;
- no executor authority.

Installer/deployment helper:

- renders/registers the macOS Native Messaging host manifest;
- validates the expected extension origin/id;
- supports removal/repair;
- commits no machine-specific generated manifest.

### Chat Bridge

`native_events.js` or worker-owned equivalent:

- connection lifecycle;
- native protocol validation;
- durable event acceptance/ACK ordering;
- reconnect/backoff.

`worker_event_wake.js` or equivalent:

- task-watch ownership;
- recent-event cache;
- exact conversation matching;
- pending event-wake lifecycle;
- event wake prompt construction.

`control_protocol.js`:

- strict `WAIT_TASK` syntax and limits;
- command catalog/capability documentation.

`bridge_state.js`:

- bounded persisted watch/recent-event/pending-event state and migration.

Existing `worker_transport.js` / `worker_delivery.js`:

- remain the only normal ChatGPT DOM delivery path;
- accept a validated event-wake reason/input rather than duplicating submission logic.

## Testing strategy

### Pure/unit tests

Cover:

- event schema bounds and invalid fields;
- deterministic dedupe;
- outbox append/ack/replay/compaction;
- WAIT_TASK parser and malformed variants;
- duplicate watch conflict;
- exact repository/binding/task matching;
- short-task race through recent cache;
- event replay after worker restart;
- unknown binding/repository rejection;
- pending wake lifecycle;
- incompatible native protocol;
- storage bounds/TTL eviction.

### Local integration tests

Use a fake native host process and real Native Messaging framing where practical:

- host handshake;
- event -> persisted bridge state -> ACK ordering;
- host death/reconnect/replay;
- malformed/native flood bounds;
- extension reload with unconsumed event;
- task finishes before WAIT_TASK registration;
- two conversations bound to the same repository cannot steal each other's task watch.

### Browser smoke

Extend the disposable Chromium profile suite:

- queue/watch simulation -> native event -> exact conversation wake;
- assistant busy at event arrival;
- absent ChatGPT tab;
- existing unrelated composer draft;
- duplicate native event;
- service-worker restart between receive and delivery;
- normal alarm fallback with native host unavailable.

### Real Mac E2E before release

Required evidence:

1. install/register native host for the real unpacked extension;
2. queue a bounded read-only Local Agent task from a hard-bound conversation;
3. register exact task watch;
4. observe no repeated healthy polling turn;
5. task result is pushed;
6. native event wakes the correct conversation promptly;
7. ChatGPT reads the exact terminal result and continues;
8. another conversation bound to the same repository does not wake;
9. disconnect native host and demonstrate scheduled fallback still works;
10. restart Chrome/extension/Local Agent in separate tests and demonstrate no lost or duplicate logical continuation.

## Rollout policy

Ship in stages. Do not replace polling in one step.

1. land local event/outbox infrastructure with no browser behavior change;
2. land native transport and diagnostics behind an explicit feature flag;
3. land task watches and event matching while normal alarms remain unchanged;
4. prove exact end-to-end wake on the development branch;
5. only then let the planner prefer WAIT_TASK over short healthy-task polling;
6. retain normal scheduled reconciliation as a permanent safety net unless later evidence justifies a separate decision.

## Success criteria

The feature is successful when:

- task completion usually wakes the owning chat within seconds of result publication rather than minutes later;
- long healthy tasks produce no repeated no-change ChatGPT polling turns while native transport is healthy;
- loss/restart/disconnect of the event channel cannot lose authoritative task evidence or permanently stall the conversation because scheduled reconciliation remains;
- no additional repository-routing authority is introduced;
- no arbitrary terminal/shell interface is exposed;
- exact result inspection remains mandatory before the planner continues work.
