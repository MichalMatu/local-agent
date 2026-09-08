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

## Rollback

The pre-BUG-002 known-working baseline remains `v4.18.13` / `a32e54858c3bcb9687334b3232b71ae6ff130208`. Release 4.18.14 remains the validated BUG-002 scheduler fix and is the direct parent release for 4.18.15.
