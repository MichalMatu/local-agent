# Local Agent Autopilot

Autopilot means ChatGPT owns the orchestration loop until the requested gates are green or a genuine user-only blocker is reached. Versioned infrastructure invariants live in `GOLDEN_STANDARD.md`; this file describes the current operating pattern.

The default product target for this repository pair is `MichalMatu/esp32s3_LiteGraph`. Read `SESSION_BOOTSTRAP.md` at the start of a future local-agent session so the user does not need to restate paths, branches, status files or publication rules.

## Core loop

1. read `SESSION_BOOTSTRAP.md`, then inspect target source and applicable `AGENTS.md` rules;
2. inspect daemon health on `.agent/status/daemon.json` and any existing run/result relevant to the request;
3. create an exact deterministic task;
4. queue it on the remote `agent-control` branch through GitHub/API tooling or another trusted writer checkout;
5. inspect `.agent/runs/<task-id>.json` for live state instead of asking the user for logs;
6. follow the same `attempt_id` and `task_digest`; never queue a duplicate merely because output looks repetitive;
7. read `.agent/results/<task-id>.json` when complete;
8. diagnose the exact failed command/output;
9. prepare the next smallest fix or diagnostic task;
10. repeat until the targeted gates that correspond to the current diff pass;
11. add broader verification only when the changed dependency/integration surface gives it a concrete chance to detect a regression;
12. publish only the validated target diff.

Treat the daemon's local control clone as execution infrastructure, not as the planner's task-authoring checkout during normal operation.

Do not stop merely because a task is running. Remote progress exists specifically so ChatGPT can check state itself.

## Verification selection rule

Autopilot does not use a fixed test ritual. Test selection is impact-driven.

- Every queued test/build command must correspond to a plausible failure mode caused by the current diff, changed configuration, changed dependency or a realistically affected integration boundary.
- Prefer the narrowest target that can detect that failure.
- Do not run unrelated subsystem suites merely because a broad aggregate target includes them.
- A green gate remains valid while the code and dependencies it covers have not changed. Do not rerun it after an unrelated edit.
- A broad regression suite is opt-in. Use it only when the diff changes shared/cross-cutting infrastructure, the dependency blast radius cannot be bounded confidently, the target repository explicitly requires the suite for that change class, or the user explicitly requests it.
- `This is the final iteration` is not by itself a reason to run every test in the repository.

## Failure-loop rules

- compiler error -> fix and rerun the focused build;
- focused test failure -> rerun that focused target after the fix;
- frontend check/build failure -> rerun the frontend gate first;
- firmware build failure -> rerun firmware build, not the entire host suite;
- hardware/runtime failure -> capture bounded serial/HTTP/MQTT evidence before changing code;
- timeout/idle-timeout -> diagnose the blocked command before retrying;
- `interrupted_previous_attempt` -> create a new task id after inspecting the interrupted state; never force replay of the old id.

A broad suite must not be restarted blindly after every edit. If the broad suite already passed relevant portions and the later edit does not affect those portions or their dependencies, do not spend time rerunning them.

## Progress and hang handling

The daemon records every transition locally but coalesces GitHub progress commits: task boundaries, failures, the first command and phase changes are immediate; ordinary short-command progress is limited to about once per minute; successful long command completion is surfaced when it crosses that interval; long-command heartbeat state is periodic.

ChatGPT can inspect:

```text
.agent/status/daemon.json
.agent/runs/<task-id>.json
.agent/results/<task-id>.json
```

The daemon itself enforces command, idle and whole-task watchdogs. A silent or runaway command therefore cannot consume the machine indefinitely within those watchdog boundaries.

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

For a typical ESP32 change, success can require focused host tests, relevant frontend tests/check/build, firmware build, justified broader host coverage when the diff warrants it, hardware validation when requested, exact diff review and publication to `main`.

Do not report completion until the intended source commit is actually on the target branch and the requested gates are evidenced by real results. Do not add unrelated broad tests solely to make completion feel more exhaustive.

## Golden-standard reference

Read `GOLDEN_STANDARD.md` for the current versioned infrastructure invariants and audit disposition. Source publication and ESP32 hardware flashing are separate gates; never infer the running firmware commit from repository `main` or semantic firmware version alone.

### Invalid task contract

Malformed task JSON is a terminal queue error, not a retry candidate. The daemon publishes `failure_reason=invalid_task_file` under the filename rejection key, and pending scans check that rejection before parsing so a bad task cannot spam every poll forever. Valid historical filename aliases/prefixes may differ from `task.id`; execution results and claims remain keyed by `task.id`.
