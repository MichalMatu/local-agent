# Local Agent 4.18.10

## Complete quiescent-status ordering

Live verification of 4.18.9 confirmed successful polling of all four repositories
but detected a remaining intermittent watchdog warning. A captured idle snapshot
was followed by ten busy identity leases belonging to newly spawned workers; the
supervisor published running status approximately 87 milliseconds after that
idle snapshot. The control synchronization fix alone did not cover worker admission.

Worker dispatch now publishes running status before lease acquisition, registers
the new worker in the active set before returning, and publishes that set after
release of the supervisor's lease copies. Failed admission restores the actual
active worker set. Both normal and priority dispatch use this single owner.

The entrypoint also compares the complete quiescent status snapshot before and
after probing leases. If the snapshot changed, even to a newer idle snapshot,
the observation is inconclusive and preserves the existing watch without starting,
clearing or advancing recovery from mixed scheduler states. Stable idle/busy
observations still reach the existing recovery threshold; stable idle/free
observations still clear the watch.

## Verification

- Unit coverage checks busy/free probes crossed by running or newer idle status,
  stable snapshots, failed worker admission, and preservation of existing workers.
- A process-isolated real Git integration verifies control synchronization,
  inherited leases during worker admission, real task completion, and idle status
  after worker reaping.
- The existing real SIGTERM/SIGKILL, overlap, machine exclusion, inherited-resource
  and binding suites remain release gates through `scripts/verify.py` and its
  `macos-smoke` profile.

## Downstream audit

The audit in `RELEASE_NOTES_V4.18.9.md` covers the same four registered downstream
repositories and their required branches. No downstream changes are needed:
this extension corrects timing and consistency of existing shared supervisor
status, with no new task, binding, resource, control-path or planner contract.

Production verification must observe several control and worker cycles after
restart, with fresh polling of all repositories and no new false lease-watch
warnings. Version 4.18.9 remains useful historical evidence of why both sides of
the status/lease observation require ordering.
