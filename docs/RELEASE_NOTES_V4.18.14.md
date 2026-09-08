# Local Agent 4.18.14

## Preserve parallel admission during control-repository work

This release fixes BUG-002 in the bounded-parallel supervisor without weakening global-control or resource safety.

When the designated control repository is itself running a task, its worker legitimately owns that repository's execution lease. A periodic supervisor control probe therefore receives `LEASE_BUSY`. The frozen v4.18.13 scheduler could turn repeated expected ownership into a global admission drain and unnecessarily block unrelated `resources: []` repositories.

v4.18.14 separates control-probe retry state from the admission decision:

- `DEFERRED` probe failures keep bounded retry/backoff but reset the **consecutive lease-busy streak**;
- fewer than six consecutive `LEASE_BUSY` outcomes simply retry;
- six consecutive `LEASE_BUSY` outcomes while the control repository is a known active worker pause only **new control-repository admission**; unrelated repositories may continue using free worker capacity;
- once the active control worker releases its repository lease, the supervisor can probe global control before admitting another control-repository task;
- six consecutive `LEASE_BUSY` outcomes with no corresponding known active control worker retain the defensive global drain for unexplained/stale lease ownership;
- a confirmed `PENDING` global control request still stops new admission and drains active workers immediately;
- `resources: ["machine"]`, named-resource exclusion, repository leases, claims, result durability, hard binding, watchdogs and emergency-disable semantics are unchanged.

## Architecture and ownership

Control-probe retry/admission state now belongs to `local_agent.supervisor.scheduling`, alongside the existing pure bounded scheduling policy. The module exposes explicit `RETRY`, `PAUSE_CONTROL_REPOSITORY` and `DRAIN_ALL` policy outcomes. `local_agent.supervisor.orchestrator` remains the side-effect coordinator: it probes Git/control state, starts or drains workers and publishes/logs resulting state.

This avoids embedding another state machine in the already substantial orchestrator and keeps retry math/admission classification deterministic and directly unit-testable.

The configured control-repository identity is part of the policy state. If registry ordering changes that identity, stale retry, lease-busy and pause evidence is discarded and the normal control-poll clock is invalidated so the new control source is checked promptly.

## Regression coverage

The release adds focused policy tests for:

- five consecutive lease-busy outcomes remaining retry-only;
- the sixth known-worker lease-busy outcome pausing only control-repository admission;
- the sixth unexplained lease-busy outcome requiring defensive global drain;
- a degraded `DEFERRED` probe breaking the consecutive lease-busy streak without losing bounded retry behavior;
- control-repository identity changes clearing stale pause/retry evidence;
- successful control recovery clearing all deferral evidence.

A real temporary-Git integration test keeps the control repository task alive, crosses the six-`LEASE_BUSY` threshold, queues a second independent `resources: []` repository only afterwards, and requires that second task to start **before** the control task is released. The test also verifies the explicit pause log and rejects the global-drain path.

Both the pure policy test and the real overlap regression are part of the macOS smoke profile.

## Documentation and release hardening

Current operational documentation is synchronized to production `max_workers=4` and the finalized control-admission semantics. A regression test now rejects obsolete `--max-workers 2` commands and obsolete three-worker-cap claims in the canonical current operational documents.

Release metadata is also checked automatically: `local_agent.version.RELEASE_VERSION` must have matching `docs/RELEASE_NOTES_V<version>.md` and `docs/CHANGELOG.md` entries before the suite can pass.

## Rollback

The immutable pre-fix rollback target remains:

```text
v4.18.13
= a32e54858c3bcb9687334b3232b71ae6ff130208
= rollback/v4.18.13-known-working
```

Do not advance production `main` until the exact v4.18.14 candidate SHA has passed the full Linux/coverage/Python/Bridge matrix, the macOS smoke including BUG-002 coverage, downstream documentation audit, and final exact-diff review. Production restart remains an explicit post-merge operation during a safe idle window.
