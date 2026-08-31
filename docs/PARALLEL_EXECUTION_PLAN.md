# Parallel Execution Staging Plan

This document defines the v4.11 bounded-parallel experiment and records the live validation completed on 2026-08-31. The released `agent_multirepo.py` scheduler remains unchanged and is the known-safe rollback path.

## Safety objective

Parallelism is opt-in. Existing/legacy tasks must not become less safe merely because the parallel supervisor is selected.

Entry points:

- `agent_multirepo.py` — serial supervisor and direct fallback;
- `agent_parallel.py` — bounded parallel supervisor;
- `agent_parallel_worker.py` — resource-arbitrated worker used only by the parallel supervisor.

Both supervisors share the daemon lock and therefore cannot run concurrently.

## Concurrency limits

`agent_parallel.py` accepts `--max-workers N` and `LOCAL_AGENT_MAX_PARALLEL_WORKERS=N`.

- default: `1`;
- staging hard cap: `3`;
- validated live setting: `2`.

The cap is deliberately small because per-task RSS watchdogs are not an aggregate host-memory scheduler.

## Task resource contract

A missing `resources` field means:

```json
{
  "resources": ["machine"]
}
```

and therefore full-machine exclusivity. Malformed or oversized declarations also fall back to `machine`.

Clearly software-only work may opt into overlap:

```json
{
  "resources": [],
  "memory_limit_mb": 512
}
```

Named resources may be used for explicit serialization:

```json
{
  "resources": ["platformio"],
  "memory_limit_mb": 1024
}
```

Non-machine parallel admission requires an enabled memory watchdog and `memory_limit_mb <= 1024`. A disabled, omitted/default 4096 MiB or larger limit falls back to full-machine exclusivity.

For staging, hardware-sensitive, USB, serial, flashing and uncertain work should remain machine-exclusive by omitting `resources` unless a stronger explicit resource contract is known.

## Resource admission and task freshness

Resource acquisition is admission-style and non-blocking. A worker syncs the repository, selects the current pending task and immediately attempts the required locks.

If a lock is busy, the worker exits without claiming or executing the task and the supervisor retries later. This intentionally replaces the rejected prototype behavior that could wait up to an hour before claim and therefore execute a stale local snapshot.

Named-resource contention uses bounded retry and does not block unrelated repositories.

Machine contention enters priority/drain mode: admission of unrelated new workers stops, already-running workers finish and the machine-exclusive repository is retried alone.

One-shot mode retries resource/config/lease deferrals and bounds the number of deferrals so it cannot silently succeed with a pending task or loop forever.

## Lock lifetime

Every admitted parallel task holds a machine lock:

- shared for parallel/named-resource tasks;
- exclusive for `machine` tasks.

Named resources use additional exclusive lock files.

Machine and named resource descriptors are appended to the inherited lease descriptor environment before task commands are spawned. If a worker dies but a descendant command remains alive, that descendant continues to hold both repository and resource locks until it exits.

The arbitration gate is held only for the short lock-acquisition transaction; it is never held while waiting for task completion.

## Global control

Periodic maintenance polling must not destroy useful parallelism.

While workers are active, the supervisor performs only a lightweight control probe. A real unacknowledged global control request causes new admission to stop; current workers drain, then the supervisor acquires every currently configured repository execution identity before handling restart/status/self-update.

Ordinary self-update waits for natural idle. A detached staging checkout intentionally logs:

```text
self-update skipped: checkout is not on main
```

The staging worktree stays pinned to an explicitly validated runtime SHA.

## Silent Git failure diagnostics

The production serial log previously exposed a terminal self-update failure with no text after the colon. Staging now synthesizes a bounded diagnostic whenever terminal Git failure output is empty, including available exit-code, timeout, background-process-leak, failure-reason and elapsed-time metadata.

A failed periodic self-update fetch is non-fatal to repository scheduling.

## Audit corrections completed

