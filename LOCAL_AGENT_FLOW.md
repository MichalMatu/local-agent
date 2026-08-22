# Local Agent Flow

This file is the canonical execution workflow for ChatGPT-driven development with the local deterministic agent.

## Trigger

When the user says an equivalent of:

- `uzyj local-agent flow`
- `uzyj naszego flow`
- `zrob to przez local agenta`
- `use local-agent flow`

ChatGPT must read this file and follow it without asking the user to restate the architecture.

If the user also asks for `autopilot`, `autonomicznie`, `do skutku`, `until green`, or equivalent behavior, ChatGPT must also read and follow `LOCAL_AGENT_AUTOPILOT.md`.

## Roles

### ChatGPT

ChatGPT is the architect and programmer.

ChatGPT must:

- inspect the target repository and relevant `AGENTS.md` files;
- diagnose bugs and decide what source code should change;
- prepare exact deterministic patches, writes, deletes, and verification commands;
- inspect real daemon results and treat shell/tool/hardware output as ground truth;
- iterate from focused verification to broader gates;
- publish only validated source changes according to the target repository policy.

ChatGPT must not delegate source-code decisions to a local LLM.

### Local agent daemon

The daemon is an executor only.

It must:

- sync tasks from GitHub;
- prepare the disposable local work clone;
- apply ChatGPT-provided deterministic changes exactly;
- execute exact commands and stream real output;
- collect exit codes, `git status`, and `git diff`;
- publish results back to GitHub;
- clean the disposable work clone after each task.

The daemon must not invent code changes or reinterpret the requested fix.

## Current architecture

Target firmware repository:

- `MichalMatu/esp32s3_LiteGraph`
- normal source branch: `main`
- control branch: `agent-control`

Local paths:

- normal user checkout: `/Users/michal/Documents/PlatformIO/Projects/esp32s3_LiteGraph`
- control clone: `~/agent-workspace/control`
- disposable execution clone: `~/agent-workspace/work`
- local-agent repository: `~/local-agent`
- daemon entry point: `~/local-agent/agentd.py`
- deterministic execution core: `~/local-agent/agent_core.py`
- LaunchAgent: `~/Library/LaunchAgents/com.michal.local-agent.plist`
- daemon log: `~/Library/Logs/local-agent.log`
- daemon state: `~/Library/Application Support/local-agent`

Daemon v3 is deterministic and does not use Qwen/Ollama in the execution path.

Expected startup log:

```text
Local Agent daemon v3 starting; mode=deterministic command_timeout=1200s self_update=60s
```

## Replay and process safety

Daemon v3 has durable execution ownership.

Before running a task it atomically creates a claim under:

```text
~/Library/Application Support/local-agent/claims/
```

A task ID with an existing claim must never be executed again automatically.

If the daemon or Mac stops while a claimed task is running, the next daemon instance publishes a terminal result with:

```text
failure_reason = interrupted_previous_attempt
```

and does not replay the commands. A retry must use a new task ID after ChatGPT has inspected the failure.

The daemon also holds an exclusive process lock at:

```text
~/Library/Application Support/local-agent/agentd.lock
```

so only one daemon instance can own the queue at a time.

Command timeouts are bounded:

- default per-command timeout: `1200` seconds;
- maximum accepted per-command timeout: `3600` seconds;
- timed-out command process groups are terminated by the execution core.

Do not use multi-hour command timeouts to hide a hung build or test.

## Self-update

The daemon checks `MichalMatu/local-agent` `main` for updates approximately every 60 seconds, only between tasks.

Self-update rules:

1. do nothing while a task is executing;
2. refuse to update over tracked local changes;
3. fetch `origin/main`;
4. accept only a fast-forward update;
5. pull with `--ff-only`;
6. validate the installed code with `py_compile` and `test_agentd.py` when present;
7. on validation failure, reset to the previous known-good commit and remember the rejected SHA so it is not retried every minute;
8. on success, replace the daemon process with the new `agentd.py` using the same Python interpreter;
9. the macOS LaunchAgent remains the outer supervisor (`KeepAlive=true`).

This means that after the one-time installation of daemon v3, future changes pushed to the local-agent repository can install themselves without the user manually running `git pull` or restarting the service.

