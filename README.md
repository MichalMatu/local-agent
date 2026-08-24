# local-agent

[![CI](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml)

Deterministic local execution daemon used for real development work. ChatGPT or another planner decides the exact change and commands; `local-agent` executes them on the local machine and publishes machine-readable evidence.

> The planner decides what to do. The daemon executes the deterministic task and reports what actually happened.

## Repository role

This repository is execution infrastructure, not the product repository and not a coding model.

The established default target is `MichalMatu/esp32s3_LiteGraph`:

- target source branch: `main`
- target control branch: `agent-control`
- daemon source branch: `main`

For a new reusable/config-driven deployment, prefer [`MichalMatu/DeterministicRunner`](https://github.com/MichalMatu/DeterministicRunner). `local-agent` intentionally preserves environment-specific and legacy behavior from the working macOS/ESP32 setup.

## Layout

```text
.
├── agentd.py                  # daemon orchestration, claims, status/control, self-update
├── agent_core.py             # deterministic task execution/publication
├── agent_runtime.py          # watchdogs, staged execution, progress/telemetry
├── agent_process.py          # shared bounded output and process-group lifecycle
├── agentctl.py               # diagnostics CLI
├── tests/                    # unit tests
├── docs/
│   ├── OPERATIONS.md         # canonical execution workflow
│   ├── SESSION_BOOTSTRAP.md  # established Mac + ESP32 deployment details
│   ├── GOLDEN_STANDARD.md    # current infrastructure invariants/audit state
│   └── history/              # historical design material
├── deploy/macos/             # launchd configuration for the established machine
└── .github/workflows/ci.yml
```

## Quick validation

The runtime daemon has no third-party Python dependency requirement. CI additionally installs a pinned Ruff version for lint validation.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m py_compile agentd.py agent_core.py agent_runtime.py agent_process.py agentctl.py
python -m pip install ruff==0.12.11
ruff check agentd.py agent_core.py agent_runtime.py agent_process.py agentctl.py tests
python -m unittest discover -q
```

Useful diagnostics:

```bash
./.venv/bin/python agentctl.py status
./.venv/bin/python agentctl.py doctor
./.venv/bin/python agentctl.py task <task-id>
./.venv/bin/python agentctl.py validate-task /path/to/task.json
```

Do not start a second foreground daemon when the production LaunchAgent is already running. The daemon enforces a single active instance with an OS file lock.

## Current runtime contract

The current canonical release line is daemon v4.5.x. Important behavior:

- durable task digest + attempt claim; interrupted tasks are never silently replayed;
- command timeout default 900 s, maximum 1500 s;
- no-output timeout default 300 s, maximum 900 s;
- whole-task budget 1800 s with a 60 s finalization reserve;
- process-group RSS limit default 4096 MiB, configurable up to 16384 MiB, with `0` disabling that watchdog;
- command stdout uses bounded read chunks, a bounded handoff queue and a strictly bounded 60,000-character result buffer;
- process spawning and process-group termination are centralized in `agent_process.py`;
- runtime execution is explicitly injected into core task processing rather than installed by mutating a global command runner;
- structured stages may define smaller explicit timeouts;
- task progress/results/status are published on `agent-control`;
- broad target-project regression suites are impact-driven, not automatic;
- self-update accepts only validated fast-forward updates from a clean `main` checkout;
- dirty disposable workspaces are checkpointed before destructive cleanup;
- source publication and hardware flashing are separate validation gates.

`expected_head` guarding from DeterministicRunner is not implemented here. If exact source identity matters, verify the expected Git SHA explicitly in an early task command.

The historical `v4.2.4-staging` branch remains as a reference. Its useful bounded-output/RSS ideas were manually adapted to the current v4.5 runtime instead of merging the divergent branch directly.

## Documentation

Read in this order when working on the daemon:

1. [`AGENTS.md`](AGENTS.md) — repository safety and authoring rules.
2. [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — canonical queue/execution workflow.
3. [`docs/SESSION_BOOTSTRAP.md`](docs/SESSION_BOOTSTRAP.md) — established machine and ESP32 bench details when needed.
4. [`docs/GOLDEN_STANDARD.md`](docs/GOLDEN_STANDARD.md) — versioned invariants and audit disposition.

Historical design material is retained under [`docs/history/`](docs/history/) and is not a source of current runtime behavior.
