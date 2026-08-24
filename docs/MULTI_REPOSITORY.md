# Multi-Repository Design (v4.6 staging)

This document defines the staged design for running one `local-agent` launchd service against multiple repositories without mixing workspaces or task state.

## Goals

- One launchd-managed supervisor remains the only scheduler.
- Multiple repositories may queue work independently.
- Only one task executes at a time in v4.6; parallel execution is intentionally out of scope.
- Every repository has isolated `control`, `work` and `checkpoints` directories.
- Existing LiteGraph deployment remains compatible when no repository registry exists.
- Task/result/claim identity is repository-scoped so the same task id may safely exist in different repositories.
- A broken or unavailable repository must not prevent the supervisor from polling other configured repositories.

## Registry

Machine-local configuration lives at:

```text
~/Library/Application Support/local-agent/repositories.json
```

If this file does not exist, the registry resolves to the current v4.5 LiteGraph layout:

```text
repository: MichalMatu/esp32s3_LiteGraph
control:    ~/agent-workspace/control
work:       ~/agent-workspace/work
checkpoints:~/agent-workspace/checkpoints
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

The registry is machine-local and must not contain secrets.

## Process-isolated execution model

The v4.6 staging architecture uses one long-lived supervisor (`agent_multirepo.py`) and a short-lived repository worker (`agent_repo_worker.py`).

The supervisor:

- owns the existing daemon lock, so v4.5 and v4.6 cannot run concurrently;
- loads/reloads the repository registry;
- polls repositories in deterministic round-robin order;
- starts only one repository worker at a time;
- forwards termination to the active worker process group;
- continues to other repositories when one worker fails before claiming work.

The repository worker:

- receives exactly one configured repository id;
- validates that the repository control/work checkouts already exist;
- binds the legacy v4.5 `agent_core` paths once inside the worker process;
- scopes claims and local run/status state under a repository-specific state directory;
- syncs that repository control branch;
- recovers terminal state for that repository;
- executes at most one pending task;
- exits after the poll/dispatch turn.

Binding the legacy core path globals is allowed only inside this short-lived isolated worker process. The long-lived supervisor never changes `agent_core.WORK`, `agent_core.CONTROL` or related globals at runtime. This avoids cross-repository races without forcing a high-risk rewrite of the validated v4.5 execution core.

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

The following state is repository-scoped:

- control checkout
- disposable work checkout
- checkpoints
- queued tasks and results
- durable claims
- local run/progress files
- remote run/progress/result files in that repository control branch

Daemon-wide state remains global:

- process lock
- local-agent source checkout and release state
- active worker process
- scheduling cursor

Repository ids and workspace paths must be unique. The registry rejects duplicate ids and any path collision between repositories.

## Checkout provisioning

v4.6 staging does not automatically clone a repository during polling. A repository must be provisioned explicitly before it is enabled. This prevents an invalid registry entry from causing unexpected network or filesystem mutation on daemon startup.

Automatic/safe provisioning may be added later as an explicit administrative command, not as an implicit poll-loop side effect.

## Rollout plan

1. Add and test the repository registry parser with v4.5-compatible fallback. **Implemented on staging.**
2. Add process-isolated repository workers. **Implemented on staging.**
3. Add deterministic round-robin supervisor with global concurrency 1. **Implemented on staging.**
4. Add repository-scoped remote daemon control/status semantics where needed.
5. Add safe explicit checkout provisioning/admin tooling.
6. Add multi-repository integration tests using temporary Git repositories.
7. Validate every staging SHA with compile, Ruff and unit tests.
8. Stop the production v4.5 daemon and run an isolated two-repository smoke test.
9. Verify results, claims, checkpoints and failure isolation in both repositories.
10. Only then consider replacing the v4.5 launchd entry point and fast-forwarding `main`.

`main` remains on v4.5 until every rollout step is complete and the two-repository smoke test passes.
