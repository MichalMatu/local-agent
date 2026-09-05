# Session Bootstrap: Local Agent Multi-Repository Mac Deployment

This document records the established machine-specific deployment. It is operational context, not a portable installer.

## Project pairing

When the established Local Agent flow is requested, derive the target repository and source branch from the active conversation goal plus that repository's own instructions. The current machine registry contains:

- `litegraph` -> `MichalMatu/esp32s3_LiteGraph`;
- `growbox-ml-controller` -> `MichalMatu/growbox-ml-controller`;
- `matrixhub` -> `MichalMatu/MatrixHub`;
- `esp32-c6-zigbee` -> `MichalMatu/esp32_c6_zigbee`.

Each repository uses its own `agent-control` branch. The production daemon source is `MichalMatu/local-agent/main`. Only treat `local-agent` itself as the product target when the request explicitly concerns the daemon/infrastructure.

## Local topology

```text
normal LiteGraph checkout: /Users/michal/Documents/PlatformIO/Projects/esp32s3_LiteGraph
registry:                  ~/Library/Application Support/local-agent/repositories.json
LiteGraph control:         ~/agent-workspace/repos/litegraph/control
LiteGraph work:            ~/agent-workspace/repos/litegraph/work
LiteGraph checkpoints:     ~/agent-workspace/repos/litegraph/checkpoints
Growbox control:           ~/agent-workspace/repos/growbox-ml-controller/control
Growbox work:              ~/agent-workspace/repos/growbox-ml-controller/work
Growbox checkpoints:       ~/agent-workspace/repos/growbox-ml-controller/checkpoints
MatrixHub control:         ~/agent-workspace/repos/matrixhub/control
MatrixHub work:            ~/agent-workspace/repos/matrixhub/work
MatrixHub checkpoints:     ~/agent-workspace/repos/matrixhub/checkpoints
ESP32-C6 Zigbee control:   ~/agent-workspace/repos/esp32-c6-zigbee/control
ESP32-C6 Zigbee work:      ~/agent-workspace/repos/esp32-c6-zigbee/work
ESP32-C6 Zigbee checkpoints: ~/agent-workspace/repos/esp32-c6-zigbee/checkpoints
daemon checkout:           ~/local-agent
installed LaunchAgent:     ~/Library/LaunchAgents/com.michal.local-agent.plist
daemon stdout:             ~/Library/Logs/local-agent.log
daemon stderr:             ~/Library/Logs/local-agent-error.log
```

All four current registry entries use the default non-legacy workspace layout derived from their repository ids. The loaded LaunchAgent runs `~/local-agent/agent_entrypoint.py --registry "$HOME/Library/Application Support/local-agent/repositories.json" --max-workers 2` from `~/local-agent`.

The user's normal ESP32 checkout is not the disposable agent worktree. Never reset, clean or overwrite it during normal daemon execution.

Generate the guarded parallel LaunchAgent with `python scripts/macos_launchd.py install --mode parallel --max-workers 2`. The installed service is `~/Library/LaunchAgents/com.michal.local-agent.plist` with label `com.michal.local-agent`. The generator also supports serial rollback configuration; serial and parallel services must never run simultaneously.

## Current ESP32 bench

Observed bench details:

- API/frontend base URL: `http://192.168.0.21`
- observed serial adapter VID:PID: `1A86:7523`
- previously observed serial path: `/dev/cu.usbserial-110`
- firmware target observed: `esp32s3-firmware-embedded-web`

The serial path is not a stable identifier. Rediscover the device immediately before upload or serial capture.

The frontend root and `GET /rest/features` are suitable reachability probes. Protected endpoints require local authentication when device security is enabled. Never place credentials, bearer tokens or session data in Git tasks, results, runs or repository documentation.

## Efficient LiteGraph verification

Use `workflow_policy: "efficient-verification-v1"` for normal LiteGraph coding tasks. Verification must be derived from the changed files and integration boundary rather than defaulting to the repository-wide host suite.

During iteration:

- build and run only the affected host suite or executable;
- reuse the canonical persistent build directory for that suite, for example `build/test/datalogger`, so CMake and ccache can reuse unchanged objects;
- do not create throwaway `*-golden`, `*-audit` or other clean build directories unless a clean/reproducibility check is explicitly required;
- do not delete an existing build directory merely to obtain a clean test run unless stale build artifacts are suspected;
- when a test source is changed or added inside an existing executable, let the normal incremental CMake build recompile only changed translation units and relink that executable;
- if a focused suite fails, rerun only that failing suite while fixing it.

`pio run -c platformio.tests.ini -e test-all-host` is a broad final gate, not an iteration command. Run it at most once after focused verification, and only when the user explicitly requests a full/golden/release gate or when the change is sufficiently cross-cutting that repository-wide host validation is materially justified. A small isolated change such as Nodeflow Archive/datalogger work should normally use the datalogger suite only during development.

For Nodeflow Archive/datalogger changes, prefer the canonical incremental path:

```bash
cmake -S test/host/datalogger -B build/test/datalogger
cmake --build build/test/datalogger -j2
./build/test/datalogger/datalogger_backend_test
```

A full clean build is evidence for reproducibility, not a prerequisite for every code change. Do not run both a separate clean copy of a suite and then `test-all-host` unless that duplicate compilation is explicitly justified.

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
4. inspect daemon status and any relevant existing run/result on the target repository's `agent-control`;
5. when Chrome Chat Bridge autonomy is active, also read `docs/AUTONOMOUS_CHAT_LOOP.md` and follow one active task for the current conversation goal while allowing unrelated repository work to use normal resource-aware executor concurrency;
6. follow an existing active attempt instead of queuing a duplicate;
7. classify task resources conservatively before queueing work;
8. derive verification from the actual diff and affected integration boundaries;
9. prefer `efficient-verification-v1` with focused incremental verification before any broad final gate;
10. publish only the exact validated target changes.

The user should not need to paste live daemon logs during normal operation when remote run/status/result evidence is available.
