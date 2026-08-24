# local-agent

[![CI](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml)

Deterministic local execution daemon used for real development work. ChatGPT or another planner decides the exact change and commands; `local-agent` executes them on the local machine and publishes machine-readable evidence.

> The planner decides what to do. The daemon executes the deterministic task and reports what actually happened.

## Repository role

This repository is execution infrastructure, not the product repository and not a coding model.

The validated production baseline on `main` is daemon v4.5.x and the established default target remains `MichalMatu/esp32s3_LiteGraph`.

A multi-repository v4.6 implementation is developed independently on `v4.6-multirepo-staging`. It keeps the v4.5 execution core and adds a process-isolated supervisor/worker layer so multiple repositories may queue work independently while local execution remains serialized.

For a new reusable/config-driven deployment, prefer [`MichalMatu/DeterministicRunner`](https://github.com/MichalMatu/DeterministicRunner). `local-agent` intentionally preserves environment-specific and legacy behavior from the working macOS/ESP32 setup.

## Layout

```text
.
├── agentd.py                  # validated v4.5 daemon/runtime orchestration
├── agent_core.py             # deterministic task execution/publication
├── agent_runtime.py          # watchdogs, staged execution, progress/telemetry
├── agent_process.py          # shared bounded output and process-group lifecycle
├── agent_repository.py       # v4.6 repository registry and workspace identity
├── agent_repo_worker.py      # v4.6 isolated one-repository worker turn
├── agent_multirepo.py        # v4.6 serialized multi-repository supervisor
├── agent_repo_admin.py       # v4.6 explicit provisioning/validation CLI
├── agentctl.py               # diagnostics CLI
├── config/
│   └── repositories.example.json
├── tests/                    # unit + temporary-Git integration tests
├── docs/
│   ├── OPERATIONS.md         # canonical execution workflow
│   ├── MULTI_REPOSITORY.md   # v4.6 architecture and administration
│   ├── SESSION_BOOTSTRAP.md  # established Mac + ESP32 deployment details
│   ├── GOLDEN_STANDARD.md    # current infrastructure invariants/audit state
│   └── history/              # historical design material
├── deploy/macos/             # launchd configuration/templates
└── .github/workflows/ci.yml
```

## Quick validation

The runtime daemon has no third-party Python dependency requirement. CI additionally installs a pinned Ruff version for lint validation.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m py_compile agentd.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_repo_admin.py agentctl.py
python -m pip install ruff==0.12.11
ruff check agentd.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_repo_admin.py agentctl.py tests
python -m unittest discover -q
```

Useful v4.5 diagnostics:

```bash
./.venv/bin/python agentctl.py status
./.venv/bin/python agentctl.py doctor
./.venv/bin/python agentctl.py task <task-id>
./.venv/bin/python agentctl.py validate-task /path/to/task.json
```

Useful v4.6 staging administration:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
python agent_repo_admin.py provision --repository-id photomaps
python agent_multirepo.py --once
```

Do not start a second foreground daemon/supervisor when the production LaunchAgent is already running. v4.5 and v4.6 use the same OS daemon lock so they cannot execute concurrently.

## v4.5 production contract

The canonical `main` release remains v4.5.x until the v4.6 staging release gate is explicitly completed. Important behavior:

- durable task digest + attempt claim; interrupted tasks are never silently replayed;
- command timeout default 900 s, maximum 1500 s;
- no-output timeout default 300 s, maximum 900 s;
- whole-task budget 1800 s with a 60 s finalization reserve;
- process-group RSS limit default 4096 MiB, configurable up to 16384 MiB, with `0` disabling that watchdog;
- command stdout uses bounded read chunks, a bounded handoff queue and a strictly bounded 60,000-character result buffer;
- process spawning and process-group termination are centralized in `agent_process.py`;
- task progress/results/status are published on `agent-control`;
- self-update accepts only validated fast-forward updates from a clean `main` checkout;
- dirty disposable workspaces are checkpointed before destructive cleanup.

## v4.6 multi-repository staging contract

v4.6 adds the following without changing the single-task execution semantics:

- machine-local repository registry at `~/Library/Application Support/local-agent/repositories.json`;
- v4.5-compatible LiteGraph fallback when that registry does not exist;
- isolated `control`, `work`, `checkpoints`, claims, runs and status per repository;
- one long-lived supervisor plus a short-lived worker process per repository turn;
- deterministic round-robin scheduling with global execution concurrency fixed at one;
- repository-scoped task identity, so identical task ids in different repositories do not collide;
- explicit provisioning that validates existing paths/origins and can safely create a missing `agent-control` branch;
- repository-local status control; global `restart`/`self_update` are deliberately rejected inside workers because they are supervisor-wide maintenance actions;
- temporary-Git two-repository integration coverage, including duplicate task ids and clean claim/workspace recovery.

This means separate ChatGPT conversations can queue work independently to different repositories. The chats may work concurrently, while the Mac executes their queued tasks one at a time to avoid conflicts around PlatformIO, USB, serial ports and other machine-wide resources.

`expected_head` guarding from DeterministicRunner is not implemented here. If exact source identity matters, verify the expected Git SHA explicitly in an early task command.

## Documentation

Read in this order when working on the daemon:

1. [`AGENTS.md`](AGENTS.md) — repository safety and authoring rules.
2. [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — canonical queue/execution workflow.
3. [`docs/MULTI_REPOSITORY.md`](docs/MULTI_REPOSITORY.md) — v4.6 registry, provisioning, scheduler and rollout.
4. [`docs/SESSION_BOOTSTRAP.md`](docs/SESSION_BOOTSTRAP.md) — established machine and ESP32 bench details when needed.
5. [`docs/GOLDEN_STANDARD.md`](docs/GOLDEN_STANDARD.md) — versioned invariants and audit disposition.

Historical design material is retained under [`docs/history/`](docs/history/) and is not a source of current runtime behavior.
