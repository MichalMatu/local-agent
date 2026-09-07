# Local Agent 4.18.8

## Summary

Fix a stale repository-lease recovery watchdog starvation case observed in production after the 4.18.7 cleanup.

The guarded entrypoint correctly detected `idle` supervisor states with a busy repository lease, but it reset the 30-second recovery watch whenever the supervisor briefly became non-quiescent. With four repositories polling independently, unrelated worker turns or global-control activity could occur often enough that the watch repeatedly restarted and never reached the recovery threshold.

## Changes

- preserve an already-started stale-lease watch across transient scheduler activity
- clear the watch only after a verified quiescent observation finds all repository leases free, or when the supervisor lifecycle itself is reset
- keep destructive orphan recovery gated on a later verified quiescent + busy observation after the 30-second threshold
- keep global-control status excluded from quiescent classification
- keep daemon-lock exclusion, supervisor stop-before-recovery, and SIGTERM -> SIGKILL holder recovery unchanged

## Safety rationale

Transient active workers do not themselves trigger destructive recovery. They only stop erasing evidence from an earlier quiescent + busy observation. Recovery still requires the supervisor to be quiescent again and the repository lease set to remain busy after the threshold. The supervisor is then stopped before holder inspection or termination, preserving the existing fail-closed recovery invariant.

## Regression coverage

- a quiescent + busy observation starts the watchdog
- transient non-quiescent scheduler activity preserves that start time
- a later quiescent + busy observation can reach the 30-second threshold
- a verified quiescent + free observation clears the watchdog

Release candidate: 4.18.8.
