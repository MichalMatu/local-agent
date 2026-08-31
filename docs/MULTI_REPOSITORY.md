# Multi-Repository Design (v4.11 staging)

This document defines the current multi-repository architecture for `local-agent`. The released serial scheduler remains the fallback; v4.11 adds an opt-in bounded parallel scheduler with explicit machine-resource arbitration.

## Status

The shared multi-repository contract includes:

- machine-local repository registry with legacy LiteGraph fallback;
- isolated control/work/checkpoint paths and repository-scoped durable state;
- short-lived process-isolated repository workers;
- inherited OS repository leases that survive supervisor/worker failure through descendants;
- immutable registry-entry validation at worker dispatch;
- explicit provisioning and origin validation;
- durable result spooling and publication-only recovery;
- bounded worker turns and recoverable workspace checkpoints;
- strict normalized path, repository-id and remote-identity isolation;
- real temporary-Git integration plus SIGTERM/SIGKILL process tests.

Two scheduler entry points now exist:

- `agent_multirepo.py`: released serial fallback, global concurrency exactly one;
- `agent_parallel.py`: opt-in v4.11 staging scheduler with bounded worker slots and resource arbitration.

Both use the same daemon lock, registry, task format, repository workers/state layout and rollback-compatible control branches.

## Goals

- One launchd-managed supervisor is the only scheduler at a time.
- Multiple repositories may queue work independently.
- The serial path remains unchanged and directly recoverable.
- Parallel execution is explicit and conservative rather than inferred from command text.
- Existing tasks without a resource declaration preserve machine-wide exclusivity.
- Every repository keeps isolated control/work/checkpoint state.
- Task/result/claim identity is repository-scoped.
- A broken, busy or unavailable repository must not prevent unrelated repositories from making progress.
- Repository polling never performs implicit cloning or repair.

## Registry

Machine-local configuration:

```text
~/Library/Application Support/local-agent/repositories.json
```

If absent, the registry resolves to the established LiteGraph layout:

```text
repository:  MichalMatu/esp32s3_LiteGraph
control:     ~/agent-workspace/control
work:        ~/agent-workspace/work
checkpoints: ~/agent-workspace/checkpoints
```

Non-legacy defaults:

```text
~/agent-workspace/repos/<id>/control
~/agent-workspace/repos/<id>/work
~/agent-workspace/repos/<id>/checkpoints
```

Repository ids and remote `owner/repository` identities are unique case-insensitively. All normalized workspace paths must be disjoint; equal, symlink-aliased, case-insensitive and ancestor/descendant collisions are rejected before scheduling begins.

Do not remove or identity-mutate active registry entries while a staging worker or descendant may still exist. Global-control arbitration can only acquire identities for repositories still present in the current registry.

## Process isolation

The long-lived supervisor never mutates legacy repository path globals. Every repository turn runs in a short-lived worker process that:

- receives one repository id and the immutable digest of the selected registry entry;
- validates inherited repository leases and the exact registry digest;
- validates control/work checkouts;
- binds legacy core globals only inside the worker process;
- scopes claims, run/status state and result spools to that repository;
- syncs the repository control branch;
- performs safe stale-state recovery;
- executes at most one pending task;
- exits after the turn.

This preserves the validated execution core while preventing cross-repository path races.

## Serial scheduler

`agent_multirepo.py` remains the known-safe fallback:

- deterministic repository ordering;
- one worker/task at a time;
- independent full-scan and supervisor-control deadlines;
- no hardware/resource declarations required;
- direct compatibility with all existing task payloads.

The serial path is intentionally conservative for PlatformIO, USB, serial ports and other machine-wide resources.

## Parallel scheduler

`agent_parallel.py` is opt-in staging behavior:

- default `max_workers=1`;
- staging hard cap `max_workers=3`;
- first validated live setting `max_workers=2`;
- separate `agent_parallel_worker.py` performs resource admission before task claim/execution;
- repository worker processes remain isolated and short-lived;
- machine-wide and named resource locks are real POSIX `flock` descriptors inherited into task descendants.

### Resource contract

No `resources` field means conservative full-machine exclusivity:

```json
{
  "resources": ["machine"]
}
```

Malformed or oversized resource declarations also fall back to `machine`.

Clearly software-only tasks may opt into overlap:

```json
{
  "resources": [],
  "memory_limit_mb": 512
}
```

Named resources allow explicit serialization:

```json
{
  "resources": ["platformio"],
  "memory_limit_mb": 1024
}
```

Resource lists are bounded. `"machine"` always means full exclusivity. Tasks sharing a named resource serialize; tasks with different named resources may overlap.

Parallel/named-resource execution is admitted only when the RSS watchdog is enabled and `memory_limit_mb <= 1024`. Otherwise the task falls back to machine exclusivity. This is a staging aggregate-memory guard, not a full host memory scheduler.

