# Local Agent 4.18.15

## Summary

Fix parallel-supervisor self-update starvation caused by a retained repository-owned `cancel_task` control request.

## Changes

- Keep `cancel_task` ownership in repository workers; the global supervisor still does not consume or globally drain for repository-owned cancellation.
- Decouple validated self-update from the `cancel_task` dispatch guard so stale, completed, or rejected cancel control files cannot permanently pin an otherwise clean installed `main` checkout to an older release.
- Add a focused regression that reproduces the 4.18.14 failure (`maybe_self_update()` was never called while `cancel_task` occupied the control slot).
- Include the regression in the explicit macOS smoke profile as well as the full Python, Python 3.14, and coverage suites.

## Compatibility

No task schema, repository-binding, resource-classification, watchdog, result, worker-concurrency, BUG-002 admission-policy, or downstream planner contract changes.

## Live incident evidence

The production 4.18.13 supervisor remained on `a32e54858c3bcb9687334b3232b71ae6ff130208` after `main` advanced because LiteGraph `agent-control` retained `production-audit-a2-cancel-r26-resource-20260906` as `action: cancel_task`. Its ACK already recorded `rejected / task_not_pending`, proving the control request was complete while the retained control slot still suppressed every parallel `maybe_self_update()` call.

## Production validation

- The running 4.18.13 supervisor accepted the explicit self-update control, installed `a00fda47016654c80e6ec4cf4170f49713e82628`, re-executed the guarded entrypoint and came back as Local Agent 4.18.15 with `max_workers=4`.
- A live BUG-002 regression used a long read-only LiteGraph control-repository task with `resources: []`. After the supervisor logged six consecutive control-lease-busy probes and paused only new LiteGraph admission, a read-only Growbox task with `resources: []` started while LiteGraph was still running and finished before the LiteGraph task completed.
- The Growbox task started at `2026-09-08T03:58:34.978296+00:00`; the LiteGraph task completed at `2026-09-08T03:59:07.150692+00:00`, proving real cross-repository overlap after the old starvation threshold.
- An opportunistic runtime-GC push raced a concurrent `agent-control` commit and was correctly rejected by GitHub rather than overwriting the newer ref. The task result had already been published, later GC retries succeeded, and the control branch returned to a normal idle state.
- The final release-freeze documentation pass changes no runtime code; `rollback/v4.18.15-production-validated` preserves the exact runtime-validated merge commit.

## Rollback

`rollback/v4.18.15-production-validated` points to the live runtime-validated 4.18.15 merge commit. The older pre-BUG-002 known-working baseline remains `v4.18.13` / `a32e54858c3bcb9687334b3232b71ae6ff130208` as a deeper historical rollback point.
