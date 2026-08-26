# Multi-Repository Design (v4.10)

This document defines the production design for running one `local-agent` launchd service against multiple repositories without mixing workspaces or task state.

## Status

The v4.10 multi-repository contract includes:

- repository registry and legacy LiteGraph fallback;
- isolated per-repository workspaces and durable state;
- process-isolated repository workers;
- deterministic round-robin supervisor;
- global execution concurrency of one;
- repository-local status/control semantics;
- explicit provisioning and checkout-origin validation;
- safe creation of a missing `agent-control` branch;
- unit tests plus real temporary-Git integration tests for two repositories;
- isolated macOS staging smoke validation;
- durable result spooling and publication-only recovery;
- bounded worker turns and checkpoint creation;
- strict normalized workspace-path isolation;
- case-insensitive repository-id and remote-identity isolation;
- inherited OS execution leases that survive supervisor or worker failure;
- immutable registry-entry validation at worker dispatch;
- bounded all-process shutdown and real SIGTERM/SIGKILL recovery tests;
- full-scan and supervisor-control deadlines that cannot be starved by hot polling.

## Goals

- One launchd-managed supervisor is the only scheduler.
- Multiple repositories may queue work independently.
- Only one task executes at a time; parallel local execution is intentionally out of scope.
- Every repository has isolated `control`, `work` and `checkpoints` directories.
- Existing LiteGraph deployment remains compatible when no repository registry exists.
- Task/result/claim identity is repository-scoped so the same task id may safely exist in different repositories.
- A broken or unavailable repository must not prevent the supervisor from polling other configured repositories.
- Repository polling never performs implicit cloning or repair.

## Registry

Machine-local configuration lives at:

```text
~/Library/Application Support/local-agent/repositories.json
```

If this file does not exist, the registry resolves to the established LiteGraph layout:

```text
repository:  MichalMatu/esp32s3_LiteGraph
control:     ~/agent-workspace/control
work:        ~/agent-workspace/work
checkpoints: ~/agent-workspace/checkpoints
```

Example multi-repository registry:

```json
{
  "version": 1,
  "repositories": [
    {
      "id": "litegraph",
      "repository": "MichalMatu/esp32s3_LiteGraph",
      "legacy_workspace": true
    },
    {
      "id": "photomaps",
      "repository": "MichalMatu/PhotoMaps"
    },
    {
      "id": "wreckscanner",
      "repository": "MichalMatu/WreckScanner"
    }
  ]
}
```

Default paths for a non-legacy repository are:

```text
~/agent-workspace/repos/<id>/control
~/agent-workspace/repos/<id>/work
~/agent-workspace/repos/<id>/checkpoints
```

The registry is machine-local and must not contain secrets. Repository ids and remote `owner/repository` identities are unique case-insensitively. All normalized workspace paths must be disjoint; equal, symlink-aliased, case-insensitive and ancestor/descendant collisions are rejected before scheduling begins.

## Process-isolated execution model

The architecture uses one long-lived supervisor (`agent_multirepo.py`) and a short-lived repository worker (`agent_repo_worker.py`).

The supervisor:

- owns the global daemon lock, so alternate entry points cannot run concurrently;
- loads/reloads the repository registry;
- polls repositories in deterministic round-robin order;
- starts only one repository worker at a time;
- gives due supervisor control and periodic full scans priority over hot polling;
- passes its PID to the worker for status evidence;
- terminates every registered process group on shutdown with bounded escalation;
- continues to other repositories when one worker fails before processing a task.

The repository worker:

- receives exactly one configured repository id and the immutable digest of the selected registry entry;
- rejects a changed registry entry before binding paths or executing repository work;
- validates that the repository control/work checkouts already exist;
- binds the legacy `agent_core` paths once inside the worker process;
- scopes claims and local run/status state under a repository-specific state directory;
- syncs that repository control branch;
- recovers terminal state for that repository;
- handles safe repository-local control requests;
- executes at most one pending task;
- exits after the poll/dispatch turn.

Binding legacy core path globals is allowed only inside this short-lived isolated worker process. The long-lived supervisor never changes `agent_core.WORK`, `agent_core.CONTROL` or related globals at runtime. This avoids cross-repository races without a high-risk rewrite of the validated execution core.

## Scheduling and multiple ChatGPT conversations

Each registered repository keeps its own `agent-control` branch and `.agent/` queue/results/status files. Separate ChatGPT conversations may therefore plan and queue work for different repositories independently.

Actual local execution remains serialized:

```text
Chat A -> LiteGraph queue -----\
Chat B -> PhotoMaps queue ------> one supervisor -> one worker/task at a time
Chat C -> WreckScanner queue ---/
```

Each periodic full scan starts after the repository that most recently completed a task. A full scan becomes due every 15 seconds and runs before another hot poll; supervisor control has an independent 15-second cadence and runs first when due. These priorities apply between worker turns and never interrupt an already-running stage. A continuously non-empty repository therefore cannot permanently starve another queue or supervisor maintenance.

