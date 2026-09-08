# Local Agent 4.18.16

## Summary

Harden Chat Bridge wake pacing, stale-tab recovery, unconfirmed-delivery handling and assistant-control retry behavior. Also make the planner use existing repository-scoped `cancel_task` when exact live evidence proves a long-running task cannot succeed.

## Chat Bridge 0.5.5

- Raise the content-script protocol from 3 to 4 so the worker can distinguish an already-open tab running an older Bridge implementation.
- When preflight finds a reachable but stale content protocol, reinject the current `control_protocol.js`, `content_retry.js` and `content.js`, dispose the old listeners/timers, then probe again instead of requiring a manual ChatGPT tab reload.
- Increase the bounded send-button wait and post-submit DOM-confirmation windows for slow/background tabs.
- Preserve an exact Bridge-owned prompt when `send_button_not_ready` or `delivery_unconfirmed` occurs instead of clearing text that the operator can visibly recover.
- Allow a later Bridge run to reuse that non-empty composer only when the previous status is recoverable and the composer still equals the current Bridge prompt byte-for-byte. Any operator edit blocks automatic reuse.
- Keep `delivery_unconfirmed` diagnostic and non-blocking; this release does not restore the old durable `pendingDelivery` journal or manual resolution gate.
- Replace the content-script assistant-control scanner's fixed three-failure give-up with a pure bounded retry policy: 5, 10, 20, then 30 seconds, capped at 30 seconds without terminal exhaustion. New assistant content resets the backoff.
- Add protocol/injection consistency tests so worker, content script, test harness and manifest load order cannot silently drift apart.

## Planner pacing

- Preserve explicit `[LAB:NEXT=30s]` protocol compatibility for operator/emergency use.
- Remove 30-second cadence from the autonomous healthy-task policy.
- Use no sooner than about two minutes for an early liveness re-check of healthy executor work.
- Use 5-10 minute `NEXT` intervals for ordinary multi-minute builds/tests unless exact evidence supports a nearer completion.
- Add a planner-pacing regression contract so future prompt/documentation changes cannot silently restore 30-second polling as the normal autonomous recommendation.

## Active-task cancellation

- Document and prompt the planner to use the existing repository-scoped `cancel_task` control when exact current run/status evidence already proves that an active task cannot achieve its intended outcome.
- Require cancellation to target the exact active task id and require cancellation/result evidence before queueing a replacement.
- Keep cancellation ownership in the Local Agent repository worker; Chat Bridge remains transport-only and receives no repository write credential.
- Do not add a direct popup cancel button in this release because that would require a separate trusted operator transport.

## Architecture

- Add `chat_bridge/content_retry.js` as a pure retry-policy owner instead of embedding another mini state machine in `content.js`.
- Keep `content.js` responsible for DOM interaction and transport lifecycle only.
- Keep existing executor, hard-binding, resource, worker-concurrency, BUG-002, self-update and repository-control ownership unchanged.

## Regression coverage

The candidate adds or extends coverage for:

- content protocol v4 consistency and dynamic reinjection order;
- stale reachable content-script replacement;
- unbounded-in-attempt-count but bounded-in-delay assistant-control retry;
- retained prompt visibility after unconfirmed delivery;
- operator edit protection after a retained Bridge prompt;
- exact retained-prompt reuse only in recoverable transport states;
- autonomous healthy-task pacing contract;
- continued explicit 30-second protocol compatibility.

The isolated Chromium smoke contains the direct regression assertion:

```text
PASS: unconfirmed Bridge prompt stays visible and any operator edit blocks automatic reuse
```

## Candidate verification before release metadata finalization

Exact functional candidate `f4be7eb7a70f2070096e11fbe049da9fd66684f8` completed GitHub Actions run `34188173871` successfully:

- compile and Ruff;
- Chat Bridge Node syntax/tests;
- full Python unit/integration tests;
- coverage;
- Python 3.14 compatibility;
- macOS ARM64 smoke;
- isolated Chromium extension smoke.

The final release SHA must be re-verified after version/release-metadata changes before merge.

## Compatibility

No task schema, binding UUID, repository registry, `resources`, worker-count, result schema, BUG-002 admission or self-update semantics change. Explicit `NEXT=30s` remains valid protocol. Existing schema-v3 Bridge conversation state remains valid.

## Production state

While this file is on the candidate branch, production remains `v4.18.15` at the previously live-validated release point. `v4.18.16` must not be described as current production until the explicit release decision advances `main` and live runtime verification succeeds.

## Rollback

Before release, the production rollback remains `rollback/v4.18.15-production-validated`. A new 4.18.16 rollback/tag point should be created only after merge and live validation.
