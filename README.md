# local-agent

[![CI](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml)

Deterministic local execution infrastructure for AI-assisted software development.

A planner decides **what should change** and supplies the exact task. `local-agent` executes that task on the local machine under bounded runtime rules, preserves failure evidence, and publishes a machine-readable result describing **what actually happened**.

> The planner decides the work. The executor makes the run deterministic, bounded and observable.

**Current release:** `v4.10.2`

`local-agent` is the actively developed implementation. It started as execution infrastructure for one ESP32 development workspace and has evolved into a multi-repository supervisor while retaining a compatible single-repository fallback for the established setup.

## What it provides

- **Deterministic task execution** — immutable task digests, durable attempt claims and explicit terminal results.
- **Bounded processes** — command, no-output, whole-task and RSS watchdogs with bounded stdout retention.
- **Process-tree control** — commands run in process groups; leaked descendants are terminated and reported.
- **Crash-safe recovery** — dirty workspaces are checkpointed before destructive cleanup and completed results are durably spooled before publication.
- **Multi-repository scheduling** — one supervisor dispatches isolated repository workers with repository-scoped state.
- **OS execution leases** — repository/workspace identities remain locked through descendant-process lifetime, preventing unsafe concurrent recovery or reuse.
- **Git-backed control plane** — tasks, acknowledgements, progress, results and status are exchanged through repository control branches.
- **Failure-aware networking** — transient Git transport failures use bounded retry/backoff while deterministic authentication/configuration errors fail fast.
- **Safe maintenance** — self-update accepts validated fast-forward updates from a clean `main` checkout.
- **macOS deployment** — `launchd` templates are included for single-repository and multi-repository operation.

## Architecture

```text
AI planner / ChatGPT
        │
        │ exact task payload
        ▼
repository agent-control branch
        │
        ▼
┌─────────────────────────────┐
│ local-agent supervisor      │
│ - repository registry       │
│ - deterministic scheduling  │
│ - global execution lock     │
└──────────────┬──────────────┘
               │ one repository turn
               ▼
┌─────────────────────────────┐
│ short-lived repo worker     │
│ - validates repository      │
│ - claims task durably       │
│ - owns execution leases     │
└──────────────┬──────────────┘
               │
               ▼
local worktree / commands
               │
               ▼
durable result spool
               │
               ▼
agent-control result + status
```

Global execution concurrency is intentionally fixed at **one**. Separate planner conversations may queue work for different repositories concurrently, while the Mac serializes actual local execution to avoid collisions around PlatformIO, USB devices, serial ports and other machine-wide resources.

## Repository layout

```text
.
├── agentd.py                  # single-repository daemon + shared orchestration
├── agent_config.py            # startup-loaded timeout/resource configuration
├── agent_core.py              # deterministic task execution and publication
├── agent_runtime.py           # staged execution, watchdogs and telemetry
├── agent_process.py           # process groups, leases and bounded output
├── agent_storage.py           # bounded control-Git storage helpers
├── agent_repository.py        # repository registry and workspace identity
├── agent_repo_worker.py       # isolated one-repository worker turn
├── agent_multirepo.py         # multi-repository supervisor/scheduler
├── agent_repo_admin.py        # provisioning and registry validation CLI
├── agentctl.py                # diagnostics CLI
├── agent_version.py           # release-version source of truth
├── config/
│   └── repositories.example.json
├── deploy/macos/              # launchd templates
├── tests/                     # unit + temporary-Git integration tests
├── docs/
│   ├── OPERATIONS.md          # canonical task/execution workflow
│   ├── MULTI_REPOSITORY.md    # registry, workers and scheduler
│   ├── SESSION_BOOTSTRAP.md   # established machine/ESP32 bench setup
│   ├── GOLDEN_STANDARD.md     # current production invariants
│   └── history/               # historical design material
└── .github/workflows/ci.yml
```

## Runtime limits

Defaults are deliberately finite. Upper bounds prevent a task payload from silently disabling the safety model.

| Guard | Default | Maximum |
| --- | ---: | ---: |
| Command timeout | 900 s | 7200 s |
| No-output timeout | 300 s | 3600 s |
| Whole-task budget | 1800 s | 21600 s |
| Process-group RSS | 4096 MiB | 16384 MiB |

The RSS watchdog can be disabled explicitly with `0`. Whole-task admission reserves finalization headroom so a new stage is not started when it cannot fit safely inside the remaining budget.

## Reliability model

The runtime is designed around interrupted and partially successful work rather than assuming a happy-path command runner.

### Task identity and replay

- every task has an immutable payload digest;
- a durable claim records the execution attempt;
- an interrupted claimed task is not silently replayed;
- malformed or oversized task files fail as terminal input errors;
- repository-scoped task identities allow the same task id in different repositories without collision.

### Processes and shutdown

- every spawned subprocess is registered atomically with shutdown;
- commands use process groups rather than tracking only the direct child;
- successful commands may not leave background descendants;
- residual process groups are terminated and reported as `background_process_leak`;
- SIGTERM handling uses bounded TERM → KILL escalation;
- signals arriving during sensitive spawn/control-Git transactions are deferred only for the bounded critical section and then redelivered.

### Workspace recovery

- dirty tracked and untracked content is checkpointed outside the worktree before destructive cleanup;
- checkpoint creation is bounded by time, file count and bytes and is durably synced;
- checkpoint failure prevents cleanup and preserves the original dirty state;
- cleanup/finalization failures remain visible alongside the original task failure.

### Publication recovery

- progress publication is asynchronous and coalesced so network Git cannot block command watchdog enforcement;
- final results are atomically spooled before remote publication;
- if publication fails, recovery republishes the durable result without re-executing the task.

The exact production invariants are maintained in [`docs/GOLDEN_STANDARD.md`](docs/GOLDEN_STANDARD.md).

## Multi-repository mode

The optional local registry lives at:

```text
~/Library/Application Support/local-agent/repositories.json
```

When configured, the supervisor provides:

- deterministic round-robin repository scheduling;
- faster polling for the recently active repository without starving periodic full scans or supervisor controls;
- isolated `control`, `work`, `checkpoints`, claims, runs and status per repository;
- case-insensitive repository-id and remote uniqueness checks;
- normalized workspace isolation, including alias and ancestor/descendant overlap rejection;
- immutable worker-dispatch configuration digests;
- inherited OS leases for repository id, remote and workspace identities;
- explicit provisioning rather than implicit checkout repair or replacement;
- worker isolation so one repository failure does not stop polling the others.

Example administration:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
python agent_repo_admin.py provision --repository-id matrixhub
python agent_multirepo.py --once
```

See [`docs/MULTI_REPOSITORY.md`](docs/MULTI_REPOSITORY.md) for the full contract.

## Efficient verification workflow

Structured coding tasks can opt into:

```json
"workflow_policy": "efficient-verification-v1"
```

The policy distinguishes three verification intents:

- `work` — fast checks while implementing;
- `focused` — validation of the affected behavior;
- `full` — the repository-wide final gate.

A structured plan must finish with exactly one `full` verification stage. The daemon validates the stage contract but does **not** infer intent from command text and never silently deduplicates declared commands.

The canonical edit → review → final-gate → defect-recovery workflow is documented in [`docs/OPERATIONS.md`](docs/OPERATIONS.md#efficient-verification-workflow).

## Local validation

The runtime itself has no third-party Python dependency requirement. CI installs a pinned Ruff version for linting.

```bash
python3 -m venv .venv
source .venv/bin/activate

python -m py_compile \
  agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py \
  agent_storage.py agent_repository.py agent_repo_worker.py agent_multirepo.py \
  agent_repo_admin.py agentctl.py agent_version.py

python -m pip install ruff==0.12.11
ruff check \
  agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py \
  agent_storage.py agent_repository.py agent_repo_worker.py agent_multirepo.py \
  agent_repo_admin.py agentctl.py agent_version.py tests

python -m unittest discover -q
```

Useful diagnostics:

```bash
./.venv/bin/python agentctl.py status
./.venv/bin/python agentctl.py doctor
./.venv/bin/python agentctl.py task <task-id>
./.venv/bin/python agentctl.py validate-task /path/to/task.json
```

GitHub Actions also runs a macOS smoke job covering process lifecycle, checkpoint/recovery behavior and multi-repository execution.

## Deployment note

Do not start a second foreground daemon or supervisor when the production `launchd` service is already running. All entry points share the same OS daemon lock.

## Documentation

Read these in order when changing the runtime:

1. [`AGENTS.md`](AGENTS.md) — repository safety and authoring rules.
2. [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — canonical queue and execution workflow.
3. [`docs/MULTI_REPOSITORY.md`](docs/MULTI_REPOSITORY.md) — registry, provisioning and scheduler behavior.
4. [`docs/SESSION_BOOTSTRAP.md`](docs/SESSION_BOOTSTRAP.md) — established machine and ESP32 bench details when needed.
5. [`docs/GOLDEN_STANDARD.md`](docs/GOLDEN_STANDARD.md) — versioned runtime/release invariants.

Historical design material under [`docs/history/`](docs/history/) is retained for context and is not a source of current runtime behavior.
