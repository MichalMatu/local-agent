# Local Agent Golden Standard v4.2

This is the final infrastructure audit summary for the `MichalMatu/local-agent` + `MichalMatu/esp32s3_LiteGraph` pair. Operational details remain canonical in `SESSION_BOOTSTRAP.md`.

## Invariants

- `agentd.py` is the only daemon entry point.
- The daemon is a deterministic executor, never a coding model.
- One OS-locked daemon instance is allowed.
- Every task has an immutable payload digest and one durable attempt claim.
- A claimed, interrupted, or corrupt-claim task is never automatically replayed.
- Corrupt durable claims are converted to a terminal `corrupt_claim_state` result for a known queued task and quarantined for evidence.
- Malformed task JSON and filename/payload-id mismatches are terminal `invalid_task_file` failures; they are never retried and may not spam every poll forever.
- Command, no-output, and whole-task watchdogs are mandatory.
- SIGTERM/SIGINT terminate the active process group.
- Result publication may be retried, execution may not.
- Self-update is allowed only from a clean `local-agent/main` checkout, accepts fast-forward updates only, validates locally, rolls back failures, then restarts by `exec`.
- The live daemon checkout is never mutated to prepare a daemon release. Release staging happens in a separate temporary clone.
- The ESP32 user checkout is never reset or cleaned by the daemon. Work happens in `~/agent-workspace/work`.
- Progress/status/results are remotely observable on `esp32s3_LiteGraph/agent-control`.
- Secrets never belong in GitHub tasks, results, runs, logs committed to control, or repository documentation.

## ESP32 product workflow

Default product target is `MichalMatu/esp32s3_LiteGraph/main`. `local-agent` is infrastructure unless explicitly requested otherwise.

Normal loop: inspect source/rules -> focused patch -> focused tests -> broader gates -> exact diff review -> publish target source -> hardware flash when required -> bounded serial capture -> authenticated API/log-tail smoke -> final evidence.

Publishing source is not the same as flashing hardware. Never state that the bench contains a source commit merely because `main` contains it or because the device reports semantic version `0.6.0`. Hardware validation of a new firmware commit requires an explicit successful upload or an exact build-identity mechanism that proves the running source revision.

Current bench base URL is `http://192.168.0.21`. The serial port must be rediscovered immediately before upload/monitor. Existing observed adapter VID:PID is `1A86:7523`; the observed path `/dev/cu.usbserial-110` is not a permanent identifier.

For future ESP32 work, adding an exact firmware source/build revision to `/rest/features` or `/rest/systemStatus` is desirable because it lets ChatGPT prove which commit is actually running after a flash.

## Required daemon release gate

For non-trivial daemon changes:

1. create a fresh temporary clone from current `local-agent/main` and create/update `v*-staging` there; never checkout staging in the live `~/local-agent` daemon directory;
2. make deterministic source/test/doc changes in that isolated clone;
3. run `python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py`;
4. run `python -m unittest discover -q`;
5. review the exact staged diff and paths;
6. push the staging SHA and require green GitHub CI on that exact SHA;
7. fast-forward `main` to exactly the validated SHA, never force it;
8. let the idle daemon self-update from `main`;
9. verify remote `daemon_version` and `self_revision`;
10. run one real queue smoke task through `agent-control` and require a terminal green result.

## Audit disposition

The v4.2 audit:

- removed obsolete `agent_OLD.py`;
- removed the unused v2 daemon loop from `agent_core.py` so `agentd.py` is the only daemon entry point;
- hardened self-update to require a clean `main` checkout;
- added terminal recovery/quarantine for corrupt durable claims;
- added terminal handling for malformed task files and filename/id mismatches;
- preserved command, idle and whole-task watchdogs plus process-group termination;
- preserved v4.1 coalesced progress publication;
- formalized isolated release staging and the distinction between published ESP32 source and flashed/running firmware.

## Invalid task contract

Malformed task JSON and filename/payload-id mismatches are terminal queue errors, not retry candidates. The daemon publishes `failure_reason=invalid_task_file`, and pending scans check an existing result by filename before parsing so a bad task cannot spam every poll forever.
