# Chat Bridge live validation evidence — 2026-09-16

Branch: `feature/chat-bridge-event-wake`
PR: `#77` (keep draft; do not merge without explicit operator approval)

## Final live candidate under validation

The operator Mac loaded the documentation-synchronized 0.5.11 candidate from the dedicated candidate worktree:

- commit: `c69ebeb5bd3fe56ae385ef4b5c0aedbc1596a5f4`
- extension: `0.5.11`
- content protocol: expected `7`, reported `7`, match `true`
- repository id: `local-agent`
- repository: `MichalMatu/local-agent`
- agent binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`
- conversation: `chat-fd34c75d`
- Native Messaging protocol while watched: `1`

The candidate worktree was explicitly detached at the exact commit above and `git rev-parse HEAD` returned that same SHA before the extension reload.

GitHub Actions run `#791` (`35111409415`) for this exact candidate completed successfully in all five jobs:

- `test` including `Validate chat bridge`
- `bridge-browser`
- `macos-smoke`
- `coverage`
- `python-314`

The PR remained draft/unmerged and `main` was not changed during validation.

## Prompt/pacing candidate

0.5.11 keeps the hybrid wake model while reducing repeated prompt cost:

- `WAIT_TASK`: action-driven Native Messaging wake plus scheduled reconciliation fallback;
- `NEXT`: retained for genuinely time-based or external rechecks;
- manual/operator wake paths remain available;
- `task_result_ready` remains a wake hint only and exact result evidence stays authoritative.

Measured worst-case prompt sizes for the 0.5.11 candidate are:

- bootstrap: 1556 characters;
- normal wake: 1041 characters;
- event wake: 661 characters.

Explicit hard-binding, bridge/operator-only and Master-switch safety invariants remain present despite the prompt reduction.

## Previous 0.5.10 live transport evidence

Runtime/code candidate previously validated on the same operator Mac:

- commit: `a658d722c00538691e9828038c45db639194a0ea`
- extension: `0.5.10`
- content protocol: expected `7`, reported `7`, match `true`

GitHub Actions run `#777` (`35102488484`) for that exact runtime/code commit completed successfully in all five jobs.

### Live regression: delivery confirmation

An ordinary scheduled/fallback wake reached the live ChatGPT conversation and diagnostics changed to:

- `bootstrapPending = false`
- `lastStatus = sent`

This validated the generalized delivery-acceptance path on the operator's current Chrome/ChatGPT renderer.

### Live `WAIT_TASK` -> event

Task id: `e2e-native-0510-20260916`

Before event creation diagnostics proved an exact persisted watch, connected Native Messaging protocol v1, no error and no pending wake. A synthetic event was created through the production `local_agent.foundation.result_events.record_published_result()` API using a temporary control directory and the exact hard binding.

The live conversation was autonomously woken with the exact event/task. Post-delivery diagnostics proved:

- `lastStatus = event_sent:e2e-native-0510-20260916`
- `currentWatch = null`
- `pendingWake = null`
- `lastAcceptedEventId = evt-38e1bec7fa015e769460b17c23974dc5`
- `lastDeliveredEventId = evt-38e1bec7fa015e769460b17c23974dc5`
- Native Messaging returned to idle with no error.

### Live fast-task race: event before watch

Task id: `e2e-fast-before-watch-0510-20260916`

A synthetic `task_result_ready` event was created while no watch existed and Native Messaging was idle. The conversation registered `WAIT_TASK` afterwards. The durable outbox/recent-event path replayed the exact earlier event and the live conversation woke autonomously.

Post-delivery diagnostics proved:

- `lastStatus = event_sent:e2e-fast-before-watch-0510-20260916`
- `currentWatch = null`
- `pendingWake = null`
- `lastAcceptedEventId = evt-f8fda7b6eb4ad72906664f220348d441`
- `lastDeliveredEventId = evt-f8fda7b6eb4ad72906664f220348d441`
- Native Messaging returned to idle with no error.

## 0.5.11 live host kill/restart durable replay

Task/watch id: `e2e-host-restart-0510-20260916`

