# Local Agent 4.18.13

## Prevent launchd from orphaning a draining supervisor

A macOS restart exposed a lifecycle budget inversion: launchd reported an effective five-second exit timeout while the guarded entrypoint itself gives the parallel supervisor up to five seconds to terminate cleanly. When the supervisor was draining an active worker, launchd could SIGKILL the entrypoint just before its bounded SIGKILL fallback ran, leaving the old supervisor alive with the global daemon lock.

The LaunchAgent now declares `ExitTimeOut = 15`, while the restart helper waits up to 20 seconds for bootout to complete. This keeps launchd alive long enough for the existing bounded process-group cleanup to finish and preserves the current SIGTERM-then-SIGKILL behavior rather than shortening task cleanup.

The macOS LaunchAgent test suite verifies the explicit exit timeout, verifies that the bootout wait budget exceeds it, and retains the direct four-worker render regression from 4.18.12.

The repository scheduling documentation is also corrected to state the current hard cap of four workers. No task schema, planner contract, resource classification, lease ownership, watchdog policy, worker admission ordering, result format, or downstream repository instruction changes are required.
