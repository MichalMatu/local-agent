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

## Current physical ESP32 bench

The current development bench is reachable from the Mac at:

- frontend/API base URL: `http://192.168.0.21`;
- current serial candidate: `/dev/cu.usbserial-110`;
- detected USB serial adapter: VID:PID `1A86:7523`;
- current firmware reports build target `esp32s3-firmware-embedded-web`.

Treat the serial path as a current observation, not a permanent identifier. Always re-run `pio device list` immediately before flashing or serial capture and verify the expected ESP32 adapter is still present.

The frontend root and `GET /rest/features` are suitable unauthenticated reachability probes. When `/rest/features` reports `security=true`, protected endpoints such as `/rest/systemStatus`, `/rest/logging`, `/rest/logs/tail` and `/api/nodeflow/archive/status` require an authenticated bearer token.

Never commit usernames, passwords, bearer tokens or session data to either repository, `.agent/tasks`, `.agent/results` or `.agent/runs`. Device authentication material must stay on the Mac in a local secret store such as macOS Keychain or another non-versioned local mechanism.

## Flash, boot-log and live-API validation flow

For a firmware change targeting the connected bench, after the required source/tests are green:

1. re-detect the serial device with `pio device list`;
2. build the exact intended firmware target;
3. upload with PlatformIO/esptool, explicitly selecting the detected port when ambiguity exists;
4. capture a bounded post-upload serial window rather than leaving an unbounded monitor process running;
5. read the resulting device-monitor log and check for boot loops, panics, watchdog resets, coredump notices and expected startup milestones;
6. wait for `http://192.168.0.21/rest/features` to become reachable again;
7. authenticate locally when security is enabled, without exposing credentials in GitHub control files;
8. inspect `/rest/systemStatus` and the feature-specific status endpoint relevant to the change;
9. inspect `/rest/logs/tail?lines=<n>` for application logs when authenticated;
10. perform the required live smoke test and record the result before calling the change hardware-validated.

The target PlatformIO configuration uses `esptool` uploads. The default environment monitors at `115200` baud with filters `esp32_exception_decoder, log2file`, `monitor_rts=0`, and `monitor_dtr=0`.

PlatformIO serial-monitor output is persisted under the ESP32 project `logs/` directory. Existing examples use names such as:

```text
logs/device-monitor-260819-124048.log
```

After a monitor run, locate/read the newest `logs/device-monitor-*.log`; do not assume a fixed timestamped filename.

For firmware-only iteration where changed UI assets must not be embedded, follow the target repository rules and use `SKIP_FRONTEND=1` for the build/upload path. For UI changes that must ship in firmware, build the UI first and use the normal embedded-web firmware path.

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
