# local-agent

[![CI](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/MichalMatu/local-agent/actions/workflows/ci.yml)
![Status](https://img.shields.io/badge/status-working%20implementation-2ea44f)

**The working, opinionated deterministic execution daemon used for real local development.**

`local-agent` is the practical implementation of the same planning/execution split that is being generalized in [`DeterministicRunner`](https://github.com/MichalMatu/DeterministicRunner).

ChatGPT decides the code changes and exact commands. `local-agent` executes them on the local machine and publishes machine-readable evidence back to the target repository.

> **The planner decides what to do. The daemon executes the deterministic task and reports what actually happened. Real output is the source of truth.**

```text
ChatGPT / planner
      |
      v
explicit task JSON
      |
      v
Git control branch
      |
      v
local-agent daemon
      |
      +--> disposable work clone
      |       commands / tests / builds / flash / inspect
      |
      +--> durable local state
      |       claims / checkpoints / status / runs
      |
      v
machine-readable result + progress
      |
      +--------> planner inspects evidence and chooses the next task
```

## Which repository should I use?

| Repository | Best for |
| --- | --- |
| [`MichalMatu/local-agent`](https://github.com/MichalMatu/local-agent) | Inspecting or continuing the existing macOS/ESP32 implementation used in practice. |
| [`MichalMatu/DeterministicRunner`](https://github.com/MichalMatu/DeterministicRunner) | Starting a new, reusable, repository-agnostic and config-driven setup. |

If you want to reproduce the concept on another machine or target project, **start with DeterministicRunner**. `local-agent` intentionally contains environment-specific and legacy implementation semantics from the system it currently operates.

## What this repository is

This repository is **execution infrastructure**, not the product repository and not a coding model.

For the established workflow, the default product target is:

```text
MichalMatu/esp32s3_LiteGraph
```

with:

```text
target source branch: main
target control branch: agent-control
daemon repository: MichalMatu/local-agent
daemon source branch: main
```

Future AI sessions should treat `esp32s3_LiteGraph` as the product target unless the user explicitly asks to modify, audit, or debug `local-agent` itself.

The daemon can:

- consume explicit tasks from a Git control branch;
- run shell commands, builds and tests;
- flash and inspect ESP32 hardware;
- capture bounded result output and exit codes;
- publish remote task progress and terminal result JSON;
- expose daemon health remotely;
- accept durable `status`, `restart`, and `self_update` control requests;
- checkpoint dirty disposable-workspace state before destructive cleanup.

## Environment truth

`local-agent` is the **working deployment**, not a general cross-platform package.

The established runtime assumes:

- macOS/POSIX behavior including `fcntl`;
- Git;
- a local control/work/checkpoint topology under `~/agent-workspace`;
- a daemon checkout normally at `~/local-agent`;
- `launchd` as the outer production supervisor;
- PlatformIO/Homebrew tool paths used by the current development environment.

The core daemon currently uses only the Python standard library. GitHub CI validates compile/unit tests on **Python 3.12 / Ubuntu**, while the deployed workflow is macOS-specific.

The checked-in [`com.michal.local-agent.plist`](com.michal.local-agent.plist) contains machine-specific absolute paths. It documents the current installation; it is **not a portable installer and should not be copied unchanged** to another user account or machine.

For a portable/config-driven installation, use [`DeterministicRunner`](https://github.com/MichalMatu/DeterministicRunner).

## Important differences from DeterministicRunner

Do not assume that every DeterministicRunner v0.2 feature exists in this older working daemon.

Current `local-agent` semantics include:

- Git control transport and workspace paths are hardcoded for the established deployment rather than YAML-configured;
- the task validator is a legacy contract and does not reject every unknown field;
- `expected_head` source-revision guarding is **not implemented** here—an `expected_head` field would not provide DeterministicRunner-style protection;
- if source identity matters, verify the expected SHA explicitly in an early task command before later side effects;
- identical command strings inside one task may reuse the earlier command result instead of executing the same string again;
- disposable-worktree cleanup uses `git clean -fd`, intentionally preserving ignored build caches;
- self-update validates the fast-forwarded checkout and rolls back on failure; DeterministicRunner uses the newer detached-candidate validation design.

These differences are intentional documentation of the current code, not recommendations for new generic deployments.

---

## Quick start for development and validation

Clone the daemon:

```bash
git clone https://github.com/MichalMatu/local-agent.git ~/local-agent
cd ~/local-agent
```

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

There is currently no third-party package-install step for the core daemon.

Validate the checkout:

```bash
python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py
python -m unittest discover -q
```

Useful diagnostics:

```bash
./.venv/bin/python agentctl.py status
./.venv/bin/python agentctl.py doctor
./.venv/bin/python agentctl.py task <task-id>
./.venv/bin/python agentctl.py validate-task /path/to/task.json
```

`doctor` and actual daemon operation expect the established control/work topology to exist.

After that topology is present, the daemon can be run in the foreground with:

```bash
./.venv/bin/python agentd.py
```

Do not start a second foreground instance when the production LaunchAgent is already running. The daemon uses an OS file lock to enforce a single active instance.

For the exact established machine/ESP32 setup, read [`SESSION_BOOTSTRAP.md`](SESSION_BOOTSTRAP.md) rather than treating this repository as a generic installer.

## Established local topology

The working deployment currently uses:

```text
~/local-agent
~/agent-workspace/control
~/agent-workspace/work
~/agent-workspace/checkpoints
~/Library/Application Support/local-agent
~/Library/Logs/local-agent.log
```

The human/project checkout is **not** the disposable agent worktree. Normal daemon execution must not reset or clean the human working checkout.

Treat `~/agent-workspace/control` as daemon execution infrastructure. During normal operation, publish new tasks/control requests to the remote `agent-control` branch through GitHub/API tooling or another trusted writer checkout rather than manually editing the daemon's control clone.

## Queue and remote observability

On the target repository's `agent-control` branch:

```text
.agent/tasks/<task-id>.json
.agent/status/daemon.json
.agent/runs/<task-id>.json
.agent/results/<task-id>.json
.agent/daemon/control.json
.agent/daemon/acks/<control-id>.json
```

Use them as follows:

- `.agent/tasks/<task-id>.json` — explicit queued work;
- `.agent/status/daemon.json` — daemon health/state;
- `.agent/runs/<task-id>.json` — current task progress;
- `.agent/results/<task-id>.json` — terminal execution result;
- `.agent/daemon/control.json` — remote daemon request;
- `.agent/daemon/acks/<control-id>.json` — durable acknowledgement.

The user should not need to paste live daemon output during normal operation. An AI planner should inspect the remote status/run/result evidence directly.

## Remote daemon control

Example request:

```json
{
  "id": "restart-20260823-001",
  "action": "restart"
}
```

Supported actions are:

- `status`;
- `restart`;
- `self_update`.

A handled command receives a durable acknowledgement so the same control request is not repeated after restart.

## Current golden-standard contract

The authoritative infrastructure invariants are in [`GOLDEN_STANDARD.md`](GOLDEN_STANDARD.md). The current golden-standard family is **v4.3**, and `agentd.py` currently reports:

```text
DAEMON_VERSION = 4.3.0
```

Important invariants include:

- `agentd.py` is the only daemon entry point;
- the daemon is a deterministic executor, never a coding model;
- one OS-locked daemon instance is allowed;
- every task is bound to an immutable payload digest and unique attempt ID;
- a durable claim exists before side-effect-capable execution;
- a claimed/interrupted task is never automatically replayed;
- malformed task JSON becomes terminal `invalid_task_file`;
- corrupt durable claims are quarantined and fail closed;
- command, no-output, and whole-task watchdogs are mandatory;
- child commands run in process groups so timeout/shutdown can terminate the group;
- long workflows should use named sequential `steps`/`verify_steps`; intentionally
  long single scripts should emit `[AGENT_PROGRESS]` JSON markers;
- local command heartbeats are about 30 seconds and remote progress is normally
  refreshed about every 60 seconds, with best-effort host/process telemetry;
- result publication may be retried, execution may not;
- self-update is fast-forward-only, validates before the new revision becomes the long-running process, and fails closed;
- target-project verification is selected from realistic change impact instead of blindly running unrelated broad suites;
- secrets never belong in Git-backed task/result/run/control data or repository documentation.

When README wording and operational detail ever diverge, [`GOLDEN_STANDARD.md`](GOLDEN_STANDARD.md) and [`SESSION_BOOTSTRAP.md`](SESSION_BOOTSTRAP.md) are the authoritative references for the established deployment.

## Replay safety

A task is durably claimed before execution begins. The claim records the task payload digest and attempt ID.

If the daemon or host restarts while a task is claimed, the old task is not automatically executed again. Recovery publishes terminal evidence such as `interrupted_previous_attempt` or, for corrupt durable state, fails closed according to the golden-standard contract.

Do not reuse a task ID for a different payload.

## Workspace checkpoints

Before destructive reset/clean of the disposable worktree, the daemon checks whether it is dirty.

Dirty state is saved under:

```text
~/agent-workspace/checkpoints/<task-id>/
```

Tracked changes are preserved as a binary Git patch, non-ignored untracked files are copied byte-for-byte, and metadata records the base commit.

If checkpoint creation fails, cleanup is skipped and the task fails closed rather than destroying the only remaining copy.

Checkpoints are intentionally not deleted automatically.

## Time limits

Current defaults are:

```text
command timeout:   1200 s
no-output timeout:  600 s
whole-task timeout: 3600 s
```

Current maximums are:

```text
command timeout:   3600 s
no-output timeout: 3600 s
whole-task timeout: 14400 s
```

`idle_timeout=0` disables only the no-output watchdog.

## Self-update

When idle, the daemon checks `local-agent/main` at most once every **60 seconds**.

The current implementation first requires a clean checkout on `main` and a fast-forward remote revision. It then fast-forwards the checkout, runs `py_compile` and the unit suite against the installed revision, resets to the previous SHA if validation fails, remembers the rejected SHA, and only `exec`-restarts after validation succeeds. `launchd` remains the outer supervisor.

This differs from DeterministicRunner's newer detached-candidate self-update design: `local-agent` temporarily moves the checkout before validation, but the already-running Python process is not replaced by the new revision unless validation succeeds.

For non-trivial daemon changes, use the isolated release flow described in [`SESSION_BOOTSTRAP.md`](SESSION_BOOTSTRAP.md) and [`GOLDEN_STANDARD.md`](GOLDEN_STANDARD.md). Never prepare a daemon release by mutating the checkout that is currently running `agentd.py`.

## Live logs

Latest 30 lines:

```bash
tail -n 30 ~/Library/Logs/local-agent.log
```

Follow the log:

```bash
tail -n 30 -f ~/Library/Logs/local-agent.log
```

Stop following with `Ctrl+C`.

Remote `.agent/status`, `.agent/runs`, and `.agent/results` remain the preferred normal-operation interface for an AI planner.

## For AI assistants and future sessions

[`SESSION_BOOTSTRAP.md`](SESSION_BOOTSTRAP.md) is the canonical cross-repository entry point.

Before queueing work, an AI system should read:

1. [`SESSION_BOOTSTRAP.md`](SESSION_BOOTSTRAP.md);
2. [`AGENTS.md`](AGENTS.md);
3. [`LOCAL_AGENT_FLOW.md`](LOCAL_AGENT_FLOW.md);
4. [`LOCAL_AGENT_AUTOPILOT.md`](LOCAL_AGENT_AUTOPILOT.md) when autonomous execution is requested;
5. [`GOLDEN_STANDARD.md`](GOLDEN_STANDARD.md);
6. the target repository's own root/nearest `AGENTS.md` and relevant documentation/tests.

Then it should:

- inspect remote daemon/task state before queueing anything;
- follow an existing `attempt_id`/`task_digest` instead of creating a duplicate task;
- publish task/control files through the remote control branch, not by editing the daemon-owned control clone;
- do not assume DeterministicRunner-only fields such as `expected_head` are enforced by `local-agent`;
- select verification from realistic change impact rather than ritual;
- distinguish executed/tested source from source actually published to the target branch;
- distinguish published firmware source from firmware actually flashed/running on hardware;
- use exact evidence instead of inference;
- keep all machine-generated execution content in English;
- keep secrets out of Git-backed control/evidence files.

## Source of truth

Use this order:

1. real local-agent command/result evidence;
2. target repository source and tests;
3. remote run/daemon status;
4. planner analysis.

Do not claim success until the requested gates are actually green and the intended source has been published. Hardware validation additionally requires explicit evidence that the intended firmware was uploaded or an exact build-identity mechanism proves the running revision.

## Safety

`local-agent` executes commands with the permissions of the local user running it.

The Git control branch is therefore trusted-code input. Anyone who can publish accepted task commands can exercise those local privileges.

Never commit passwords, API tokens, bearer tokens, private keys, or session material to:

```text
.agent/tasks
.agent/runs
.agent/results
.agent/daemon
```

Keep authentication material in a local non-versioned secret store such as macOS Keychain or an equivalent mechanism.

## Development

Canonical validation:

```bash
python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py
python -m unittest discover -q
```

GitHub CI currently runs these checks on Python 3.12 / Ubuntu.

For infrastructure changes, follow the release gate in [`GOLDEN_STANDARD.md`](GOLDEN_STANDARD.md): isolated staging, local validation, green CI on the exact candidate SHA, fast-forward `main`, daemon self-update, remote version verification, and one real queue smoke task.

## Design principle

> **The planner decides what to do. The daemon executes the deterministic task and reports what actually happened.**