## GitHub queue contract

Tasks live on the target repository `agent-control` branch:

```text
.agent/tasks/<task-id>.json
```

Results are published to:

```text
.agent/results/<task-id>.json
```

Use a unique monotonically increasing task ID for every execution attempt.
Never reuse the same ID for a retry after an interrupted or failed attempt.

Typical deterministic task schema:

```json
{
  "id": "example-013",
  "mode": "commands",
  "work_branch": "main",
  "allow_write": true,
  "patch": "<optional unified diff>",
  "writes": [
    {
      "path": "relative/path/to/file",
      "content": "complete file contents"
    }
  ],
  "deletes": [],
  "commands": [
    "<exact command 1>",
    "<exact command 2>"
  ],
  "verify_commands": [
    "<optional exact verification command>"
  ],
  "command_timeout": 1200
}
```

Use only fields needed by the task. Omit `command_timeout` when the 1200-second default is appropriate.

## Standard development flow

1. Read root `AGENTS.md` and the nearest path-specific `AGENTS.md` files.
2. Inspect current source on the intended branch, normally `main`.
3. Diagnose the requested change in ChatGPT.
4. Prepare the smallest cohesive deterministic patch or full-file write.
5. Queue a task on `agent-control` with a new task ID.
6. Run the smallest focused verification first.
7. Read `.agent/results/<task-id>.json` from `agent-control`.
8. Treat actual command output and exit codes as truth.
9. If verification fails, diagnose it and create a new deterministic task with a new ID.
10. Broaden verification only after focused gates pass.
11. For shared firmware/runtime/Nodeflow changes, run the full host suite before publication unless a narrower gate is explicitly justified:

```bash
pio run -c platformio.tests.ini -e test-all-host
```

12. Publish validated code according to the target repository policy. For the solo firmware repository, use `main` directly unless the user explicitly requests a branch or PR.
13. Report the changed files, commit, and exact verification performed.

## Important execution rule

Edits made inside `~/agent-workspace/work` are disposable. The daemon resets and cleans this clone after a task result is produced.

Therefore a successful local task does not by itself publish target source changes. ChatGPT must explicitly publish the validated source change, or deliberately include exact commit/push commands in the task when that is the chosen workflow.

## Focused tests first

Do not run the entire host suite after every tiny edit when a focused target exists.

Typical pattern:

1. apply patch;
2. build/run focused test;
3. inspect result;
4. fix locally with a new task if necessary;
5. only then run the broad suite.

For the firmware repository the broad host gate is:

```bash
pio run -c platformio.tests.ini -e test-all-host
```

Never use `pio test` for that repository.

A broad gate that greatly exceeds its known normal duration should be treated as a possible infrastructure/test hang. Do not blindly restart the same expensive command. Capture the current evidence and diagnose first.

## Hardware execution

When a task requires real hardware, ChatGPT still decides the exact commands and the daemon executes them.

Examples include firmware build/upload, bounded serial capture, crash reproduction, coredump retrieval, MQTT checks, REST smoke tests, browser verification, and device integration checks.

Prefer bounded captures instead of indefinite interactive monitors. The daemon timeout/process-group termination is the final execution safety boundary.

## Source of truth hierarchy

Use this order:

1. real shell/tool/hardware output from the local daemon;
2. repository source and tests;
3. deterministic verification results;
4. ChatGPT analysis;
5. local-model prose, if a local model is ever used experimentally.

Model speculation must never override actual tool output.

## Failure handling

If a task fails:

- inspect the exact failed command and exit code;
- inspect `git_diff` and `git_status` from the result;
- distinguish source failure from infrastructure/build-cache/serial/hardware failure;
- do not rerun a broad suite blindly when a smaller diagnostic command can isolate the cause;
- use a new task ID for every retry;
- treat `interrupted_previous_attempt` as terminal for that task ID and diagnose before retrying.

If a requested edit produces no diff, treat that as a workflow failure rather than silently continuing verification.

## User interaction

The user should not need to manually edit files or re-enter commands unless local bootstrap/recovery or a physical action is genuinely required.

The user may watch execution with:

```bash
tail -f ~/Library/Logs/local-agent.log
```

but watching the log is optional and is not required for execution.
