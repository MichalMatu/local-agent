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

## Workspace checkpoints

Before any destructive reset/clean of `~/agent-workspace/work`, the agent now checks for a dirty Git worktree. Dirty state is saved under `~/agent-workspace/checkpoints/<task-id>/...` as a binary Git patch for tracked files plus byte-for-byte copies of non-ignored untracked files and metadata containing the base commit. The checkpoint path is also returned in `workspace_checkpoint` when a task exits dirty.

The same safeguard runs before `prepare_work`, so an interrupted daemon cannot silently lose edits on the next task. If checkpoint creation itself fails, cleanup is skipped and the task is marked `workspace_checkpoint_failed` rather than destroying the only remaining copy. Ignored build/cache output is intentionally excluded.

Checkpoints are not automatically deleted. After changes are safely committed/pushed, old checkpoint directories may be removed manually.

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

## Live daemon logs

Show the latest 30 lines once:

```bash
tail -n 30 ~/Library/Logs/local-agent.log
```

Show the latest 30 lines and continue following new output live:

```bash
tail -n 30 -f ~/Library/Logs/local-agent.log
```

Follow only new output from the current end of the log:

```bash
tail -f ~/Library/Logs/local-agent.log
```

Stop live following with `Ctrl+C`. When the daemon prints `no pending task`, the queue is currently empty; use `agentctl.py status` or the remote `.agent/status/daemon.json` for authoritative daemon state.

Large unified diffs are compacted in the live daemon log after a bounded threshold, while small diffs remain visible. Compaction affects only the live log: raw command output is still retained in the existing bounded task-result buffer (`MAX_OUTPUT`) for diagnostics.

## Tests

```bash
python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py
python -m unittest discover -q
```

## Golden-standard reference

Read `GOLDEN_STANDARD.md` for the final infrastructure invariants and audit disposition. Source publication and ESP32 hardware flashing are separate gates; never infer the running firmware commit from repository `main` or semantic firmware version alone.

### Invalid task contract

Malformed task JSON is a terminal queue error, not a retry candidate. The daemon publishes `failure_reason=invalid_task_file` under the filename rejection key, and pending scans check that rejection before parsing so a bad task cannot spam every poll forever. Valid historical filename aliases/prefixes may differ from `task.id`; execution results and claims remain keyed by `task.id`.
