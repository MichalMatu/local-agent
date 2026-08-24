# Multi-Repository Design (v4.6 staging)

This document defines the staged design for running one `local-agent` daemon against multiple repositories without mixing workspaces or task state.

## Goals

- One launchd-managed daemon process remains the only scheduler.
- Multiple repositories may queue work independently.
- Only one task executes at a time in v4.6; parallel execution is intentionally out of scope.
- Every repository has isolated `control`, `work` and `checkpoints` directories.
- Existing LiteGraph deployment remains compatible when no repository registry exists.
- Task/result/claim identity is repository-scoped so the same task id may safely exist in different repositories.
- A broken or unavailable repository must not prevent the daemon from polling other configured repositories.

## Registry

Machine-local configuration lives at:

```text
~/Library/Application Support/local-agent/repositories.json
```

If this file does not exist, the daemon must behave exactly like the v4.5 deployment and use:

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

## Scheduling

Each registered repository keeps its own `agent-control` branch and `.agent/` queue/results/status files. The daemon polls registered repositories in a deterministic round-robin order and executes at most one claimed task at a time.

This allows separate ChatGPT conversations to work with different projects concurrently at the planning/queueing level. The daemon serializes actual local execution, so PlatformIO, serial ports and other machine resources are not accidentally used by two tasks at once.

## Isolation requirements

Repository context must be passed explicitly through execution and publication paths. Do not switch module globals such as `WORK` or `CONTROL` at runtime to select a repository.

The following state is repository-scoped:

- control checkout
- disposable work checkout
- checkpoints
- queued tasks and results
- durable claims
- run/progress files
- daemon control acknowledgements published to that repository

Daemon-wide state remains global:

- process lock
- self-update state
- local daemon health
- active process watchdogs
- scheduling cursor

## Rollout plan

1. Add and test the repository registry parser with v4.5-compatible fallback.
2. Refactor `agent_core` to accept an explicit repository context while preserving legacy defaults.
3. Refactor `RuntimeExecutor` to execute in the selected repository worktree.
4. Refactor daemon queue/status/claim paths to be repository-scoped.
5. Add deterministic round-robin polling with one active task globally.
6. Add multi-repository integration tests using temporary Git repositories.
7. Validate on `v4.6-multirepo-staging` only.
8. Run a two-repository smoke test before considering any fast-forward to `main`.

`main` remains on v4.5 until every step above is green and the multi-repository smoke test passes.
