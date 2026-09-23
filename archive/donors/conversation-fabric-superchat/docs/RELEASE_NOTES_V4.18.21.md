# Local Agent 4.18.21

## Summary

Harden Chat Bridge scheduling against stale asynchronous side effects while preserving the known-good branch-neutral conversation binding model from `d2c23951456d1e1528e3c52e47bdd104294cf170`.

A ChatGPT conversation remains hard-bound only to the Local Agent repository identity and binding UUID. Source branch selection remains task-scoped through `work_branch`; changing source branches does not require Rebind.

## Chat Bridge ordering hardening

- Make delayed alarm clears and schedules generation-ordered so an older operation cannot erase or replace a newer `NEXT`, interval change, enable, or reconciliation result.
- Make delayed conversation-status writes generation-aware so stale delivery/error paths cannot overwrite newer control state.
- Protect popup enable/disable/interval scheduling, upsert/rebind bootstrap scheduling, scheduler reconciliation, worker-error retry, and early delivery failure paths with the generation they actually inspected or created.
- Keep confirmed `conversation_exhausted` terminal for the same hard binding even when ordinary pacing changes race with it.
- Reject an exhaustion report that became stale across an explicit Rebind so the old binding cannot mutate the new one. The exhaustion guard may subsequently report the still-exhausted conversation again under the current binding.

## Regression coverage

Deterministic race tests cover:

- exhaustion versus `NEXT` on the same binding;
- exhaustion versus explicit Rebind;
- stale disable cleanup versus newer `NEXT`;
- stale master-off reconciliation versus newer master-on scheduling;
- delayed Rebind bootstrap scheduling versus a newer operator interval change;
- stale asynchronous status versus a newer generation.

The exact candidate also passes the full Local Agent CI matrix, including Chat Bridge validation, unit/integration tests, coverage, Python 3.14, isolated Chromium Bridge smoke, and macOS smoke.

## Compatibility and scope

- Chat Bridge extension advances from `0.5.7` to `0.5.8`.
- Content protocol remains `v6`; this release changes service-worker scheduling semantics, not the content-script protocol contract.
- Task schema, `work_branch`, repository binding, resource scheduling, executor behavior, result schema, and downstream planner contract are unchanged.
- Strict runtime-schema work, compact wake/v4 planner work, and independent content-script revisioning remain explicitly out of scope.
- No downstream repository documentation migration is required for this release.

## Rollout

After `main` advances, the installed Local Agent checkout may self-update through the existing validated fast-forward path. Because the Chat Bridge is an unpacked Chrome extension, the extension must then be reloaded so Chrome starts the `0.5.8` service worker. Existing conversation bindings and state are retained.
