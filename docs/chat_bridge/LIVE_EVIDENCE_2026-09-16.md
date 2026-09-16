# Chat Bridge live validation evidence — 2026-09-16

Branch: `feature/chat-bridge-event-wake`
PR: `#77` (keep draft; do not merge without explicit operator approval)

## Final live candidate under validation

The operator Mac loaded the final cold-start candidate from the dedicated candidate worktree:

- commit: `8da2dd576fd2d5e076961886492f59c0164fdbf2`
- extension: `0.5.12`
- content protocol: expected `7`, reported `7`, match `true`
- repository id: `local-agent`
- repository: `MichalMatu/local-agent`
- agent binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`
- conversation: `chat-fd34c75d`
- Native Messaging protocol while watched: `1`

The candidate worktree was explicitly detached at the exact commit above before the extension reload. Live DEBUG after the final Chrome restart reported extension `0.5.12`, protocol `7/7`, the same hard binding, and the expected configured conversation.

GitHub Actions run `#801` (`35117866465`) for this exact code candidate completed successfully in all five jobs:

- `test` including `Validate chat bridge`
- `bridge-browser`
- `macos-smoke`
- `coverage`
- `python-314`

The PR remained draft/unmerged and `main` was not changed during validation.

## Prompt/pacing candidate

The candidate keeps the hybrid wake model while reducing repeated prompt cost:

- `WAIT_TASK`: action-driven Native Messaging wake plus scheduled reconciliation fallback;
- `NEXT`: retained for genuinely time-based or external rechecks;
- manual/operator wake paths remain available;
- `task_result_ready` remains a wake hint only and exact result evidence stays authoritative.

Measured worst-case repeated prompt sizes from the compact runtime candidate are:

- bootstrap: 1556 characters;
- normal wake: 1041 characters;
- event wake: 661 characters.

Explicit hard-binding, `bridge/operator-only` and Master-switch safety invariants remain present despite the prompt reduction.

## Native host installer health — PASSED

The operator ran the production status command against extension id `emgnoogeajmnkpijlaedlooabdgbblgb` from the candidate worktree. It reported:

- `healthy = true`;
- `problems = []`;
- manifest mode `0o600`;
- wrapper mode `0o700` and executable;
- wrapper matches expected installation;
- registered and expected extension ids match;
- exact allowed origin is configured.

## Previous live transport evidence

### Live watch-before-event and fast event-before-watch

0.5.10 live tests proved both exact event paths through the real Chrome/ChatGPT renderer:

- watch-before-event: `evt-38e1bec7fa015e769460b17c23974dc5`;
- event-before-watch replay: `evt-f8fda7b6eb4ad72906664f220348d441`.

Both ended with accepted event id equal to delivered event id, no pending wake and Native Messaging back at idle.

### 0.5.11 host kill/restart durable replay — PASSED

Task/watch id: `e2e-host-restart-0510-20260916`.

The exact Native Messaging process was killed with `SIGTERM`, then the matching synthetic result event was created through production `record_published_result()` into the real durable outbox before the reconnect window elapsed.

Post-test DEBUG proved:

- `lastStatus = event_sent:e2e-host-restart-0510-20260916`;
- accepted and delivered event id `evt-4174b0dd4c6e6142746e5d32146474ed`;
- `lastAcceptedAt = 2026-09-16T15:04:27.252Z`;
- `lastDeliveredAt = 2026-09-16T15:04:28.972Z`;
- final `currentWatch = null`;
- final `pendingWake = null`;
- final transport state `idle`, `lastError = null`.

This closes the real-Mac native-host crash/restart durable replay gate.

## Chrome full-restart evidence

### 0.5.11 original failure — reproduced

Task id: `e2e-chrome-restart-0511-20260916`.

A full Chrome quit was performed with an exact watch armed. While Chrome was closed, a matching production-format synthetic event was written to the real durable outbox. On Chrome restart the event was accepted by the Bridge but was not delivered promptly to ChatGPT. It was only delivered after later page activity.

The decisive diagnostics were:

- accepted event: `evt-b1ca5559ea7bc25620a7fe3407cbd291`;
- `lastAcceptedAt = 2026-09-16T15:22:05.726Z`;
- `lastDeliveredAt = 2026-09-16T15:35:15.850Z`.

