# Multi-Repository Design (v4.6 staging)

This document defines the staged design for running one `local-agent` launchd service against multiple repositories without mixing workspaces or task state.

## Status

The v4.6 multi-repository implementation is feature-complete on `v4.6-multirepo-staging` for its intended first release scope:

- repository registry and legacy LiteGraph fallback;
- isolated per-repository workspaces and durable state;
- process-isolated repository workers;
- deterministic round-robin supervisor;
- global execution concurrency of one;
- repository-local status/control semantics;
- explicit provisioning and checkout-origin validation;
- safe creation of a missing `agent-control` branch;
- unit tests plus real temporary-Git integration tests for two repositories;
- isolated macOS staging smoke validation.

`main` remains the validated v4.5 production daemon until a separate activation/release decision is made.

## Goals

- One launchd-managed supervisor is the only scheduler.
- Multiple repositories may queue work independently.
- Only one task executes at a time in v4.6; parallel local execution is intentionally out of scope.
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

If this file does not exist, the registry resolves to the current v4.5 LiteGraph layout:

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

The registry is machine-local and must not contain secrets. Repository ids and all workspace paths must be unique; collisions are rejected before scheduling begins.

## Process-isolated execution model

The v4.6 architecture uses one long-lived supervisor (`agent_multirepo.py`) and a short-lived repository worker (`agent_repo_worker.py`).

The supervisor:

- owns the same daemon lock as v4.5, so v4.5 and v4.6 cannot run concurrently;
- loads/reloads the repository registry;
- polls repositories in deterministic round-robin order;
- starts only one repository worker at a time;
- passes its PID to the worker for status evidence;
- forwards termination to the active worker process group;
- continues to other repositories when one worker fails before processing a task.

The repository worker:

- receives exactly one configured repository id;
- validates that the repository control/work checkouts already exist;
- binds the legacy v4.5 `agent_core` paths once inside the worker process;
- scopes claims and local run/status state under a repository-specific state directory;
- syncs that repository control branch;
- recovers terminal state for that repository;
- handles safe repository-local control requests;
- executes at most one pending task;
- exits after the poll/dispatch turn.

Binding legacy core path globals is allowed only inside this short-lived isolated worker process. The long-lived supervisor never changes `agent_core.WORK`, `agent_core.CONTROL` or related globals at runtime. This avoids cross-repository races without a high-risk rewrite of the validated v4.5 execution core.

## Scheduling and multiple ChatGPT conversations

Each registered repository keeps its own `agent-control` branch and `.agent/` queue/results/status files. Separate ChatGPT conversations may therefore plan and queue work for different repositories independently.

Actual local execution remains serialized:

```text
Chat A -> LiteGraph queue -----\
Chat B -> PhotoMaps queue ------> one v4.6 supervisor -> one worker/task at a time
Chat C -> WreckScanner queue ---/
```

After one repository completes a task, the scheduler starts the next scan after that repository in registry order. This prevents a repository with a large queue from permanently starving another repository.

This model is intentionally conservative for PlatformIO, serial ports, USB devices and other machine-wide resources.

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
- active worker process;
- scheduling cursor.

Repository-local `status` control is supported. Worker status contains repository identity, worker PID and, when launched by the supervisor, supervisor PID. Idle status is persisted locally on every poll but remote idle status commits are heartbeat-throttled.

`restart` and `self_update` are deliberately rejected inside repository workers. They are global supervisor maintenance actions; allowing a child worker to execute the legacy v4.5 restart path could create a second scheduler. v4.6 first-release operation therefore treats global daemon restart/update as an explicit administrative/launchd operation rather than a repository-local command.

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

An isolated macOS smoke test also checked the staging implementation from a detached local-agent worktree while production v4.5 remained running. The worktree was removed after the test and the production daemon returned to idle.

## Activation model

The repository contains a separate launchd template for the v4.6 supervisor. It intentionally uses the same launchd label as the v4.5 service and the same daemon lock; it is a replacement configuration, never a second service to load alongside v4.5.

Before activation:

```bash
python agent_repo_admin.py validate
python -m unittest discover -q
```

Then stop/unload the v4.5 service before loading the v4.6 supervisor configuration. Never run both entry points concurrently even though the OS lock provides a final safety boundary.

Rollback is straightforward: stop the v4.6 supervisor, restore the v4.5 launchd configuration and start it again. Existing legacy LiteGraph paths are retained and no repository source checkout is migrated in place.

## Release gate

A v4.6 release candidate is acceptable only when all of the following are true:

1. staging is based on current `main` and has no unrelated changes;
2. compile, Ruff, unit and temporary-Git integration tests are green on the exact staging SHA;
3. the exact diff is reviewed;
4. an isolated macOS two-repository smoke test passes on the exact candidate SHA;
5. the smoke worktree is removed and production v4.5 remains healthy/idle;
6. the repository registry is validated before any activation;
7. `main` is advanced only by validated fast-forward after an explicit release decision.

Until that release decision, `main` and the production launchd service remain on v4.5.
