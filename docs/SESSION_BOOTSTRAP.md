# Session Bootstrap: ESP32 LiteGraph + Local Agent

This document records the established machine-specific deployment. It is operational context, not a portable installer.

## Project pairing

When the established local-agent flow is requested, default to:

- target: `MichalMatu/esp32s3_LiteGraph`
- target source branch: `main`
- target control branch: `agent-control`
- daemon: `MichalMatu/local-agent/main`

Only treat `local-agent` itself as the product target when the request explicitly concerns the daemon/infrastructure.

## Local topology

```text
/Users/michal/Documents/PlatformIO/Projects/esp32s3_LiteGraph
~/agent-workspace/control
~/agent-workspace/work
~/agent-workspace/checkpoints
~/local-agent
~/Library/LaunchAgents/com.michal.local-agent.plist
~/Library/Logs/local-agent.log
```

The user's normal ESP32 checkout is not the disposable agent worktree. Never reset, clean or overwrite it during normal daemon execution.

The repository copy of the LaunchAgent now lives at `deploy/macos/com.michal.local-agent.plist`. It contains machine-specific paths and is documentation of the established installation, not a generic installer.

## Current ESP32 bench

Observed bench details:

- API/frontend base URL: `http://192.168.0.21`
- observed serial adapter VID:PID: `1A86:7523`
- previously observed serial path: `/dev/cu.usbserial-110`
- firmware target observed: `esp32s3-firmware-embedded-web`

The serial path is not a stable identifier. Rediscover the device immediately before upload or serial capture.

The frontend root and `GET /rest/features` are suitable reachability probes. Protected endpoints require local authentication when device security is enabled. Never place credentials, bearer tokens or session data in Git tasks, results, runs or repository documentation.

## Hardware validation sequence

For a firmware change that requires bench validation:

1. rediscover the serial device;
2. build the intended firmware target;
3. upload to the detected device;
4. capture a bounded post-upload serial window;
5. inspect the persisted device-monitor log for panics, resets and expected startup milestones;
6. wait for the API to become reachable again;
7. authenticate locally when required;
8. inspect system/application status relevant to the change;
9. run the requested live smoke test;
10. record evidence before claiming hardware validation.

Publishing source to `main` is not proof that the connected board is running that source revision.

## Session startup

For future work using this deployment:

1. read root `AGENTS.md`;
2. read `docs/OPERATIONS.md`;
3. inspect the target repository's applicable `AGENTS.md` files;
4. inspect daemon status and any relevant existing run/result on `agent-control`;
5. follow an existing active attempt instead of queuing a duplicate;
6. derive verification from the actual diff and affected integration boundaries;
7. publish only the exact validated target changes.

The user should not need to paste live daemon logs during normal operation when remote run/status/result evidence is available.