The original parallel prototype was not live-test ready. The re-audit corrected:

1. stale pre-claim resource waiting;
2. restart/self-update/status races with active workers;
3. unnecessary worker-pool draining for periodic maintenance;
4. all-current-repository lease acquisition for global control;
5. scheduler exception containment;
6. staging worker cap and 1024 MiB parallel memory admission limit;
7. bounded resource declarations;
8. explicit `parallel-staging` result/status identity;
9. one-shot resource/config/lease retry semantics;
10. explicit compile/Ruff validation of parallel modules;
11. real two-repository overlap integration;
12. real POSIX resource-lock survival after worker exit;
13. process test pipe cleanup with no macOS `ResourceWarning`;
14. actionable diagnostics for silent Git failures.

## CI candidate

Runtime candidate used for live validation:

```text
084e81b792cd01a261a0f0ee1a2a9b46b9964168
```

GitHub Actions run `33407799093` completed successfully for that exact SHA. Linux passed compile, pinned Ruff, Chat Bridge validation and full unittest discovery. macOS passed compile plus process/checkpoint/multi-repository/parallel smoke coverage.

## Real macOS live evidence — 2026-08-31

### Parallel overlap

Two harmless software-only tasks were queued to different repositories with:

```json
{
  "resources": [],
  "memory_limit_mb": 512
}
```

Observed command windows:

```text
growbox-ml-controller  15:27:50.239857Z -> 15:28:10.244669Z
MatrixHub               15:27:52.721723Z -> 15:28:12.726339Z
```

The commands overlapped for approximately 17.5 seconds. Both results were `done`, exit code zero, clean Git status/diff, no timeout and no background-process leak.

### Machine exclusion

A second pair tested conservative fallback:

- Growbox task omitted `resources`, therefore machine-exclusive;
- MatrixHub task used `resources: []`, 512 MiB.

Observed command windows:

```text
machine-exclusive Growbox  15:29:00.440278Z -> 15:29:15.445082Z
software-only MatrixHub    15:29:31.456303Z -> 15:29:46.456119Z
```

Overlap was zero. This proves the live Mac honored full-machine exclusion rather than only the CI/mocked contract.

### Shutdown and persistent activation

After the manual foreground supervisor was stopped with Ctrl-C, no serial supervisor, parallel supervisor or repository worker process remained.

The existing LaunchAgent was then changed to launch the detached staging worktree with `--max-workers 2`. Status reported:

```text
daemon_version: 4.10.2-parallel-staging
self_revision: 084e81b792cd01a261a0f0ee1a2a9b46b9964168
execution_model: parallel_repository_supervisor_staging
max_parallel_workers: 2
active_repository_ids: []
```

The staging stderr log was empty.

The known-good serial plist is preserved at:

```text
~/Library/LaunchAgents/com.michal.local-agent.serial-backup.plist
```

## Current staging policy

- Keep `max_workers=2` for normal staging use.
- Do not move to `3` until additional real workload evidence justifies it.
- Software-only tasks may opt into `resources: []` with an explicit memory limit at or below 1024 MiB.
- Hardware/uncertain tasks remain machine-exclusive.
- Do not mutate/remove active registry identities while workers may exist.
- Do not silently update the detached live worktree to newer staging commits.
- Documentation-only staging commits do not invalidate the validated runtime SHA, but they also do not constitute runtime validation of newer code.

## Rollback

Rollback remains state-compatible:

1. stop `com.michal.local-agent`;
2. restore `com.michal.local-agent.serial-backup.plist` over the active plist;
3. bootstrap/kickstart the same launchd label;
4. verify the serial supervisor startup and one real queued task.

No repository control/work/checkpoint migration is required.

## Release decision

The live staging success does not automatically authorize merging to `main`. A release remains a separate explicit decision. Before release, review the final diff against `main`, ensure only intended code/docs/tests/CI changes remain, require green CI for the release candidate and retain the serial fallback path.
