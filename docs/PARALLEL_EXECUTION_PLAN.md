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

## Concurrency control

`agent_parallel.py` accepts `--max-workers N` and
`LOCAL_AGENT_MAX_PARALLEL_WORKERS=N`.

The default is `1`. The supported staging range is `1..8`. A production trial
should begin with `2`, then move to `3` only after clean smoke evidence.

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

A task that is known not to use shared machine hardware can opt into parallel
execution:

```json
{
  "id": "frontend-tests",
  "resources": []
}
```

Named resources provide finer arbitration:

```json
{
  "id": "esp32-build",
  "resources": ["platformio"]
}
```

```json
{
  "id": "device-flash",
  "resources": ["usb", "serial"]
}
```

Tasks with different named resources may overlap. Tasks sharing a named resource
serialize on that resource. `"machine"` always means full exclusivity.

Malformed resource declarations fall back to `"machine"` rather than weakening
safety.

## Lock lifetime

Every parallel task holds a shared or exclusive machine `flock`. Named resources
use additional exclusive lock files. The machine and named resource descriptors
are appended to the existing inherited lease descriptor environment before task
commands are spawned.

This intentionally keeps resource locks alive in descendant commands if the
worker itself is killed, matching the existing repository-lease crash boundary.

An arbitration gate prevents a stream of new shared tasks from continuously
jumping ahead of a waiting full-machine exclusive task.

## Staging sequence

1. Keep `main` and the running production daemon unchanged.
2. Develop only on `v4.11-parallel-staging`.
3. Require unit/integration CI on the exact staging SHA.
4. Add a real temporary-Git test proving two repositories can execute
   concurrently without state collision.
5. Add a process test proving named/exclusive resource locks survive worker
   failure while a descendant remains alive.
6. Run an isolated macOS smoke with the production daemon stopped only for the
   bounded staging window.
7. First trial: `--max-workers 2`.
8. Second trial: `--max-workers 3`.
9. Do not fast-forward `main` until all release gates are green.

## Rollback

Rollback does not require reverting commits or migrating state:

1. Stop the parallel supervisor.
2. Start the existing `agent_multirepo.py` launchd configuration.
3. Verify the daemon lock, repository registry, status, and one real queued task.

Repository control branches, workspaces, claims, results, checkpoints, and
registry layout are unchanged by this experiment.