This model is intentionally conservative for PlatformIO, serial ports, USB devices and other machine-wide resources.

## Repository lifetime leases and crash recovery

Every supervisor repository turn acquires non-blocking `flock` leases under the daemon state directory for five identities: case-folded repository id, case-folded remote identity, and normalized control, work and checkpoint paths. The supervisor passes the open descriptors to the worker, and the shared spawn path passes them to every descendant command. A lease is released only after the last process holding its descriptor exits.

The worker validates both the inherited lease identity and the exact registry-entry digest before it binds repository globals, syncs control state or performs stale-claim recovery. A restarted supervisor that encounters an old live worker or command treats the repository as busy and continues polling other configured repositories. It does not recover the claim, replay the task or mutate that repository.

SIGTERM is handled in the supervisor, worker and legacy daemon. Workers first stop active task work and quiesce asynchronous control-Git publication so a graceful shutdown cannot interrupt its own staged update. Remaining registered process groups receive TERM with bounded escalation to KILL. A signal that arrives inside the process-spawn window is deferred until the child has been registered and is then redelivered. SIGKILL cannot run handlers, so inherited leases provide the recovery boundary until orphaned descendants really exit.

## Isolation requirements

Repository-scoped state:

- control checkout;
- disposable work checkout;
- checkpoints;
- queued tasks and results;
- durable claims and corrupt-claim quarantine;
- local run/progress/status files;
- remote run/progress/result/status files in that repository control branch.

Daemon-wide state:

- process lock;
- local-agent source checkout and release state;
- registered subprocess groups and repository execution-lease files;
- scheduling cursor.

Repository-local `status` control is supported. Worker status contains repository identity, worker PID and, when launched by the supervisor, supervisor PID. Idle status is persisted locally on every poll but remote idle status commits are heartbeat-throttled.

`restart` and `self_update` are deliberately rejected inside repository workers. They are global supervisor maintenance actions; allowing a child worker to execute the restart path could create a second scheduler. Global daemon restart/update is therefore an explicit administrative/launchd operation rather than a repository-local command.

## Checkout provisioning

Provisioning is explicit:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
python agent_repo_admin.py provision --repository-id photomaps
```

`provision` never overwrites an existing non-Git path. Existing Git checkouts must have the configured repository as `origin`.

For a new repository:

- if remote `agent-control` already exists, the control checkout clones that branch directly;
- if it does not exist, provisioning creates a fresh control clone, creates an orphan `agent-control`, adds only the `.agent/` skeleton, commits it and pushes it;
- creation of a new control branch requires an existing Git `user.name` and `user.email` identity;
- the work checkout starts from the configured default branch and remains able to fetch other work branches;
- checkpoint storage is created outside the worktree.

Provisioning never occurs as a side effect of the supervisor poll loop.

## Validation evidence

The automated integration suite creates real temporary bare Git repositories and validates the actual worker/provisioning behavior rather than only mocking it.

The two-repository worker integration test proves that:

- two repositories can use the same task id without claim/result collision;
- each repository executes against its own work checkout;
- results are published to the matching control checkout;
- claims are released independently;
- disposable worktrees remain clean.

The provisioning integration test proves that a repository with only `main` can be provisioned into separate control/work checkouts and receive a newly published `agent-control` skeleton safely.

Crash-recovery integration tests use real process groups, temporary Git repositories and external barriers to prove that supervisor SIGTERM terminates the active command, while supervisor or worker SIGKILL cannot cause overlap, premature stale-claim recovery or automatic replay.

An isolated macOS smoke test checks release candidates from a detached local-agent worktree while production remains running. The worktree must be removed after the test and the production daemon must remain healthy.

## Activation model

The repository contains a launchd template for the supervisor. It intentionally uses the same launchd label and daemon lock as the single-repository service; it is a replacement configuration, never a second service.

Before activation:

```bash
python agent_repo_admin.py validate
python -m unittest discover -q
```

Stop/unload the current service before loading a replacement supervisor configuration. Never run both entry points concurrently even though the OS lock provides a final safety boundary.

Rollback is straightforward: stop the supervisor, restore the previous launchd configuration and start it again. Existing legacy LiteGraph paths are retained and no repository source checkout is migrated in place.

## Release gate

A release candidate is acceptable only when all of the following are true:

1. staging is based on current `main` and has no unrelated changes;
2. compile, Ruff, unit and temporary-Git integration tests, including real SIGTERM/SIGKILL recovery, are green on the exact staging SHA;
3. the exact diff is reviewed;
4. an isolated macOS two-repository smoke test passes on the exact candidate SHA;
5. the smoke worktree is removed and production remains healthy/idle;
6. the repository registry is validated before any activation;
7. `main` is advanced only by validated fast-forward after an explicit release decision.
