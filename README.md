# Local Agent

Deterministic local execution daemon used by ChatGPT to build, test, flash and inspect `MichalMatu/esp32s3_LiteGraph` on the user's Mac.

The daemon is deliberately **not** a coding model. ChatGPT decides code changes and exact commands; the daemon executes them and publishes machine-readable evidence back to the `agent-control` branch.

## v4 guarantees

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
- self-update from `local-agent/main`, local validation, rollback on failure, then `exec` restart.

## Time limits

Defaults are command 1200 s, no-output 600 s and whole task 3600 s. Maximums are 3600 s, 3600 s and 14400 s respectively. `idle_timeout=0` explicitly disables only the no-output watchdog.

## Remote observability

On the target repository's `agent-control` branch:

```text
.agent/status/daemon.json
.agent/runs/<task-id>.json
.agent/results/<task-id>.json
```

Command transitions publish immediately. Long-running commands publish a remote heartbeat at most once every five minutes.

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
