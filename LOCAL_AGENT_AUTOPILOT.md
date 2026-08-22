# Local Agent Autopilot v4.1

Autopilot means ChatGPT owns the orchestration loop until the requested gates are green or a genuine user-only blocker is reached.

The default product target for this repository pair is `MichalMatu/esp32s3_LiteGraph`. Read `SESSION_BOOTSTRAP.md` at the start of a future local-agent session so the user does not need to restate paths, branches, status files or publication rules.

## Core loop

1. read `SESSION_BOOTSTRAP.md`, then inspect target source and applicable `AGENTS.md` rules;
2. inspect daemon health on `.agent/status/daemon.json` and any existing run/result relevant to the request;
3. create an exact deterministic task;
4. queue it on `agent-control`;
5. inspect `.agent/runs/<task-id>.json` for live state instead of asking the user for logs;
6. follow the same `attempt_id` and `task_digest`; never queue a duplicate merely because output looks repetitive;
7. read `.agent/results/<task-id>.json` when complete;
8. diagnose the exact failed command/output;
9. prepare the next smallest fix or diagnostic task;
10. repeat until focused gates pass;
11. broaden gates progressively;
12. publish only the validated target diff.

Do not stop merely because a task is running. Remote progress exists specifically so ChatGPT can check state itself.

## Failure-loop rules

- compiler error -> fix and rerun the focused build;
- focused test failure -> rerun that focused target after the fix;
- frontend check/build failure -> rerun the frontend gate first;
- firmware build failure -> rerun firmware build, not the entire host suite;
- hardware/runtime failure -> capture bounded serial/HTTP/MQTT evidence before changing code;
- timeout/idle-timeout -> diagnose the blocked command before retrying;
- `interrupted_previous_attempt` -> create a new task id after inspecting the interrupted state; never force replay of the old id.

A broad suite must not be restarted blindly after every edit.

## Progress and hang handling

The daemon records every transition locally but coalesces GitHub progress commits: task boundaries, failures, the first command and phase changes are immediate; ordinary short-command progress is limited to about once per minute; successful long command completion is surfaced when it crosses that interval; long-command heartbeat state is periodic.

ChatGPT can inspect:

```text
.agent/status/daemon.json
.agent/runs/<task-id>.json
.agent/results/<task-id>.json
```

The daemon itself enforces command, idle and whole-task watchdogs. A silent or runaway command therefore cannot consume the machine indefinitely.

`.agent/status/daemon.json` is health/state telemetry. `.agent/runs/<task-id>.json` is the detailed execution stream. Do not duplicate each command boundary into both files.

## Daemon maintenance during autopilot

ChatGPT may improve `MichalMatu/local-agent` when execution infrastructure itself is the blocker. For non-trivial daemon work, use staging -> compile/unit tests -> green GitHub CI -> fast-forward `main` -> daemon self-update -> remote version/revision verification.

The daemon self-updates only while idle, validates the new checkout and rolls back failed updates before they become the long-running version.

ChatGPT may request `restart`, `self_update` or `status` through `.agent/daemon/control.json`; durable acknowledgements prevent repeating the same control request.

Normal daemon maintenance should not require the user to run `git pull`, restart LaunchAgent manually or paste daemon logs.

## User interaction

Ask the user only for actions that cannot be performed remotely: reconnecting hardware, moving wires, pressing a physical button, supplying unavailable credentials, or resolving a truly ambiguous product decision.

The user does not need to watch `tail -f` for normal operation.

## Completion

For a typical ESP32 change, success can require focused host tests, relevant frontend tests/check/build, firmware build, broad host suite when warranted, hardware validation when requested, exact diff review and publication to `main`.

Do not report completion until the intended source commit is actually on the target branch and the requested gates are evidenced by real results.
