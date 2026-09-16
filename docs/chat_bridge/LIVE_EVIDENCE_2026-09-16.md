# Chat Bridge live validation evidence — 2026-09-16

Branch: `feature/chat-bridge-event-wake`
PR: `#77` (keep draft; do not merge without explicit operator approval)

## Candidate under live validation

Runtime/code candidate validated on the operator Mac:

- commit: `a658d722c00538691e9828038c45db639194a0ea`
- extension: `0.5.10`
- content protocol: expected `7`, reported `7`, match `true`
- repository id: `local-agent`
- repository: `MichalMatu/local-agent`
- agent binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`
- conversation: `chat-fd34c75d`
- Native Messaging protocol after `WAIT_TASK`: `1`

GitHub Actions run `#777` (`35102488484`) for the exact runtime/code commit completed successfully in all five jobs:

- `bridge-browser`
- `test`
- `macos-smoke`
- `coverage`
- `python-314`

The PR remained draft/unmerged and `main` was not changed during this validation.

## Live regression: delivery confirmation

The previous live build could send a real ChatGPT wake while retaining `delivery_unconfirmed`, because DOM turn identity/text is not a stable delivery oracle in the live ChatGPT renderer.

On `0.5.10`, an ordinary scheduled/fallback wake reached the same live ChatGPT conversation and diagnostics changed to:

- `bootstrapPending = false`
- `lastStatus = sent`

This validates the generalized delivery-acceptance path on the operator's current Chrome/ChatGPT build: exact new-turn matching remains the strongest signal, with the bounded fallback requiring composer acceptance plus forward progress.

## Live `WAIT_TASK` -> event test

Task id: `e2e-native-0510-20260916`

Before event creation, diagnostics proved:

- `lastStatus = waiting_task:e2e-native-0510-20260916`
- exact `currentWatch` persisted
- Native Messaging `state = connected`
- Native Messaging `protocolVersion = 1`
- `lastError = null`
- `pendingWake = null`

A synthetic event was then created through the real `local_agent.foundation.result_events.record_published_result()` API using a temporary control directory and the exact hard binding. The live conversation was autonomously woken with:

```text
[LA_EVENT=task_result_ready]
[LA_TASK=e2e-native-0510-20260916]
```

Post-delivery diagnostics proved:

- `lastStatus = event_sent:e2e-native-0510-20260916`
- `currentWatch = null`
- `pendingWake = null`
- `recentEventCount = 1`
- `lastAcceptedEventId = evt-38e1bec7fa015e769460b17c23974dc5`
- `lastDeliveredEventId = evt-38e1bec7fa015e769460b17c23974dc5`
- `lastAcceptedTaskId = e2e-native-0510-20260916`
- `lastDeliveredAt` populated
- Native Messaging returned to `state = idle`
- Native Messaging `lastError = null`

This validates the real-Mac transport/UI path:

```text
WAIT_TASK
  -> on-demand Native Messaging connect
  -> exact event acceptance
  -> persisted pending ownership
  -> live ChatGPT wake
  -> delivery confirmation
  -> pending/watch consumption
  -> native transport idle
```

## Live fast-task race: event before watch

Task id: `e2e-fast-before-watch-0510-20260916`

A second synthetic `task_result_ready` event was created while no watch existed and Native Messaging was idle. Only afterwards the conversation registered:

```text
[LAB:WAIT_TASK=e2e-fast-before-watch-0510-20260916]
```

The live conversation was then autonomously woken with the exact earlier event:

```text
[LA_EVENT=task_result_ready]
[LA_TASK=e2e-fast-before-watch-0510-20260916]
```

Post-delivery diagnostics proved:

- `lastStatus = event_sent:e2e-fast-before-watch-0510-20260916`
- `currentWatch = null`
- `pendingWake = null`
- `recentEventCount = 2`
- `lastAcceptedEventId = evt-f8fda7b6eb4ad72906664f220348d441`
- `lastDeliveredEventId = evt-f8fda7b6eb4ad72906664f220348d441`
- `lastAcceptedTaskId = e2e-fast-before-watch-0510-20260916`
- `lastDeliveredAt` populated
- Native Messaging returned to `state = idle`
- `lastError = null`

This validates the real durable-outbox/replay fast-task transport race: event creation before `WAIT_TASK` did not lose the event, and later watch registration connected the host and replayed the exact matching event.

## What these live tests prove

The operator-Mac gates now have direct evidence for:

- real Chrome extension `0.5.10` loaded from the candidate worktree;
- protocol `7/7` content-script compatibility;
- exact hard binding retained across reload;
- real installed macOS Native Messaging transport connecting on demand;
- live ChatGPT delivery confirmation on the current renderer;
- exact watch-before-event event routing;
- exact event-before-watch durable replay;
- accepted event id equals delivered event id;
- pending/watch state is consumed only after successful live delivery;
- native transport returns to idle after delivery;
- alarm/fallback delivery remains functional and no longer reports the old false `delivery_unconfirmed` state.

## What these tests do NOT prove

The two `task_result_ready` events above were synthetic transport smoke events created through the production event API with a temporary control directory. They did **not** create or inspect a real authoritative `.agent/results/<task-id>.json` result in the bound repository.

Therefore these results must not be described as proving the semantic real-task publication gate. Still-open release evidence includes, where applicable:

- a real Local Agent task whose authoritative result is published before event creation;
- real success/failed/rejected/cancelled terminal statuses;
- deferred publication waking only after successful remote publication;
- multi-minute no-spam behavior with a real task;
- host kill/restart replay;
- Chrome restart recovery with pending/outbox state;
- intentional host-absent fallback.

The `local-agent` binding used by this conversation is bridge/operator infrastructure with execution disabled, so this validation intentionally did not create Local Agent project task files merely to manufacture a semantic task-result test.

## Release/merge constraint

This evidence does not authorize a merge. PR `#77` must remain draft and `main` must remain unchanged until the operator explicitly approves release/merge. A `main` update may trigger Local Agent autoupdate.
