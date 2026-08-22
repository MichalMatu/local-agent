# Local Agent Flow

This file is the canonical execution workflow for ChatGPT-driven development on this repository.

## Trigger

When the user says any equivalent of:

- `uzyj local-agent flow`
- `uzyj naszego flow`
- `zrob to przez local agenta`
- `use local-agent flow`

ChatGPT must read this file and follow it without asking the user to restate the architecture.

If the user also says `autopilot`, `autonomicznie`, `do skutku`, `until green`, or otherwise asks ChatGPT to keep iterating without manual check-ins, ChatGPT must also read and follow `LOCAL_AGENT_AUTOPILOT.md`.

## Roles

### ChatGPT

ChatGPT is the architect and programmer.

ChatGPT must:

- inspect the repository and relevant `AGENTS.md` files;
- diagnose bugs and decide what code should change;
- prepare exact source edits as deterministic patches or full-file writes;
- choose exact build, test, flash, serial, MQTT, Playwright, or other verification commands;
- inspect the real execution result returned by the local agent;
- treat shell/tool output as ground truth;
- iterate on failures by preparing the next deterministic change;
- publish validated source changes to GitHub according to repository policy.

ChatGPT must not delegate source-code decisions to a local LLM.

### Local agent daemon

The local daemon is an executor only.

It must:

- sync tasks from GitHub;
- prepare the disposable local work clone;
- apply ChatGPT-provided patches/writes/deletes exactly;
- execute ChatGPT-provided commands exactly;
- stream real command output;
- collect exit codes, `git status`, and `git diff`;
- publish the result back to GitHub;
- clean the disposable work clone after the task.

The daemon must not invent code changes or reinterpret the requested fix.

## Current architecture

Repository:

- `MichalMatu/esp32s3_LiteGraph`
- normal source branch: `main`
- control branch: `agent-control`

Local paths:

- normal user checkout: `/Users/michal/Documents/PlatformIO/Projects/esp32s3_LiteGraph`
- control clone: `~/agent-workspace/control`
- disposable execution clone: `~/agent-workspace/work`
- daemon: `~/local-agent/agentd.py`
- LaunchAgent: `~/Library/LaunchAgents/com.michal.local-agent.plist`
- daemon log: `~/Library/Logs/local-agent.log`

Daemon v2 is deterministic and does not use Qwen/Ollama in the execution path.

Expected startup log:

```text
Local Agent daemon v2 starting; mode=deterministic command_timeout=7200s
```

## GitHub queue contract

Tasks live on `agent-control`:

```text
.agent/tasks/<task-id>.json
```

Results are published to:

```text
.agent/results/<task-id>.json
```

Use unique monotonically increasing task IDs where practical.

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
  "command_timeout": 7200
}
```

Use only the fields needed for the task.

## Standard development flow

1. Read root `AGENTS.md` and the nearest path-specific `AGENTS.md` files.
2. Inspect the current source on the intended source branch, normally `main`.
3. Diagnose the requested change in ChatGPT.
4. Prepare the smallest cohesive deterministic patch or full-file write.
5. Queue a local-agent task on `agent-control`.
6. Run the smallest focused verification first.
7. Read `.agent/results/<task-id>.json` from `agent-control`.
8. Treat actual command output and exit codes as truth; never substitute model speculation.
9. If focused verification fails, prepare a new deterministic patch/task and iterate.
10. If focused verification passes, broaden verification as appropriate.
11. For shared firmware/runtime/Nodeflow changes, run the full host suite before publication unless a narrower gate is explicitly justified:

```bash
pio run -c platformio.tests.ini -e test-all-host
```

12. Publish validated code according to root `AGENTS.md`. For this solo repository, use `main` directly unless the user explicitly asks for a branch/PR.
13. Report changed files and exact verification commands.

## Important execution rule

Edits made inside `~/agent-workspace/work` are disposable. The daemon resets and cleans this clone after publishing the task result.

Therefore a successful local task does not by itself publish source changes.

After verification, ChatGPT must explicitly publish the validated source change to GitHub, or intentionally include commit/push commands in a task when that is the chosen workflow.

## Focused tests first

Do not run the entire host suite after every tiny edit when a focused target exists.

Typical pattern:

1. apply patch;
2. build/run focused test target;
3. inspect result;
4. only then run the broad suite.

For this project the broad host gate is:

```bash
pio run -c platformio.tests.ini -e test-all-host
```

Never use `pio test` for this repository.

## Hardware execution

When the task requires real hardware, ChatGPT still decides the exact commands and the daemon executes them.

Examples include:

- firmware build;
- firmware upload with PlatformIO;
- serial log capture;
- ESP32 reset/crash reproduction;
- coredump retrieval;
- MQTT publish/subscribe checks;
- REST smoke tests against the board;
- Playwright/browser verification;
- Shelly/Telegram/BLE integration checks.

Follow the live-bench safety and hardware directives from `AGENTS.md`.

For serial monitoring, prefer bounded capture suitable for a task result rather than an indefinite interactive monitor. The daemon command timeout/process-group kill is the safety boundary.

## Source of truth hierarchy

Use this order:

1. real shell/tool/hardware output from the local daemon;
2. repository source and tests;
3. deterministic verification results;
4. ChatGPT analysis;
5. local-model prose, if a local model is ever used experimentally.

Local-model speculation must never override actual tool output.

## Failure handling

If a task fails:

- inspect the exact failed command and exit code;
- inspect `git_diff` and `git_status` from the result;
- distinguish source failure from infrastructure/build-cache/serial/hardware failure;
- do not rerun a broad suite blindly when a smaller diagnostic command can isolate the cause;
- prepare the next deterministic task from ChatGPT.

If a requested edit produces no diff, treat that as a workflow failure rather than silently continuing verification.

## User interaction

The user should not need to manually edit files or re-enter commands unless local bootstrap/recovery is required.

Normally the user may simply say, for example:

```text
Uzyj local-agent flow. Napraw <problem>.
```

or:

```text
Uzyj local-agent flow i sprawdz ten bug na prawdziwej plytce.
```

For an autonomous repair loop, the user may say:

```text
Uzyj local-agent autopilot. Napraw <problem> do skutku, przetestuj i zweryfikuj na plytce.
```

ChatGPT should then operate the GitHub queue and local execution flow directly. In autopilot mode, ChatGPT must not stop after queueing a task; it must follow `LOCAL_AGENT_AUTOPILOT.md` and poll/iterate within the active turn until the requested gates are green or a genuine user-only blocker is reached.

The user may watch execution with:

```bash
tail -f ~/Library/Logs/local-agent.log
```

but watching the log is optional and is not required for task execution.