This exposed a real cold-start readiness gap: session-restored tabs can already be complete when the MV3 worker comes up, so relying only on `tabs.onUpdated(status=complete)` is insufficient.

### 0.5.12 cold-start recovery — replay/retention PASSED, immediate live send not claimed

Final task id: `e2e-chrome-restart-final-0512-20260916`.

0.5.12 adds bounded startup reconciliation rather than permanent polling. On browser startup it arms three one-shot reconciliation alarms at approximately 1 s, 3 s and 8 s. Each pass refreshes configured content scripts and re-arms any exact pending event wake. The existing `tabs.onUpdated(status=complete)` path remains as an additional readiness signal.

After loading exact commit `8da2dd576fd2d5e076961886492f59c0164fdbf2`, quitting Chrome, creating the matching synthetic event while Chrome was closed, reopening Chrome and later reading fresh DEBUG, the live state proved:

- extension `0.5.12`;
- protocol `7/7`;
- exact repository/chat/binding retained;
- `currentWatch = null` because the matching event had been accepted;
- `pendingWake.eventId = evt-5a518b7b5f2d3a5d5f5506a33d39ea33`;
- `pendingWake.taskId = e2e-chrome-restart-final-0512-20260916`;
- `lastAcceptedEventId = evt-5a518b7b5f2d3a5d5f5506a33d39ea33`;
- `lastAcceptedTaskId = e2e-chrome-restart-final-0512-20260916`;
- `lastAcceptedAt = 2026-09-16T15:56:27.716Z`;
- Native Messaging connected at `2026-09-16T15:56:27.714Z` and returned to idle with no error;
- `lastStatus = assistant_busy`;
- retry remained scheduled one minute later;
- `lastDeliveredEventId` still referred to the preceding event, so the final restart event had not yet been consumed.

The delivery implementation intentionally treats `assistant_busy` as retryable, retains the durable pending event, and consumes it only after a delivery returns `ok`. Therefore the final live run proves Chrome cold-start outbox replay, exact event acceptance, persisted pending retention and scheduled retry under a busy ChatGPT renderer. It does **not** prove immediate end-to-end ChatGPT injection after Chrome restart, because the renderer reported `assistant_busy` during the observed delivery attempt.

No additional manual browser restart tests were requested after this point; the branch is frozen with this limitation recorded rather than extending operator testing indefinitely.

## What the live tests prove

The operator-Mac gates have direct evidence for:

- real Chrome extension 0.5.12 loaded from exact candidate commit `8da2dd576...`;
- content protocol `7/7` compatibility;
- exact hard binding retained across extension and Chrome restart;
- healthy exact-origin Native Messaging installation;
- real installed macOS Native Messaging transport connecting on demand;
- live ChatGPT delivery confirmation on the current renderer in earlier watch/event and host-restart tests;
- exact watch-before-event routing;
- exact event-before-watch durable replay;
- exact host kill -> durable outbox -> reconnect -> replay -> delivery path;
- Chrome full-restart durable outbox replay and event acceptance on 0.5.12;
- pending event is retained rather than consumed when delivery reports `assistant_busy`;
- scheduled fallback remains configured independently of Native Messaging.

## What these tests do NOT prove

The transport events above were synthetic smoke events created through the production event API with temporary repository binding/control metadata. They did **not** create or inspect a real authoritative `.agent/results/<task-id>.json` result in the bound repository.

Therefore these results must not be described as proving the semantic real-task publication gate. Still-open release evidence includes, where applicable:

- a real Local Agent task whose authoritative result is published before event creation;
- real success/failed/rejected/cancelled terminal statuses;
- deferred publication waking only after successful remote publication;
- multi-minute no-spam behavior with a real task;
- Local Agent restart around publication;
- polling-only fallback with Native Messaging intentionally absent;
- an observed successful immediate ChatGPT send after a full Chrome restart when the renderer is not busy.

The `local-agent` binding used by this conversation is `bridge/operator-only` with execution disabled, so validation intentionally did not create Local Agent project task files merely to manufacture semantic task-result evidence.

## Release/merge constraint

This evidence does not authorize a merge. PR `#77` must remain draft and `main` must remain unchanged until the operator explicitly approves release/merge. A `main` update may trigger Local Agent autoupdate.
