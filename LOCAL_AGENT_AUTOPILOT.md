# Local Agent Autopilot

This file extends `LOCAL_AGENT_FLOW.md` with the autonomous iteration contract.

## Trigger

When the user says an equivalent of:

- `uzyj local-agent autopilot`
- `uzyj local-agent flow w autopilocie`
- `zrob autonomicznie przez local agenta`
- `napraw do skutku przez local agenta`
- `autopilot until green`

ChatGPT must read both `LOCAL_AGENT_FLOW.md` and this file and follow them without asking the user to restate the architecture.

## Core rule

Do not stop merely because a local task was queued or because a build/test is still running.

Within the active ChatGPT turn, keep the orchestration loop alive:

1. inspect source and prepare an exact deterministic patch/write;
2. queue a local-agent task with a new unique task ID;
3. poll `.agent/results/<task-id>.json` on `agent-control` until it is published;
4. inspect actual exit codes, command output, `git_status`, and `git_diff`;
5. if verification failed, diagnose the real failure in ChatGPT;
6. prepare the smallest useful next deterministic patch/task using a new task ID;
7. repeat until the requested verification is green;
8. broaden verification progressively: focused test -> relevant suite/build -> full host suite when appropriate -> hardware checks when requested;
9. publish only validated source changes.

The user should not need to paste daemon logs or say `sprawdz` between normal iterations.

## Replay-safe retry rule

Daemon v3 claims a task ID before executing its commands.

Never reuse an existing task ID for a retry.

If the result contains:

```text
failure_reason = interrupted_previous_attempt
```

that attempt is terminal. The daemon intentionally blocked automatic replay because the previous process ended while the task was running.

ChatGPT must:

1. inspect the available result/log/source evidence;
2. decide whether a retry is appropriate;
3. queue a new task with a new ID and the smallest useful diagnostic or verification command.

Do not delete a claim merely to force the same task to run again.

## When to stop and ask the user

Stop the autonomous loop only when one of these is true:

- a physical action is required, such as reconnecting hardware, moving a wire, pressing a button, or supplying a missing device;
- an ambiguous product/behavior decision cannot be resolved safely from repository context;
- credentials, secrets, or permissions unavailable to the agent are required;
- the next operation is materially destructive or outside the authorized scope;
- repeated evidence indicates an infrastructure failure that cannot be corrected from code/tasks;
- the user explicitly asks to pause.

Normal compiler errors, test failures, lint/type errors, missing includes/imports, deterministic patch mismatches, endpoint mismatches, and ordinary firmware build failures are not reasons to ask the user. Diagnose and iterate autonomously.

## Task construction rules

Keep task JSON small and mechanically valid.

For substantial edits:

- store deterministic patching scripts or patches under `.agent/patches/` on `agent-control`;
- make the task JSON reference that file with a short exact command;
- do not embed large Python/heredoc programs inside JSON command strings;
- use structured JSON serialization rather than hand-escaping large payloads;
- verify task JSON is parseable before considering it queued;
- use the default `1200` second command timeout unless a specific command legitimately requires more;
- never set a timeout above the daemon maximum of `3600` seconds.

If an invalid task file is discovered, replace/remove it promptly so the daemon does not report the same parse failure every poll.

## Failure-loop policy

Use the smallest useful retry after each failure.

Examples:

- compiler error in one translation unit -> fix it and rerun the focused build first;
- focused host test failure -> fix and rerun only that test first;
- frontend type/lint error -> rerun the relevant frontend gate first;
- firmware link/build failure -> rerun firmware build, not the full host suite;
- hardware runtime failure -> capture bounded serial/HTTP/MQTT evidence before changing code;
- broad suite appears hung -> do not blindly start the same suite again; inspect duration, active process/output, and isolate the stuck target first.

Do not restart an expensive broad suite from scratch unless the preceding focused gate is green and a new full run is actually justified.

Treat actual compiler/test/hardware output as ground truth. Never invent a diagnosis from model prose when shell output says otherwise.

## Cache and retries

Preserve ignored build/cache directories unless a clean rebuild is specifically required. The disposable work clone may be reset/cleaned, but normal `git clean -fd` must not remove ignored PlatformIO/CMake caches. Reuse caches to make autonomous iterations faster.

## Daemon self-update

Daemon v3 updates its own `MichalMatu/local-agent` checkout independently of target-project tasks.

The self-update check runs only between tasks. It accepts only a clean fast-forward from `origin/main`, validates the new daemon code, rolls back a failed update, remembers rejected SHAs, and restarts the daemon process after a valid update.

Do not use target-project task commands to modify `~/local-agent` during normal operation. Publish local-agent changes to its own `main`; the daemon self-update mechanism is the deployment path after the one-time v3 bootstrap.

## Hardware autopilot

When the user has already stated that the board is connected and the requested task includes hardware validation, continue automatically through safe hardware stages after software gates pass:

1. build firmware;
2. detect/confirm the expected serial/upload port using local commands;
3. upload with the repository-approved PlatformIO command;
4. capture bounded serial output;
5. run relevant REST/MQTT/browser smoke checks when applicable;
6. analyze evidence and iterate if necessary.

Do not require the user to watch `tail -f`; logs are optional observability only.

## Chat/session limitation

This autopilot loop is autonomous while the ChatGPT turn is active. The local daemon can continue executing deterministic tasks after the turn ends, but it cannot by itself wake this exact ChatGPT conversation and request a new programming decision.

Therefore ChatGPT should keep the turn active and poll expected task results instead of ending a response merely because a build/test is still pending.

A truly unattended reasoning loop after the chat turn ends would require a separate callable model/orchestrator endpoint. Do not claim that the current chat performs background reasoning after its turn ends.

## Completion criteria

Do not report success until requested gates are actually green.

For a typical Nodeflow firmware change this may mean:

- focused host tests green;
- relevant frontend tests/check/build green;
- firmware build green;
- full `pio run -c platformio.tests.ini -e test-all-host` green when warranted;
- firmware upload green when hardware validation was requested;
- bounded serial/runtime smoke evidence consistent with requested behavior;
- final diff reviewed and limited to intended files;
- validated source published according to repository policy.
