# Session Bootstrap: ESP32 LiteGraph + Local Agent

This file is the canonical cross-repository bootstrap contract for future ChatGPT sessions.

## Default project pairing

When the user provides or references `MichalMatu/local-agent`, says to use the local-agent flow, or asks to continue the established autonomous workflow, assume the default development target is:

- target repository: `MichalMatu/esp32s3_LiteGraph`;
- target source branch: `main`;
- target control branch: `agent-control`;
- execution infrastructure repository: `MichalMatu/local-agent`;
- daemon source branch: `main`.

Only treat `local-agent` itself as the product target when the user explicitly asks to modify, audit or debug the daemon/infrastructure.

## Local topology

- user ESP32 checkout: `/Users/michal/Documents/PlatformIO/Projects/esp32s3_LiteGraph`;
- control clone: `~/agent-workspace/control`;
- disposable execution clone: `~/agent-workspace/work`;
- daemon checkout: `~/local-agent`;
- LaunchAgent: `~/Library/LaunchAgents/com.michal.local-agent.plist`;
- daemon log: `~/Library/Logs/local-agent.log`.

The user checkout is not the disposable agent worktree. Never reset, clean or overwrite the user checkout as part of normal local-agent execution.

## Session bootstrap sequence

At the start of a future session using this flow:

1. read this file, root `AGENTS.md`, `LOCAL_AGENT_FLOW.md` and, for autonomous work, `LOCAL_AGENT_AUTOPILOT.md`;
2. inspect `MichalMatu/esp32s3_LiteGraph/main` and read its root `AGENTS.md` plus the nearest path-specific `AGENTS.md`;
3. inspect `esp32s3_LiteGraph/agent-control:.agent/status/daemon.json`;
4. inspect any relevant `.agent/runs/<task-id>.json` and `.agent/results/<task-id>.json`;
5. if a task is already running, follow its `attempt_id` and `task_digest` instead of queueing a duplicate;
6. queue unique deterministic tasks under `.agent/tasks/`;
7. run focused verification first, then broaden only after the focused gate is green;
8. publish the exact validated ESP32 diff to `main`; never treat a successful disposable-worktree test as publication by itself.

The user should not need to paste `tail -f` output during normal operation. ChatGPT should inspect remote status/run/result files itself.

## ESP32 verification defaults

Follow the target repository rules. In particular:

- never use `pio test`;
- broad host gate: `pio run -c platformio.tests.ini -e test-all-host`;
- UI changes normally require relevant Vitest coverage, `npm run lint`, `npm run check`, and `npm run build`;
- hardware validation is performed when requested or required by the target repository contract;
- commit/push only intended files and never use broad staging such as `git add -A`.

## Daemon observability

On `esp32s3_LiteGraph/agent-control`:

```text
.agent/status/daemon.json
.agent/runs/<task-id>.json
.agent/results/<task-id>.json
.agent/daemon/control.json
.agent/daemon/acks/<control-id>.json
```

`attempt_id` identifies one execution attempt. `task_digest` identifies the immutable task payload. A claimed/interrupted task is never automatically replayed.

## Daemon maintenance flow

For non-trivial `local-agent` changes:

1. create/update a staging branch from current `local-agent/main`;
2. make deterministic source/test/doc changes;
3. run `python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py`;
4. run `python -m unittest discover -q`;
5. require green GitHub CI on staging;
6. fast-forward `local-agent/main` to the exact validated SHA;
7. let the idle daemon self-update from `main`;
8. verify `.agent/status/daemon.json` reports the expected `daemon_version` and `self_revision`;
9. use remote `status`, `self_update` or `restart` control only when needed and verify the durable ACK.

The daemon validates a self-update locally and rolls back a bad update. `launchd` remains the outer supervisor.

## Progress publication policy

Local state is updated on every execution transition. GitHub progress is deliberately coalesced to avoid turning every short command into multiple commits:

- task start and task finish: immediate;
- first command and phase changes: immediate;
- normal command transitions: at most about once per minute;
- successful long command completion: immediate when the command lasted at least the progress interval;
- failures: immediate;
- long-running heartbeat: every five minutes;
- daemon health: state changes plus a five-minute heartbeat.

Detailed task progress belongs in `.agent/runs/<task-id>.json`; `.agent/status/daemon.json` is daemon health/state rather than a per-command log.

## Source of truth

Use this order:

1. local-agent result and command output;
2. target repository source/tests;
3. remote run/daemon status;
4. ChatGPT analysis.

Do not claim success until the requested gates are actually green and the intended source has been published.
