# Local Agent 4.18.5

Local Agent could become permanently stuck after a command launched a detached daemon that inherited repository execution-lease descriptors. The incident was reproduced with `adb`: the foreground task completed, but the background ADB server kept the inherited repository `flock` alive after the worker exited. The parallel supervisor then repeatedly deferred global control during startup because it could no longer acquire all repository identities.

## Hardening

The guarded entrypoint now detects repository leases that remain busy after the scheduler is genuinely idle. After a bounded 30-second stall it stops the supervisor first, acquires the global daemon lock, identifies only processes that actually carry the inherited `flock`, terminates those orphan holders, verifies that the leases are free and then allows the supervisor to restart cleanly.

Recovery remains fail-closed:

- repository execution-lease inheritance is preserved, so worker/supervisor failure still cannot release isolation prematurely;
- Linux identifies inherited lock holders through matching `/proc/<pid>/fdinfo/<fd>` `FLOCK` records rather than relying on the stale original PID in `/proc/locks`;
- macOS uses bounded `lsof` inspection and requires both current lock status and Darwin's per-fileglob `FHASLOCK`/`FWASLOCKED` flag, preventing a process that merely opens the same lock file from becoming a recovery victim;
- destructive orphan cleanup refuses to run while another Local Agent instance owns `agentd.lock`;
- legitimate global-control status is excluded from scheduler-idle recovery detection;
- the same orphan cleanup runs before supervisor startup, allowing restart to repair an already-stuck installation.

The macOS LaunchAgent helper also surfaces `launchctl bootstrap` stdout/stderr when restart fails, instead of hiding the useful launchd error behind a generic `CalledProcessError` traceback.

## Regression coverage

The release adds real process-lifecycle coverage for:

- inherited repository leases surviving the original owner;
- a holder that ignores `SIGTERM`, requiring bounded `SIGKILL` escalation;
- reacquisition of the repository lease after recovery;
- preservation of an unrelated process that only has the lock file open;
- current-supervisor scheduler-idle gating;
- exclusion of legitimate global-control state;
- global daemon-lock exclusion during destructive recovery.

The lease-recovery suite is part of the required macOS smoke profile so the macOS `lsof` path is exercised by CI.

## Downstream documentation audit

The current Local Agent instructions were reviewed in:

- `MichalMatu/esp32s3_LiteGraph`: `AGENTS.md`, `LOCAL_AGENT_FLOW.md`, `LOCAL_AGENT_AUTOPILOT.md` on `main`;
- `MichalMatu/growbox-ml-controller`: `AGENTS.md` on `main` and `mvp/environment-controller`;
- `MichalMatu/MatrixHub`: `AGENTS.md` on `main` and `develop`;
- `MichalMatu/tracker`: `AGENTS.md` on `main`.

No downstream edit is required. Version 4.18.5 does not change task fields, agent binding, repository routing, resource declarations, control-plane paths, status/result contracts, concurrency semantics or planner instructions. It hardens the existing repository-lease/process-lifecycle contract inside the Local Agent runtime.

## Operator recovery

For an installation already stuck by an escaped ADB server, the immediate safe recovery is to stop ADB and restart the LaunchAgent from the production checkout:

```bash
adb kill-server || true
cd ~/local-agent
.venv/bin/python scripts/macos_launchd.py restart --mode parallel --max-workers 2
```

After `main` has advanced to this release, the guarded entrypoint can also repair a stale inherited repository lease automatically during startup.
