# Parallel Execution Staging Plan

This document defines the staged v4.11 experiment for bounded parallel repository
execution. The current `agent_multirepo.py` scheduler remains unchanged and is the
known-safe rollback path.

## Safety objective

The existing production model serializes all repository execution with global
concurrency one. v4.11 must preserve that behavior unless parallel execution is
explicitly selected.

The staging design therefore uses separate entry points:

- `agent_multirepo.py` — unchanged serial supervisor and production fallback.
- `agent_parallel.py` — opt-in parallel supervisor.
- `agent_parallel_worker.py` — resource-arbitrated worker used only by the
  parallel supervisor.

Both supervisors use the same daemon lock, so they cannot run at the same time.
The parallel entry point identifies itself as a `parallel-staging` executor in
status/result evidence and must not be treated as the released serial runtime.

## Concurrency control

`agent_parallel.py` accepts `--max-workers N` and
`LOCAL_AGENT_MAX_PARALLEL_WORKERS=N`.

The default is `1`. Staging is deliberately capped at `3`; the previous prototype
limit of eight was rejected during audit because per-task RSS watchdogs do not
form an aggregate host-memory budget. A live trial must begin with `2`.

Global supervisor control is a quiescent operation. Once supervisor control is
due, the scheduler stops admitting new workers, waits for tracked workers to
finish, and acquires the execution identities of every configured repository
before running status/restart/self-update work. This preserves the serial rule
that global maintenance occurs between worker turns and also detects surviving
workers from a previous supervisor process when their repository is still in the
registry.

## Task resource contract

Parallel execution is conservative by default:

```json
{
  "id": "legacy-task"
}
```

A task with no `resources` field receives the implicit resource:

```json
["machine"]
```

and therefore runs exclusively against every other task. Existing tasks keep
their previous machine-wide safety semantics.

A task known not to use shared machine hardware can opt into parallel execution,
but staging additionally requires a bounded per-task RSS limit no greater than
1536 MiB:

```json
{
  "id": "frontend-tests",
  "resources": [],
  "memory_limit_mb": 1024
}
```

If the memory watchdog is disabled, omitted at its normal 4096 MiB default, or
configured above the staging parallel limit, the task falls back to
`["machine"]`. This keeps opt-in parallel work from consuming the whole host
memory budget through several independent 4096 MiB limits.

Named resources provide finer arbitration:

```json
{
  "id": "software-build",
  "resources": ["platformio"],
  "memory_limit_mb": 1024
}
```

```json
{
  "id": "device-flash",
  "resources": ["usb", "serial"],
  "memory_limit_mb": 1024
}
```

Tasks with different named resources may overlap. Tasks sharing a named resource
serialize on that resource. `"machine"` always means full exclusivity. Resource
lists are bounded to eight names. Malformed or oversized resource declarations
fall back to `"machine"` rather than weakening safety.

For the first live staging trial, named hardware resources are not required. Use
`resources: []` only for clearly software-only tasks and leave hardware or
uncertain tasks without `resources`, which keeps them machine-exclusive.

## Resource admission and task freshness

Resource arbitration is admission-style and non-blocking. A worker first syncs
its repository and selects the current pending task, then attempts the required
machine/resource locks immediately. If a lock is busy, the worker exits without
claiming or executing the task and the supervisor retries later.

This replaces the original 3600-second pre-claim wait. Long waiting before the
durable claim was rejected during audit because the selected task could become a
stale local snapshot while waiting for a resource.

When a worker reports machine exclusion contention, the supervisor enters a
priority/drain mode: it stops admitting unrelated workers, lets already-running
workers finish, then retries the blocked repository alone. Named-resource
contention uses ordinary bounded retry and does not block unrelated repositories.

## Lock lifetime

Every admitted parallel task holds a shared or exclusive machine `flock`. Named
resources use additional exclusive lock files. The machine and named resource
descriptors are appended to the existing inherited lease descriptor environment
before task commands are spawned.

This intentionally keeps resource locks alive in descendant commands if the
worker itself is killed, matching the existing repository-lease crash boundary.
The process test suite must prove this with a real descendant process rather than
only mocks.

The arbitration gate serializes the very short lock-admission transaction; it is
never held while waiting for another task to finish.

## Audit findings addressed before live use

The first prototype was not considered live-test ready. The re-audit required the
following corrections:

1. Remove the one-hour unclaimed resource wait and stale-task window.
2. Prevent restart/self-update/status maintenance from racing active workers.
3. Make global control acquire all configured repository execution identities.
4. Add scheduler exception containment so a transient registry/spawn failure does
   not unnecessarily kill the supervisor.
5. Cap staging concurrency at three and gate parallel tasks by a conservative RSS
   limit.
6. Bound resource declarations.
7. Mark parallel result evidence as `parallel-staging` instead of presenting the
   experiment as the released serial executor.
8. Compile and lint the new modules explicitly in CI.
9. Add a real two-repository overlap test.
10. Add real POSIX process tests for machine exclusion and lock-FD survival after
    the worker process exits.

## Remaining limits

- Resource names are a planner contract, not automatic command inspection. A task
  that incorrectly declares itself software-only can still collide with external
  hardware use. Unknown tasks must therefore remain machine-exclusive.
- The locks coordinate local-agent workers only; manually started external tools
  do not participate in the lock protocol.
- The parallel memory rule is a conservative staging bound, not a full dynamic
  host-memory scheduler.
- A repository removed from the registry while an orphaned worker from a previous
  supervisor still exists is outside the all-current-repositories control lease
  check. Do not edit/remove active registry entries during staging execution.
- Concurrent worker logs can interleave in the shared launchd output. Durable
  per-repository run/result evidence remains the source of truth.

## Staging sequence

1. Keep `main` and the running production daemon unchanged.
2. Develop only on `v4.11-parallel-staging`.
3. Require compile, Ruff, unit/integration and macOS CI on the exact staging SHA.
4. Require the real two-repository overlap test to pass.
5. Require the process test proving resource locks survive worker exit while an
   inherited descendant remains alive.
6. Review the exact diff against `main` after every safety correction.
7. Only then run an isolated macOS staging smoke with production stopped for the
   bounded test window.
8. First live trial: `--max-workers 2`, software-only parallel tasks with explicit
   bounded `memory_limit_mb`; hardware/uncertain tasks stay machine-exclusive.
9. Move to `--max-workers 3` only after clean evidence from the two-worker trial.
10. Do not fast-forward `main` until all normal release gates and the parallel
    staging gates are green.

## Rollback

Rollback does not require reverting commits or migrating state:

1. Stop the parallel supervisor.
2. Start the existing `agent_multirepo.py` launchd configuration.
3. Verify the daemon lock, repository registry, status, and one real queued task.

Repository control branches, workspaces, claims, results, checkpoints, and
registry layout are unchanged by this experiment.
