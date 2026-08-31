# local-agent

[![CI](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml)

Deterministic local execution infrastructure for AI-assisted software development.

A planner decides **what should change** and supplies the exact task. `local-agent` executes it under bounded runtime rules, preserves failure evidence and publishes machine-readable results describing **what actually happened**.

> The planner decides the work. The executor makes the run deterministic, bounded and observable.

**Current release:** `v4.11.0`

## Production execution model

`main` is the runtime/release source. Temporary `v*-staging` branches and detached worktrees are used only to prepare and validate release candidates; after a validated release, production returns to `~/local-agent` on `main` and releases are marked with `vX.Y.Z` tags.

For registered multi-repository operation, the recommended v4.11 supervisor is:

```bash
python agent_parallel.py --max-workers 2
```

`agent_multirepo.py` remains the direct serial fallback with global concurrency exactly one. Both supervisors share the same daemon lock and must never run simultaneously.

The parallel scheduler is conservative by default:

- a task with no `resources` field is `machine`-exclusive;
- malformed or oversized resource declarations also fall back to `machine` exclusivity;
- `resources: []` opts a clearly software-only task into parallel admission;
- named resources serialize tasks that share the same declared resource;
- any non-machine task must have an enabled `memory_limit_mb <= 1024`, otherwise it falls back to `machine` exclusivity;
- hardware, USB, serial, flashing, unknown heavy tooling and other uncertain work should omit `resources` unless an explicit safe arbitration contract exists.

The validated production setting is two workers. The code hard-caps the scheduler at three; increasing beyond two requires separate evidence.

## What it provides

- immutable task digests, durable claims and explicit terminal results;
- command, no-output, whole-task and RSS watchdogs;
- bounded stdout retention and process-group control;
- crash-safe checkpointing and durable result spooling;
- isolated per-repository control/work/checkpoint state;
- inherited repository and machine-resource leases that survive worker death through descendants;
- bounded parallel admission with full-machine fallback;
- Git-backed tasks, runs, results, status and control;
- transient Git-network retry with actionable terminal diagnostics;
- validated fast-forward self-update from a clean `main` checkout;
- macOS `launchd` deployment templates.

## Repository layout

```text
agentd.py                    shared daemon core, claims/results/control/self-update
agent_core.py                deterministic task execution and publication
agent_runtime.py             staged execution, watchdogs and telemetry
agent_process.py             process groups and inherited execution leases
agent_storage.py             bounded control-Git helpers and diagnostics
agent_repository.py          registry and workspace identity
agent_repo_worker.py         isolated repository worker turn
agent_multirepo.py           serial multi-repository fallback
agent_parallel.py            bounded parallel multi-repository supervisor
agent_parallel_worker.py     task resource admission and resource locks
agent_repo_admin.py          registry validation/provisioning
agent_version.py             release-version source of truth
deploy/macos/                launchd templates
docs/                        canonical operational/release documentation
tests/                       unit, process and real temporary-Git integration tests
```

## Runtime limits

| Guard | Default | Maximum |
| --- | ---: | ---: |
| Command timeout | 900 s | 7200 s |
| No-output timeout | 300 s | 3600 s |
| Whole-task budget | 1800 s | 21600 s |
| Process-group RSS | 4096 MiB | 16384 MiB |

Parallel admission has the stricter 1024 MiB per-task limit described above.

## Multi-repository administration

The machine-local registry is:

```text
~/Library/Application Support/local-agent/repositories.json
```

Useful commands:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
python agent_repo_admin.py provision --repository-id <id>
python agent_parallel.py --max-workers 2 --once
```

Each repository keeps its own `agent-control` branch and repository-scoped `.agent/` queue/results/status data. Task IDs may repeat across different repositories without collision. One repository still executes only one claimed task at a time; different repositories may overlap only when resource admission permits it.

## Reliability rules

- interrupted claimed tasks are never silently replayed;
- malformed/oversized task JSON is terminal input evidence;
- final results are durably spooled before remote publication;
- publication recovery may republish evidence but may not rerun commands;
- every subprocess is registered and commands run in process groups;
- successful commands may not leave background descendants;
- stale-claim recovery is blocked while any matching inherited repository lease is alive;
- machine/named resource locks are inherited by descendants so a killed worker cannot prematurely release shared-machine safety;
- global restart/status/self-update waits for a quiescent worker set and all configured repository identities.

## Verification workflow

Structured coding tasks may use:

```json
"workflow_policy": "efficient-verification-v1"
```

Use `work` for implementation checks, `focused` for affected validation and exactly one final `full` verification stage. The daemon validates declared intent but does not infer it from command text or silently deduplicate commands.

Before publishing runtime changes:

```bash
python -m py_compile \
  agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py \
  agent_storage.py agent_repository.py agent_repo_worker.py agent_multirepo.py \
  agent_parallel.py agent_parallel_worker.py agent_repo_admin.py agentctl.py agent_version.py

ruff check \
  agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py \
  agent_storage.py agent_repository.py agent_repo_worker.py agent_multirepo.py \
  agent_parallel.py agent_parallel_worker.py agent_repo_admin.py agentctl.py \
  agent_version.py tests

python -m unittest discover -q
```

Parallel releases additionally require real two-repository overlap, machine-exclusion, inherited-resource-lock and macOS smoke evidence on the exact candidate SHA.

## Release flow

1. Keep `~/local-agent` on `main` as the known production checkout.
2. Prepare non-trivial runtime changes on an isolated `v*-staging` branch/worktree.
3. Require exact-SHA compile, Ruff, full tests and macOS smoke.
4. Audit and update planner-facing Local Agent documentation in every registered downstream repository when the execution/control contract changed.
5. Fast-forward `main` only after every gate is green.
6. Tag the released main commit `vX.Y.Z`.
7. Run the LaunchAgent from `~/local-agent` on `main`, not from the staging worktree.
8. Verify live version/revision and a real queued task.
9. Remove the staging branch/worktree after the release is established.

## Deployment

The production bounded-parallel template is `deploy/macos/com.michal.local-agent.parallel.plist`. It uses the same `com.michal.local-agent` label as the serial templates and is a replacement configuration, never a second service.

Do not start a foreground daemon while the LaunchAgent is running. All entry points share the same OS daemon lock.

## Documentation

Read these in order when changing runtime behavior:

1. `AGENTS.md` — repository invariants and release/downstream-sync rules.
2. `docs/OPERATIONS.md` — queue, task resources, deployment and rollback.
3. `docs/MULTI_REPOSITORY.md` — registry, workers and scheduling model.
4. `docs/GOLDEN_STANDARD.md` — current production invariants.
5. `docs/PARALLEL_EXECUTION_PLAN.md` — v4.11 design/audit/live-validation record.
6. `docs/AUTONOMOUS_CHAT_LOOP.md` — Chat Bridge planner loop.

Historical material under `docs/history/` is non-canonical.
