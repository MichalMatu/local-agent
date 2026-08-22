# Local Agent Autopilot

This file extends `LOCAL_AGENT_FLOW.md` with the autonomous iteration contract.

## Trigger

When the user says any equivalent of:

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
2. queue the local-agent task;
3. poll `.agent/results/<task-id>.json` on `agent-control` until it is published;
4. inspect actual exit codes, command output, `git_status`, and `git_diff`;
5. if verification failed, diagnose the real failure in ChatGPT;
6. prepare the next deterministic patch/task;
7. repeat until the requested verification is green;
8. broaden verification progressively: focused test -> relevant suite/build -> full host suite when appropriate -> hardware flash/runtime checks when requested;
9. publish only the validated source change.

The user should not need to paste daemon logs or say `sprawdz` between iterations.

## When to stop and ask the user

Stop the autonomous loop only when one of these is true:

- a physical action is required, such as reconnecting hardware, moving a wire, pressing a button, or supplying a missing device;
- an ambiguous product/behavior decision cannot be resolved safely from repository context;
- credentials, secrets, or permissions unavailable to the agent are required;
- the next operation is materially destructive or outside the authorized scope;
- repeated evidence indicates an infrastructure failure that cannot be corrected from code/tasks;
- the user explicitly asks to pause.

Normal compiler errors, test failures, lint/type errors, missing includes/imports, deterministic patch mismatches, endpoint mismatches, and ordinary firmware build failures are NOT reasons to ask the user. Diagnose and iterate autonomously.

## Task construction rules

Keep task JSON small and mechanically valid.

For substantial edits:

- store the deterministic patching script or patch as a separate file under `.agent/patches/` on `agent-control`;
- make the task JSON reference that file with a short command;
- do not embed very large Python/heredoc programs inside JSON command strings;
- use exact `json.dumps`/structured serialization when generating JSON rather than hand-escaping large payloads;
- verify the task JSON is parseable before considering it queued.

If an invalid task file is discovered, replace/remove it promptly so the daemon does not repeat the same parse error every poll.

## Failure-loop policy

Use the smallest useful retry after each failure.

Examples:

- compiler error in one translation unit -> fix it and rerun the focused build first;
- focused host test failure -> fix and rerun only that test first;
- frontend type/lint error -> rerun the relevant frontend gate first;
- firmware link/build failure -> rerun firmware build, not the full host suite;
- hardware runtime failure -> capture bounded serial/HTTP/MQTT evidence before changing code.

Do not restart an expensive broad suite from scratch unless the preceding focused gate is green.

Treat actual compiler/test/hardware output as ground truth. Never invent a diagnosis from model prose when the shell output says otherwise.

## Cache and retries

Preserve ignored build/cache directories unless a clean rebuild is specifically required. The disposable work clone may be reset/cleaned, but normal `git clean -fd` must not remove ignored PlatformIO/CMake caches. Reuse them to make autonomous iterations faster.

## Hardware autopilot

When the user has already stated that the board is connected and the requested task includes hardware validation, continue automatically through the safe hardware stages after software gates pass:

1. build firmware;
2. detect/confirm the expected serial/upload port using local commands;
3. upload with the repository-approved PlatformIO command;
4. capture bounded serial output;
5. run relevant REST/MQTT/browser smoke checks when applicable;
6. analyze the evidence and iterate if necessary.

Do not require the user to watch `tail -f`; local logs are optional observability only.

## Chat/session limitation

This autopilot loop is autonomous while the ChatGPT turn is active. The local daemon can continue running after the turn ends, but the daemon cannot by itself wake this exact ChatGPT conversation and request a new code decision.

Therefore ChatGPT should keep the turn active and poll results instead of ending the response while an expected build/test result is still pending.

A truly unattended loop that continues after the ChatGPT turn has ended would require a separate callable model/orchestrator endpoint outside this chat session. Do not claim that the current chat can do background reasoning after its turn ends.

## Completion criteria

Do not report success until all requested gates are actually green.

For a typical Nodeflow firmware change this may mean:

- focused host tests green;
- relevant frontend tests/check/build green;
- firmware build green;
- full `pio run -c platformio.tests.ini -e test-all-host` green when warranted;
- firmware upload green when hardware validation was requested;
- bounded serial/runtime smoke evidence consistent with the requested behavior;
- final diff reviewed and limited to intended files;
- validated source published according to repository policy.