After loading exact candidate `c69ebeb5bd3fe56ae385ef4b5c0aedbc1596a5f4`, live DEBUG proved:

- extension `0.5.11`;
- content protocol `7/7`;
- exact repository/chat/binding retained;
- Native Messaging connected with protocol v1;
- exact `currentWatch = e2e-host-restart-0510-20260916`;
- `pendingWake = null`.

The exact Native Messaging process was identified as PID `97585` running:

```text
python -m local_agent.platform.chrome_native_host chrome-extension://emgnoogeajmnkpijlaedlooabdgbblgb/
```

The test then killed only that exact process with `SIGTERM` and immediately created the matching synthetic result event through production `record_published_result()` into the real default Local Agent durable outbox. The extension reconnect policy has a 5-second minimum reconnect delay, so the event was queued during the host outage rather than after a completed reconnect.

The live conversation subsequently received and delivered the event. Post-test DEBUG proved:

- `lastStatus = event_sent:e2e-host-restart-0510-20260916`;
- `lastAcceptedEventId = evt-4174b0dd4c6e6142746e5d32146474ed`;
- `lastDeliveredEventId = evt-4174b0dd4c6e6142746e5d32146474ed`;
- `lastAcceptedTaskId = e2e-host-restart-0510-20260916`;
- `lastAcceptedAt = 2026-09-16T15:04:27.252Z`;
- `lastDeliveredAt = 2026-09-16T15:04:28.972Z`;
- Native Messaging `lastConnectAt = 2026-09-16T15:04:27.252Z`;
- Native Messaging `lastDisconnectAt = 2026-09-16T15:04:27.256Z`;
- final transport state `idle` with `lastError = null`;
- `currentWatch = null`;
- `pendingWake = null`;
- `recentEventCount = 3`.

This closes the live transport gate for:

```text
active WAIT_TASK watch
  -> exact native-host process killed
  -> matching event durably queued during outage
  -> Chrome/Bridge reconnect starts a new native host
  -> durable outbox event replayed
  -> event accepted and ACKed
  -> live ChatGPT delivery confirmed
  -> pending/watch consumed
  -> on-demand native transport returns idle
```

This test validates host crash/restart durable replay on real Chrome/macOS/ChatGPT for the final 0.5.11 code candidate. It does not by itself prove the semantic Local Agent task-result publication gate because the injected event was synthetic.

## What the live tests prove

The operator-Mac gates now have direct evidence for:

- real Chrome extension 0.5.11 loaded from exact candidate commit `c69ebeb5...`;
- final-candidate content protocol `7/7` compatibility;
- exact hard binding retained across reload;
- real installed macOS Native Messaging transport connecting on demand;
- live ChatGPT delivery confirmation on the current renderer;
- exact watch-before-event event routing;
- exact event-before-watch durable replay;
- exact host kill -> durable outbox -> reconnect -> replay -> delivery path;
- accepted event id equals delivered event id;
- pending/watch state is consumed only after successful live delivery;
- native transport returns to idle after delivery;
- scheduled fallback remains configured independently of Native Messaging.

## What these tests do NOT prove

The `task_result_ready` events above were synthetic transport smoke events created through the production event API with temporary repository binding/control metadata. They did **not** create or inspect a real authoritative `.agent/results/<task-id>.json` result in the bound repository.

Therefore these results must not be described as proving the semantic real-task publication gate. Still-open release evidence includes, where applicable:

- a real Local Agent task whose authoritative result is published before event creation;
- real success/failed/rejected/cancelled terminal statuses;
- deferred publication waking only after successful remote publication;
- multi-minute no-spam behavior with a real task;
- Chrome restart recovery with pending/outbox state;
- Local Agent restart around publication;
- intentional host-absent polling fallback.

The `local-agent` binding used by this conversation is bridge/operator infrastructure with execution disabled, so this validation intentionally did not create Local Agent project task files merely to manufacture a semantic task-result test.

## Release/merge constraint

This evidence does not authorize a merge. PR `#77` must remain draft and `main` must remain unchanged until the operator explicitly approves release/merge. A `main` update may trigger Local Agent autoupdate.
