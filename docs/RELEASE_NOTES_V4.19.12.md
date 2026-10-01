# Local Agent 4.19.12

## Summary

Local Agent 4.19.12 hardens GitHub outage behavior in the control plane. A transient DNS/network outage must no longer keep one Git operation blocked for minutes or cause the guarded entrypoint to hammer `operator-control` probes every two seconds.

## Runtime changes

- Git transport attempts routed through `run_git_with_network_retry()` are capped at 20 seconds per attempt.
- One transient retry after 2 seconds remains inside the storage helper; longer recovery is delegated to the existing supervisor retry/backoff policy.
- Control checkout synchronization uses a process-local 30-second circuit breaker after an exhausted transient Git failure. During the open interval it fails fast without spawning another Git network command.
- Remote emergency operator ref probing now uses a 5-second ref timeout and transport backoff of 10, 30 and then 60 seconds.
- Remote transport failures continue to preserve the last known desired state. Reachable but invalid operator state remains fail-closed.

## Compatibility

Task schema, hard binding, resource declarations, worker concurrency, MCP contracts and Chat Bridge protocol/version remain unchanged. Chat Bridge stays at 0.6.2.

## Verification requirements

The candidate requires focused network-resilience tests, the repository-wide verification suite, CI coverage/Python compatibility and macOS smoke before `main` can advance.

The Playwright dependency observed in the separate Stage 8 DEV checkout is development-only and remains pinned at 1.57.0. It should be installed in that checkout before rerunning live browser proof; it is not a production Local Agent runtime dependency.
