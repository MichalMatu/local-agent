# local-agent

[![CI](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml)

Deterministic local execution daemon used for real development work. ChatGPT or another planner decides the exact change and commands; `local-agent` executes them on the local machine and publishes machine-readable evidence.

> The planner decides what to do. The daemon executes the deterministic task and reports what actually happened.

## Repository role

This repository is execution infrastructure, not the product repository and not a coding model.

The release line is v4.10.x. The established default target remains `MichalMatu/esp32s3_LiteGraph` when no multi-repository registry is configured.

For a new reusable/config-driven deployment, prefer [`MichalMatu/DeterministicRunner`](https://github.com/MichalMatu/DeterministicRunner). `local-agent` intentionally preserves environment-specific and legacy behavior from the working macOS/ESP32 setup.

## Layout

```text
.
├── agentd.py                  # daemon orchestration and durable publication
├── agent_config.py           # startup-loaded runtime timeout configuration
├── agent_version.py          # single release-version source of truth
├── agent_core.py             # deterministic task execution/publication
├── agent_runtime.py          # watchdogs, staged execution, progress/telemetry
├── agent_process.py          # shared bounded output and process-group lifecycle
├── agent_repository.py       # repository registry and workspace identity
├── agent_repo_worker.py      # isolated one-repository worker turn
├── agent_multirepo.py        # serialized multi-repository supervisor
├── agent_repo_admin.py       # explicit provisioning/validation CLI
├── agentctl.py               # diagnostics CLI
├── config/
│   └── repositories.example.json
├── tests/                    # unit + temporary-Git integration tests
├── docs/
│   ├── OPERATIONS.md         # canonical execution workflow
│   ├── MULTI_REPOSITORY.md   # architecture and administration
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
python -m py_compile agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_repo_admin.py agentctl.py agent_version.py
python -m pip install ruff==0.12.11
ruff check agentd.py agent_config.py agent_core.py agent_runtime.py agent_process.py agent_repository.py agent_repo_worker.py agent_multirepo.py agent_repo_admin.py agentctl.py agent_version.py tests
python -m unittest discover -q
```

Useful diagnostics:

```bash
./.venv/bin/python agentctl.py status
./.venv/bin/python agentctl.py doctor
./.venv/bin/python agentctl.py task <task-id>
./.venv/bin/python agentctl.py validate-task /path/to/task.json
```

Multi-repository administration:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
python agent_repo_admin.py provision --repository-id photomaps
python agent_multirepo.py --once
```

Do not start a second foreground daemon/supervisor when the production LaunchAgent is already running. All entry points use the same OS daemon lock.

## v4.10 execution contract

Important behavior:

- durable task digest + attempt claim; interrupted tasks are never silently replayed;
- command timeout default 900 s, maximum 7200 s;
- no-output timeout default 300 s, maximum 3600 s;
- whole-task budget default 1800 s, maximum 21600 s with a 60 s finalization reserve;
- process-group RSS limit default 4096 MiB, configurable up to 16384 MiB, with `0` disabling that watchdog;
- command stdout uses bounded read chunks, a bounded handoff queue and a strictly bounded 60,000-character result buffer;
- successful stages may not leave background descendants; a residual process group is terminated and reported as `background_process_leak`;
- process spawning and process-group termination are centralized in `agent_process.py`;
- every spawned descendant inherits repository execution leases, so a restarted supervisor cannot recover or enter a repository while an earlier command still owns it;
- SIGTERM shuts down every registered process group with bounded TERM-to-KILL escalation, including a signal arriving during process creation;
- task progress publication is asynchronous and coalesced so network Git cannot delay watchdog enforcement;
- final results are durably spooled before network publication and are republished without re-execution after a publication failure;
- task progress/results/status are published on `agent-control`;
- self-update accepts only validated fast-forward updates from a clean `main` checkout;
- self-update validation uses an isolated temporary home directory;
- dirty disposable workspaces are durably checkpointed before destructive cleanup, including tracked and untracked content;
- identical commands always execute independently in their declared order.

### Efficient verification task format

Staged coding tasks can opt in to explicit verification intent with
`workflow_policy: "efficient-verification-v1"`:

```json
{
  "id": "example-efficient-change",
  "mode": "commands",
  "workflow_policy": "efficient-verification-v1",
  "steps": [
    {
      "name": "implement-and-check-edited-area",
      "command": "./scripts/check-edited-area.sh",
      "verification_level": "work"
    },
    {
      "name": "review-affected-behavior",
      "command": "./scripts/review-affected-behavior.sh",
      "verification_level": "focused"
    }
  ],
  "verify_steps": [
    {
      "name": "final-verification",
      "command": "./scripts/final-verification.sh",
      "verification_level": "full"
    }
  ]
}
```

Every structured stage must declare `verification_level`. Primary `steps` accept
`work` or `focused`; `verify_steps` accept `focused` and a single final `full`
stage. The full stage must occur exactly once and finish the whole plan. The
final-verification script in the example represents the repository-mandated
broad suite followed once by its final build or release gate; the daemon does not
interpret command text.

Tasks without `workflow_policy` retain the legacy `commands`, `verify_commands`
and structured-stage behavior. Commands are never silently deduplicated. See
[`docs/OPERATIONS.md`](docs/OPERATIONS.md#efficient-verification-workflow) for
the canonical edit, review, final-gate and defect-recovery workflow.

## Multi-repository contract

Multi-repository mode adds the following without changing the single-task execution semantics:

- machine-local repository registry at `~/Library/Application Support/local-agent/repositories.json`;
- legacy LiteGraph workspace fallback when that registry does not exist;
- isolated `control`, `work`, `checkpoints`, claims, runs and status per repository;
- one long-lived supervisor plus a short-lived worker process per repository turn;
- deterministic round-robin scheduling with global execution concurrency fixed at one;
- periodic full scans and supervisor control deadlines take priority over hot polling, preventing a continuously busy repository from starving other queues or maintenance;
- case-insensitive repository-id and remote uniqueness plus normalized, aliased and case-insensitive workspace isolation;
- immutable worker-dispatch configuration digests and OS lifetime leases for repository id, remote and workspace identities;
- repository-scoped task identity, so identical task ids in different repositories do not collide;
- explicit provisioning that validates existing paths/origins and can safely create a missing `agent-control` branch;
- repository-local status control; global `restart`/`self_update` are deliberately rejected inside workers because they are supervisor-wide maintenance actions;
- temporary-Git integration coverage, including duplicate task ids, clean claim/workspace recovery and real supervisor/worker SIGTERM/SIGKILL failures.

This means separate ChatGPT conversations can queue work independently to different repositories. The chats may work concurrently, while the Mac executes their queued tasks one at a time to avoid conflicts around PlatformIO, USB, serial ports and other machine-wide resources.

`expected_head` guarding from DeterministicRunner is not implemented here. If exact source identity matters, verify the expected Git SHA explicitly in an early task command.

## Documentation

Read in this order when working on the daemon:

1. [`AGENTS.md`](AGENTS.md) — repository safety and authoring rules.
2. [`docs/OPERATIONS.md`](docs/OPERATIONS.md) — canonical queue/execution workflow.
3. [`docs/MULTI_REPOSITORY.md`](docs/MULTI_REPOSITORY.md) — registry, provisioning, scheduler and rollout.
4. [`docs/SESSION_BOOTSTRAP.md`](docs/SESSION_BOOTSTRAP.md) — established machine and ESP32 bench details when needed.
5. [`docs/GOLDEN_STANDARD.md`](docs/GOLDEN_STANDARD.md) — versioned invariants and audit disposition.

Historical design material is retained under [`docs/history/`](docs/history/) and is not a source of current runtime behavior.
