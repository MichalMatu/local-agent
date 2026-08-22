# Local Agent Flow v4.1

This is the canonical deterministic execution workflow.

The canonical future-session entrypoint is `SESSION_BOOTSTRAP.md`. If the user provides only the `local-agent` repository or says to use the established flow, default to working on `MichalMatu/esp32s3_LiteGraph`; do not wait for the user to restate the repository pairing.

## Roles

ChatGPT is the architect/programmer. It inspects source, chooses exact edits and exact commands, reads real results, iterates on failures and publishes validated source changes.

The local daemon is an executor. It syncs tasks, prepares a disposable worktree, applies exact edits, executes exact commands, publishes progress/results and cleans the worktree. It does not invent fixes.

## Repositories

- target: `MichalMatu/esp32s3_LiteGraph`
- target source branch: normally `main`
- target control branch: `agent-control`
- daemon source: `MichalMatu/local-agent`, branch `main`

Local paths:

- user target checkout: `/Users/michal/Documents/PlatformIO/Projects/esp32s3_LiteGraph`
- control clone: `~/agent-workspace/control`
- disposable work clone: `~/agent-workspace/work`
- daemon checkout: `~/local-agent`
- daemon log: `~/Library/Logs/local-agent.log`

## Queue and observability

Tasks:

```text
.agent/tasks/<task-id>.json
```

Results:

```text
.agent/results/<task-id>.json
```

Live progress:

```text
.agent/runs/<task-id>.json
```

Daemon health:

```text
.agent/status/daemon.json
```

Typical task:

```json
{
  "id": "example-013",
  "mode": "commands",
  "work_branch": "main",
  "allow_write": true,
  "commands": ["<exact command>"],
  "verify_commands": ["<exact verification>"],
  "command_timeout": 1200,
  "idle_timeout": 600,
  "task_timeout": 3600
}
```

Task ids use letters, digits, dot, underscore and hyphen only. Every payload gets a SHA-256 digest and every execution gets a unique attempt id.

## Replay safety

The daemon durably claims a task before work begins. If the daemon or Mac restarts while a task is claimed, the previous attempt is published as `interrupted_previous_attempt`; it is not replayed automatically.

A task id must not be reused for a different payload. Digest mismatch is a workflow error.

## Watchdogs

Defaults:

- command timeout: 1200 seconds;
- no-output timeout: 600 seconds;
- whole-task timeout: 3600 seconds.

Maximums are 3600, 3600 and 14400 seconds respectively. `idle_timeout=0` disables only the no-output watchdog.

Timeouts terminate the entire command process group.

## Standard development loop

1. read `SESSION_BOOTSTRAP.md` and inspect root/nearest `AGENTS.md` in the target repository;
2. inspect relevant source/tests;
3. prepare the smallest deterministic patch/write;
4. queue a unique task on `agent-control`;
5. inspect `.agent/status/daemon.json` and `.agent/runs/<id>.json` yourself while it runs; follow the same `attempt_id`/`task_digest` and never infer replay from repeated build output alone;
6. read `.agent/results/<id>.json` when complete;
7. diagnose actual failures and queue the next focused task;
8. broaden verification only after focused gates pass;
9. review the exact diff;
10. publish only validated target source.

For the ESP32 project, use focused host tests first. The broad gate is:

```bash
pio run -c platformio.tests.ini -e test-all-host
```

Never use `pio test` for that repository.

## Progress publication

Local execution state is updated for every event. Remote GitHub progress is intentionally coalesced:

- task start/finish, failures, first command and command/verification phase changes are immediate;
- ordinary successful short-command progress is published at most about once per minute;
- successful long command completion is immediate once it crosses the progress interval;
- long command heartbeat is every five minutes;
- daemon status is health/state telemetry, not a duplicate command stream.

This keeps `.agent/runs/<id>.json` fresh enough for autonomous orchestration without turning a 20-30 command task into dozens of status commits.

## Daemon update and control

For non-trivial daemon changes, use a staging branch, run daemon compile/unit gates, require green GitHub CI, then fast-forward `local-agent/main` to the exact validated SHA. The idle daemon checks `main` every 60 seconds, validates the checkout locally, rolls back bad updates and restarts itself after a good update.

Explicit daemon control uses `.agent/daemon/control.json`. Supported actions are `restart`, `self_update` and `status`; acknowledgements are written to `.agent/daemon/acks/<id>.json` and make each control request idempotent.

After a self-update or restart, verify `.agent/status/daemon.json` reports the expected daemon version and source revision. The user should not need to run `git pull`, `launchctl` or `tail -f` during normal operation.

## Source of truth

1. real local-agent command/result output;
2. target repository source/tests;
3. deterministic progress/status files;
4. ChatGPT analysis.

Never claim a test passed unless the result says it passed.

## Golden-standard reference

Read `GOLDEN_STANDARD.md` for the final infrastructure invariants and audit disposition. Source publication and ESP32 hardware flashing are separate gates; never infer the running firmware commit from repository `main` or semantic firmware version alone.

### Invalid task contract

Malformed task JSON is a terminal queue error, not a retry candidate. The daemon publishes `failure_reason=invalid_task_file` under the filename rejection key, and pending scans check that rejection before parsing so a bad task cannot spam every poll forever. Valid historical filename aliases/prefixes may differ from `task.id`; execution results and claims remain keyed by `task.id`.
