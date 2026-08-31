# v4.11 Parallel Execution Release Record

This document records the design, audit and live-validation evidence that promoted bounded multi-repository parallelism into the v4.11 release. Current operating instructions are in `OPERATIONS.md`; current invariants are in `GOLDEN_STANDARD.md`.

## Design outcome

v4.11 adds `agent_parallel.py` and `agent_parallel_worker.py` without rewriting the validated serial path. `agent_multirepo.py` remains a direct fallback.

The design preserves one daemon lock, process-isolated repository workers, repository-scoped claims/results/state and inherited repository execution leases.

Parallelism is conservative and planner-declared:

- no `resources` field => full `machine` exclusivity;
- malformed/oversized resources => full exclusivity;
- `resources: []` => software-only overlap candidate;
- named resources => exclusive named lock plus shared machine lock;
- non-machine admission requires enabled `memory_limit_mb <= 1024`;
- production recommendation is `max_workers=2`, hard cap `3`.

## Critical audit findings fixed before live use

The initial prototype was rejected for live testing until these issues were corrected:

1. A worker could wait up to an hour for resources after selecting a task but before claiming it, creating a stale-task snapshot risk. Replaced with immediate/nonblocking resource admission.
2. Global restart/status/self-update could race active workers. Global control now drains tracked workers and acquires every configured repository execution identity.
3. Shared-machine locks could be held while waiting on named resources, causing convoy/starvation. Arbitration now uses a short admission gate and nonblocking locks.
4. Resource waits could occupy worker slots. Busy workers now exit and are retried.
5. Independent RSS watchdogs were not an aggregate host-memory budget. Parallel admission is limited to tasks with <=1024 MiB RSS limits and the scheduler is capped at three workers.
6. Resource lists were unbounded. They are limited to eight normalized names.
7. Supervisor-cycle exceptions could terminate the scheduler. Continuous mode now logs/degrades/retries.
8. One-shot mode could incorrectly treat resource-deferred work as complete or loop on deferrals. Deferrals are retried with a bounded terminal limit.
9. Periodic maintenance could unnecessarily drain active workers. Active periods now use lightweight control probing; ordinary self-update waits for idle.
10. Silent Git failures could produce `self-update fetch failed:` without diagnostics. Terminal Git failures now synthesize bounded exit/timeout/leak diagnostics when Git emits no text.
11. Original tests did not prove real overlap or FD lock lifetime. Real temporary-Git and POSIX process tests were added.

## v4.11.1 operational hardening

The patch release re-audited recovery, operator observability and the global control path after the first production deployment. The following additional findings were fixed before the v4.11.1 release was accepted:

1. A daemon interruption could leave tracked, staged-new or untracked daemon-owned control metadata that blocked the next rebase/pull. Recovery now classifies and restores/cleans exact daemon-owned status/run/result/ack paths while refusing to auto-clean task files or daemon control requests.
2. Successful status/run/result Git plumbing made `tail -f` difficult to read. Routine successful control-plane Git operations are quiet; task boundaries and bounded `IDLE` operator events remain visible, while failure/retry diagnostics are preserved.
3. A local ACK commit created before a failed push could make the old probe treat a remote request as already handled. ACK durability is now checked against the fetched remote `agent-control` branch.
4. A busy control-repository lease or transient ACK/probe failure could be collapsed into the same boolean result as a clean "no request" probe. Because the control poll and idle repository poll both use a 15-second cadence, this could phase-lock and starve a global request. Control probing now returns explicit `CLEAR`, `PENDING` or `DEFERRED`; `DEFERRED` is retried promptly and does not advance the normal control-poll clock.
5. Self-update validation did not explicitly compile the parallel production entrypoints and its 300-second full-test margin was too tight for a loaded Mac. The validator now includes the parallel modules and keeps a bounded 600-second margin.

The v4.11.1 release gate therefore includes exact-SHA Linux CI, macOS smoke, repeated SIGKILL recovery, full local unittest discovery, live control delivery while workers are active, production self-update/restart, readable operator-log verification and the existing real overlap/machine-exclusion checks.

## v4.11.2 planner/documentation alignment

The v4.11.2 patch does not change scheduler, resource, lease or execution behavior. It closes documentation drift found after the v4.11.1 live release: the autonomous Chat Bridge contract now distinguishes per-conversation planner sequencing from global executor concurrency, and the machine-specific bootstrap records the current registry-based three-repository workspace layout plus the production parallel LaunchAgent template. The downstream LiteGraph flow/autopilot documentation is synchronized in the same release gate.

## Automated evidence

The release test surface includes:

- resource normalization/memory fallback unit tests;
- global-control lease tests;
- control-probe tests;
- bounded one-shot deferral tests;
- real two-repository barrier integration proving temporal overlap;
- real full-machine exclusion tests;
- real inherited named-resource FD lifetime after a worker exits while a descendant remains alive;
- explicit compile and Ruff coverage for parallel modules;
- Linux full unittest/integration CI;
- macOS process, checkpoint, multi-repository and parallel smoke CI.

The runtime candidate used for the first live Mac validation was:

```text
084e81b792cd01a261a0f0ee1a2a9b46b9964168
```

Its CI run passed both Linux and macOS gates.

## Real Mac live evidence

The first live test used two registered repositories, `max_workers=2`, `resources: []` and `memory_limit_mb: 512`.

Growbox command interval:

```text
2026-08-31T15:27:50.239857Z -> 15:28:10.244669Z
```

MatrixHub command interval:

```text
2026-08-31T15:27:52.721723Z -> 15:28:12.726339Z
```

They overlapped for roughly 17.5 seconds. Both results were `done`, exit code 0, with clean worktrees and no background-process leak.

A second live test paired a machine-exclusive Growbox task with a software-only MatrixHub task. The machine-exclusive command ended at `15:29:15.445082Z`; the software task did not start until `15:29:31.456303Z`. Observed overlap was zero.

This proved both directions of the resource model on the real deployment: safe software overlap and conservative full-machine serialization.

## Promotion to production

The temporary detached staging LaunchAgent was useful for live validation but is not the desired steady state. Production v4.11 returns to:

```text
checkout: ~/local-agent
branch:   main
version:  4.11.x
scheduler: agent_parallel.py --max-workers 2
```

This restores normal clean-main self-update behavior and keeps `v*-staging` branches as temporary release candidates rather than permanent runtime branches.

`deploy/macos/com.michal.local-agent.parallel.plist` is the production template. `agent_multirepo.py` and the serial LaunchAgent configuration remain the rollback path.

## Remaining intentional limits

- resource declarations are planner contracts; external manually started tools do not participate in Local Agent locks;
- named hardware resources should be introduced conservatively; unknown/hardware-heavy tasks stay machine-exclusive by default;
- the 1024 MiB parallel rule is a conservative admission bound, not a dynamic whole-host memory scheduler;
- a repository completely removed from the registry while an orphaned old worker survives cannot be discovered by an all-current-registry lease sweep, so active registry identities must not be removed/mutated.

## Release hygiene

After v4.11 is verified from `main`, remove obsolete staging worktrees/branches. Future non-trivial scheduler changes repeat the same pattern: create a temporary staging candidate, prove exact-SHA CI/macOS/live evidence as warranted, fast-forward `main`, tag the release, deploy from `main`, then clean the staging branch.