The planner contract is authoritative: the daemon does not inspect shell commands to infer hardware use. Unknown, USB, serial, flashing and other machine-sensitive work therefore stays machine-exclusive by default.

## Admission, freshness and fairness

A parallel worker first syncs control state and selects the current pending task, then attempts its required locks immediately.

Lock acquisition is non-blocking. If a resource is unavailable, the worker exits without claiming or executing the task and the supervisor retries later. There is no long pre-claim wait, preventing a selected task from becoming a stale local snapshot while blocked on a resource.

Named-resource contention uses bounded retry while unrelated repositories may continue.

Machine contention uses priority/drain mode: once a repository reports that it needs full-machine exclusivity, the supervisor stops admitting unrelated new work, lets already-running workers finish and retries the blocked repository alone. This prevents starvation behind an endless stream of shared-machine tasks.

One-shot mode tracks resource/config/lease deferrals and retries them instead of treating a deferred repository as complete. Deferrals are bounded so `--once` cannot loop forever on a persistent external lock.

## Repository and resource lease lifetime

Every repository turn acquires non-blocking execution leases for stable repository identities. The supervisor passes those descriptors to the worker and the shared spawn path passes them to descendants.

Parallel tasks additionally hold:

- a shared machine lock for parallel/named-resource tasks;
- an exclusive machine lock for full-machine tasks;
- exclusive named resource locks when requested.

The resource descriptors are appended to the same inherited descriptor environment. If the worker dies but a task descendant remains alive, the descendant keeps the resource/repository locks until it exits. A restarted supervisor therefore cannot overlap new work with an orphaned command merely because the worker process disappeared.

## Global control and maintenance

Repository workers never execute supervisor-wide restart/self-update actions.

While parallel workers are active, normal supervisor maintenance polling only probes the control repository. It does not drain the worker pool just because a maintenance interval elapsed.

When a real unacknowledged global control request is detected, admission stops. Existing workers finish, then global control acquires the execution identities of every currently configured repository before handling the request.

Ordinary self-update waits for natural idle. A detached staging checkout intentionally reports `self-update skipped: checkout is not on main`; staging is pinned until an explicit runtime update is validated.

## Failure containment

- repository lease contention is a normal deferral;
- worker spawn/config/resource failures do not kill the long-lived scheduler;
- scheduler-cycle exceptions are logged and retried in continuous mode;
- result publication failure retains the durable spool and claim without command replay;
- SIGTERM stops active work and registered process groups with bounded escalation;
- SIGKILL relies on inherited repository/resource descriptors as the crash boundary.

## Provisioning

Provision explicitly:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
python agent_repo_admin.py provision --repository-id <id>
```

Provisioning never overwrites an existing non-Git path. Existing Git checkouts must match the configured origin. A missing `agent-control` branch may be initialized only by explicit provisioning. Provisioning never occurs as a supervisor side effect.

## Validation evidence

Automated validation includes:

- full unit discovery on Linux;
- macOS process/integration smoke;
- two real temporary-Git repositories executing concurrently;
- a barrier test that fails if the two software-only tasks do not overlap;
- real POSIX proof that a resource lock remains held by an inherited descendant after its worker exits;
- full-machine exclusion versus a shared-machine holder;
- bounded one-shot contention behavior;
- repository/control lease coverage.

The exact runtime candidate `084e81b792cd01a261a0f0ee1a2a9b46b9964168` passed CI and then passed real macOS live validation on 2026-08-31:

- two `resources: []`, 512 MiB tasks in different repositories overlapped for about 17.5 seconds and both completed successfully;
- a legacy task with no `resources` field had zero overlap with a software-only task in another repository;
- worktrees remained clean, claims were released and no worker/descendant remained after the manual supervisor was stopped.

The same runtime candidate was subsequently activated through the existing launchd label with `max_workers=2` and a separate serial plist backup retained for rollback.

## Activation and rollback

Serial and parallel entry points are replacement configurations, never two services. They share `com.michal.local-agent` and the daemon lock.

Current staging LaunchAgent points to the detached staging worktree and logs to `local-agent-parallel-staging*.log`. The known-good serial plist is retained as:

```text
~/Library/LaunchAgents/com.michal.local-agent.serial-backup.plist
```

Rollback is stop staging, restore that plist to `com.michal.local-agent.plist`, bootstrap/kickstart the service and verify one real serial task. No repository control/work/checkpoint migration is required.

## Release gate

A parallel release candidate is acceptable only when:

1. staging is based on current `main` and contains no unrelated runtime changes;
2. compile, pinned Ruff, full unittest discovery and temporary-Git integration are green;
3. real process/lease/resource-lock tests are green;
4. exact diff review is complete;
5. GitHub CI is green on the exact runtime candidate SHA;
6. real macOS overlap and machine-exclusion smoke passes on that exact SHA;
7. rollback remains direct and serial `agent_multirepo.py` remains intact;
8. `main` advances only after a separate explicit release decision.
