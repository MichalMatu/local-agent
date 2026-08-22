# Local Agent Autopilot v4

Autopilot means ChatGPT owns the orchestration loop until the requested gates are green or a genuine user-only blocker is reached.

## Core loop

1. inspect target source and rules;
2. create an exact deterministic task;
3. queue it on `agent-control`;
4. inspect `.agent/runs/<task-id>.json` for live state instead of asking the user for logs;
5. read `.agent/results/<task-id>.json` when complete;
6. diagnose the exact failed command/output;
7. prepare the next smallest fix or diagnostic task;
8. repeat until focused gates pass;
9. broaden gates progressively;
10. publish only the validated target diff.

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

The daemon publishes command transitions immediately and long-command heartbeat state periodically. ChatGPT can inspect:

```text
.agent/status/daemon.json
.agent/runs/<task-id>.json
```

The daemon itself enforces command, idle and whole-task watchdogs. A silent or runaway command therefore cannot consume the machine indefinitely.

## Daemon maintenance during autopilot

ChatGPT may improve `MichalMatu/local-agent` when execution infrastructure itself is the blocker. The daemon self-updates only while idle, validates the new checkout and rolls back failed updates before they become the long-running version.

ChatGPT may request `restart`, `self_update` or `status` through `.agent/daemon/control.json`; durable acknowledgements prevent repeating the same control request.

## User interaction

Ask the user only for actions that cannot be performed remotely: reconnecting hardware, moving wires, pressing a physical button, supplying unavailable credentials, or resolving a truly ambiguous product decision.

The user does not need to watch `tail -f` for normal operation.

## Completion

For a typical ESP32 change, success can require focused host tests, relevant frontend tests/check/build, firmware build, broad host suite when warranted, hardware validation when requested, exact diff review and publication to `main`.
