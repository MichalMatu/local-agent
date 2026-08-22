# Local Agent

Deterministic local execution daemon used by ChatGPT to build, test, flash and inspect `MichalMatu/esp32s3_LiteGraph` on the user's Mac.

The daemon is deliberately **not** a coding model. ChatGPT decides code changes and exact commands; the daemon executes them and publishes machine-readable evidence back to the `agent-control` branch.

For future sessions, `SESSION_BOOTSTRAP.md` is the canonical cross-repository entrypoint. Merely providing this repository or asking to use the established local-agent flow means the default product target is `MichalMatu/esp32s3_LiteGraph`, unless the user explicitly asks to modify the daemon itself.

## v4.1 guarantees

- single daemon instance enforced with an OS file lock;
- durable per-task claim before any execution;
- a claimed task is never automatically replayed after a crash/restart;
- task payload SHA-256 digest and unique attempt id are recorded;
- per-command timeout, no-output timeout and whole-task timeout;
- child commands run in their own process groups and are terminated as a group;
- SIGTERM/SIGINT terminate the active command group before daemon exit;
- remote progress is published to `.agent/runs/<task-id>.json`;
- daemon health is published to `.agent/status/daemon.json`;
- remote daemon commands use `.agent/daemon/control.json` with durable acknowledgements;
- self-update from `local-agent/main`, local validation, rollback on failure, then `exec` restart;
- remote progress commits are coalesced so short command chains do not create one or more Git commits per command boundary.

## Time limits

Defaults are command 1200 s, no-output 600 s and whole task 3600 s. Maximums are 3600 s, 3600 s and 14400 s respectively. `idle_timeout=0` explicitly disables only the no-output watchdog.

## Remote observability

On the target repository's `agent-control` branch:

```text
.agent/status/daemon.json
.agent/runs/<task-id>.json
.agent/results/<task-id>.json
```

Local command transitions are recorded immediately. Remote task progress is coalesced: task boundaries, failures, the first command and phase changes publish immediately; ordinary short-command progress is limited to about once per minute; long-running commands retain a five-minute heartbeat.

Detailed task execution belongs in `.agent/runs/<task-id>.json`. `.agent/status/daemon.json` is daemon health/state and uses state changes plus a five-minute heartbeat instead of mirroring every command.

## Remote daemon control

Write `.agent/daemon/control.json`, for example:

```json
{
  "id": "restart-20260822-001",
  "action": "restart"
}
```

Supported actions are `restart`, `self_update`, and `status`. Acknowledgements are stored in `.agent/daemon/acks/<id>.json`, so a handled command is not replayed after restart.

## Self-update

When idle, the daemon checks `MichalMatu/local-agent/main` every 60 seconds. It accepts only a fast-forward update, runs `py_compile` and the full unit suite, rolls back a failed update, remembers the rejected SHA, and `exec`s a validated daemon in place. `launchd` remains the outer supervisor.

For non-trivial daemon changes, stage and validate them before moving `main`. See `SESSION_BOOTSTRAP.md` for the exact staging -> CI -> fast-forward -> self-update -> remote verification sequence.

## Local diagnostics

```bash
cd ~/local-agent
./.venv/bin/python agentctl.py status
./.venv/bin/python agentctl.py doctor
./.venv/bin/python agentctl.py task <task-id>
./.venv/bin/python agentctl.py validate-task /path/to/task.json
```

## Tests

```bash
python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py
python -m unittest discover -q
```

## Golden-standard reference

Read `GOLDEN_STANDARD.md` for the final infrastructure invariants and audit disposition. Source publication and ESP32 hardware flashing are separate gates; never infer the running firmware commit from repository `main` or semantic firmware version alone.

### Invalid task contract

Malformed task JSON and filename/payload-id mismatches are terminal queue errors, not retry candidates. The daemon publishes `failure_reason=invalid_task_file`, and pending scans check an existing result by filename before parsing so a bad task cannot spam every poll forever.
