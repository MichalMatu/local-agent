# Local Agent Golden Standard v4.2

This is the final infrastructure audit summary for the `MichalMatu/local-agent` + `MichalMatu/esp32s3_LiteGraph` pair. Operational details remain canonical in `SESSION_BOOTSTRAP.md`.

## Invariants

- `agentd.py` is the only daemon entry point.
- The daemon is a deterministic executor, never a coding model.
- One OS-locked daemon instance is allowed.
- Every task has an immutable payload digest and one durable attempt claim.
- A claimed, interrupted, or corrupt-claim task is never automatically replayed.
- Corrupt durable claims are converted to a terminal `corrupt_claim_state` result for a known queued task and quarantined for evidence.
- Command, no-output, and whole-task watchdogs are mandatory.
- SIGTERM/SIGINT terminate the active process group.
- Result publication may be retried, execution may not.
- Self-update is allowed only from a clean `local-agent/main` checkout, accepts fast-forward updates only, validates locally, rolls back failures, then restarts by `exec`.
- The ESP32 user checkout is never reset or cleaned by the daemon. Work happens in `~/agent-workspace/work`.
- Progress/status/results are remotely observable on `esp32s3_LiteGraph/agent-control`.
- Secrets never belong in GitHub tasks, results, runs, logs committed to control, or repository documentation.

## ESP32 product workflow

Default product target is `MichalMatu/esp32s3_LiteGraph/main`. `local-agent` is infrastructure unless explicitly requested otherwise.

Normal loop: inspect source/rules -> focused patch -> focused tests -> broader gates -> exact diff review -> publish target source -> hardware flash when required -> bounded serial capture -> authenticated API/log-tail smoke -> final evidence.

Publishing source is not the same as flashing hardware. Never state that the bench contains a source commit merely because `main` contains it or because the device reports semantic version `0.6.0`. Hardware validation of a new firmware commit requires an explicit successful upload (or an exact build-identity mechanism that proves the running source revision).

Current bench base URL is `http://192.168.0.21`. The serial port must be rediscovered immediately before upload/monitor. Existing observed adapter VID:PID is `1A86:7523`; the observed path `/dev/cu.usbserial-110` is not a permanent identifier.

## Required daemon release gate

For non-trivial daemon changes:

1. branch from current `main` to `v*-staging`;
2. exact source/test/doc change;
3. `python -m py_compile agentd.py agent_core.py agent_runtime.py agentctl.py`;
4. `python -m unittest discover -q`;
5. green GitHub CI on the exact staging SHA;
6. fast-forward `main` to that exact SHA;
7. wait for daemon self-update;
8. verify remote daemon version + `self_revision`;
9. run one real queue smoke task.

## Audit disposition

The v4.2 audit removed the obsolete `agent_OLD.py` entry point and the unused v2 daemon loop from `agent_core.py`, hardened self-update cleanliness/branch checks, added corrupt-claim terminal recovery, and preserved the v4.1 coalesced progress policy.

### Invalid task contract

Malformed task JSON and filename/payload-id mismatches are terminal queue errors, not retry candidates. The daemon publishes `failure_reason=invalid_task_file`, and pending scans check an existing result by filename before parsing so a bad task cannot spam every poll forever.
