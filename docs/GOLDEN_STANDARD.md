# Local Agent Golden Standard v4.11 staging

This file records the current invariants for `MichalMatu/local-agent`. Operational workflow lives in `OPERATIONS.md`; multi-repository architecture lives in `MULTI_REPOSITORY.md`; parallel staging details and live evidence live in `PARALLEL_EXECUTION_PLAN.md`.

## Core execution and recovery invariants

- The daemon is a deterministic executor, not a coding model.
- Machine-generated execution content is English-only.
- Exactly one daemon/supervisor instance may own the global daemon lock.
- Every task has an immutable payload digest and one durable attempt claim.
- Interrupted tasks are never automatically replayed.
- Malformed or oversized task JSON is terminal `invalid_task_file`.
- Command/no-output/task/RSS limits are bounded and validated.
- The whole-task limit is an admission budget; an already-running stage is not killed solely because the global budget elapsed.
- Command stdout transport and retained output are strictly bounded.
- Runtime commands use process groups. Residual descendants are terminated and reported as `background_process_leak`.
- Every subprocess is registered atomically with shutdown.
- Graceful shutdown quiesces asynchronous control-Git publication before terminating remaining process groups.
- Final results are durably spooled before remote publication.
- Publication failure retains the claim/spool and recovery republishes without re-executing commands.
- Self-update requires a clean `main`, accepts only safe fast-forward installation and validates before restart.
- A detached staging checkout intentionally does not self-update.

## Workspace invariants

- Dirty tracked and untracked work is checkpointed outside the worktree before destructive cleanup.
- Checkpointing runs on every task exit that reaches finalization.
- Checkpoint creation is bounded by time, file count, bytes and free-space checks.
- Checkpoint failure prevents destructive cleanup.
- Cleanup failure is terminal evidence.
- Ignored build caches are preserved by normal cleanup.

## Repository isolation invariants

- Repository ids and remote identities are unique case-insensitively.
- Normalized control/work/checkpoint paths are disjoint; equal, aliased, case-insensitive and ancestor/descendant overlaps are rejected.
- Every repository turn owns inherited OS execution leases for repository id, remote and workspace identities until the last descendant exits.
- Lease contention defers polling and stale-claim recovery without mutating repository state.
- Workers validate the immutable digest of the exact selected registry entry before binding/execution.
- Claims, result spools, corrupt claims, runs and status are repository-scoped.
- Repository path globals are bound only inside short-lived worker processes.
- One repository failure does not kill scheduling for unrelated repositories.
- Polling never implicitly clones, repairs or overwrites a checkout.
- Provisioning is explicit and validates repository identity.
- Repository workers reject supervisor-wide restart/self-update actions.

## Scheduler invariants

### Serial fallback

- `agent_multirepo.py` remains the known-good direct fallback.
- Serial global execution concurrency is exactly one.
- Periodic full scans and supervisor control cannot be permanently starved by a hot repository.
- Existing task payloads require no resource metadata.

### Parallel staging

- `agent_parallel.py` is opt-in and shares the same global daemon lock with the serial supervisor.
- Default worker count is one; staging hard cap is three; validated live setting is two.
- Missing, malformed or oversized `resources` means full-machine exclusivity.
- `resources=[]` is an explicit software-only opt-in.
- Named resources are exclusive within their resource name.
- Non-machine parallel admission requires an enabled RSS watchdog and `memory_limit_mb <= 1024`.
- Machine/resource acquisition is non-blocking and happens before task claim/execution.
- A resource-busy worker exits without claiming the selected task, preventing stale pre-claim snapshots.
- Full-machine contention uses priority/drain scheduling to avoid starvation.
- Named-resource contention uses bounded retry while unrelated repositories may continue.
- One-shot contention/config/lease deferrals are bounded and retried rather than silently considered complete.
- Machine and named resource descriptors are inherited into command descendants and remain the safety boundary after worker failure.
- Normal maintenance polling must not drain active workers. Global control runs only after a real request or natural idle, with all current repository identities acquired.
- Active registry identities must not be removed while staging descendants may still exist.

## Resource planning invariant

Resource metadata is a planner contract, not command inspection. The executor does not infer whether a command is safe for parallel execution.

Therefore:

- software-only tasks may use `resources: []` with an explicit low memory limit;
- explicitly shared tools may use named resources;
- hardware-sensitive, USB, serial, flashing or uncertain work remains `machine`-exclusive by omission unless a stronger explicit arbitration contract exists.

## Git diagnostics invariant

A terminal Git failure must never produce an empty operational error line. If Git emits no text, the storage layer synthesizes a bounded diagnostic containing the exit code and available timeout, background-process-leak, failure-reason and elapsed-time metadata.

## Validated staging evidence

Runtime candidate:

```text
084e81b792cd01a261a0f0ee1a2a9b46b9964168
```

Before live use this SHA passed Linux compile/Ruff/full unit-integration CI and macOS compile/process/integration smoke.

Real macOS validation on 2026-08-31 proved:

- two software-only tasks in different repositories overlapped for about 17.5 seconds;
- both returned `done`, exit code zero, clean worktrees and no background-process leaks;
- a task without `resources` ran full-machine exclusive and had zero overlap with a software-only task in another repository;
- claims were released correctly;
- manual supervisor shutdown left no agent worker/descendant processes;
- the LaunchAgent then ran the same detached runtime SHA with `max_workers=2`, `execution_model=parallel_repository_supervisor_staging` and an empty error log.

The serial plist remains preserved separately for direct rollback.

## Required release gate

For non-trivial daemon changes:

1. stage from current `main` on an isolated `v*-staging` branch;
2. pass compile and pinned Ruff validation for release modules and tests;
3. pass focused coverage and full unittest discovery;
4. pass real temporary-Git and SIGTERM/SIGKILL process tests where relevant;
5. review the exact diff;
6. require green GitHub CI on the exact runtime candidate SHA;
7. for parallel changes, pass real overlap, exclusivity, contention and inherited-resource-lock tests;
8. pass isolated macOS live smoke on the exact candidate SHA;
9. confirm direct serial rollback remains intact;
10. fast-forward `main` only after a separate explicit release decision.

Documentation-only commits may advance the staging branch after a validated runtime SHA, but must not be used as evidence that newer runtime code was live-tested. A running detached worktree remains pinned until a new runtime candidate passes the full gate.
