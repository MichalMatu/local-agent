# Local Agent 4.18.7

Local Agent 4.18.6 fixed the macOS `launchctl bootout`/`bootstrap` restart race, but production restart exposed a separate guarded-entrypoint shutdown race during a simultaneous self-revision change.

The old guarded entrypoint received `SIGTERM` from launchd and set its in-memory stop flag. Before the loop could exit, it observed the just-updated checkout and called `os.execv()` to re-execute itself. The exec replaced the Python image, resetting that in-memory stop state. The old process therefore escaped the launchd shutdown and started a fresh parallel supervisor. That supervisor legitimately acquired `agentd.lock`, while the newly bootstrapped LaunchAgent instance then refused startup with `another local-agent daemon holds the daemon lock`.

## Fix

- a pending `SIGTERM`/`SIGINT` suppresses guarded self re-exec before `exec` whenever the stop request is already visible;
- the signal handler also records a private inherited-stop environment marker so a signal that lands after the final pre-exec check still survives `exec`;
- a re-executed guarded entrypoint consumes that marker immediately after installing signal handlers and exits before reading repository state or starting a supervisor;
- normal revision-driven self re-exec is unchanged when no shutdown is in progress;
- the existing daemon-lock fail-closed behavior remains unchanged.

## Regression coverage

A real process-lifecycle test forces the race window between the final stop check and `os.execv()`, sends `SIGTERM`, allows the real exec to occur, and verifies that:

- the inherited shutdown marker is consumed by the new process image;
- no replacement supervisor is started after exec;
- the pre-existing supervisor is reaped;
- the guarded process exits successfully instead of escaping launchd shutdown.

## Operator recovery

An installation affected by the pre-4.18.7 race can have two Local Agent process trees: the current LaunchAgent entrypoint plus an older escaped guarded entrypoint/supervisor. Stop the LaunchAgent, terminate only Local Agent processes from `~/local-agent`, then restart after updating to 4.18.7. Do not remove repository state or lock files manually.
