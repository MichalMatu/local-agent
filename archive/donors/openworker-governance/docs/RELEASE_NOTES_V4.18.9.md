# Local Agent 4.18.9

## Control synchronization watchdog fix

Live inspection on 2026-09-07 showed repeated quiescent-lease warnings after
4.18.8 started. During those observations the actual holders were the current
parallel supervisor and its Git synchronization child, with all 20 configured
repository identity leases temporarily occupied. All four repository workers
continued polling; the locks became free between control turns.

`service_control` acquired its leases and synchronized Git before publishing
`supervisor_control_repository`. The previous local `idle` snapshot therefore
misrepresented active control synchronization as a quiescent supervisor with
orphaned leases. A slow synchronization could also reach the recovery threshold.

The supervisor now publishes local control activity before acquiring any control
leases. After releasing them it restores local idle status, including contention
and failed synchronization, or disabled status when the operator stop is active.
This also prevents a failed control turn from leaving a permanent control marker
that would suppress real orphan detection. The existing watchdog timeout,
stop-before-recovery ordering, holder selection and lease inheritance are retained.

## Verification scope

The regression suite checks publication before lease acquisition, restoration on
contention and failure, and preservation of disabled state. A process-isolated
integration test synchronizes a real temporary Git remote while holding real
repository leases and verifies that the entrypoint never classifies that control
work as quiescent. It also verifies successful and failed synchronization release
the leases and restore quiescence.

Release gates are `python scripts/verify.py` and
`python scripts/verify.py --profile macos-smoke` against the exact candidate.
The suites include parallel overlap, machine exclusion, inherited locks,
contention and process termination coverage.

## Downstream audit

Inspected the current remote files on 2026-09-07:

- `esp32s3_LiteGraph/main`: `AGENTS.md`, `LOCAL_AGENT_FLOW.md`, `LOCAL_AGENT_AUTOPILOT.md`;
- `growbox-ml-controller/main` and `mvp/environment-controller`: `AGENTS.md`;
- `MatrixHub/main` and `develop`: `AGENTS.md`;
- `tracker/main`: `AGENTS.md`.

No downstream edits are required. These instructions already distinguish shared
supervisor status from repository-worker snapshots and refer to canonical main
and live daemon evidence. This fix changes the timing of existing local status
fields without changing task construction, bindings, resources, concurrency,
control paths, result schemas or planner actions.

Production installation and the release tag require an explicit release decision
after candidate validation. Live verification must then confirm fresh polling of
all four repositories, one entrypoint and supervisor, and no new quiescent-lease
warnings during ordinary control synchronization.
