# local-agent v4.11.1

v4.11.1 is a logging/readability patch release for the bounded-parallel supervisor.

## Changes

- restores an explicit human-readable `IDLE` supervisor line after startup and after real task completion;
- emits the `IDLE` operator heartbeat every 5 minutes while the daemon remains idle, keeping `tail -f` readable even after routine control/status Git publication;
- changes real parallel task execution markers to `TASK START` / `TASK DONE`;
- keeps low-level Git/process diagnostics unchanged for troubleshooting;
- does not change task/resource arbitration, concurrency, leases, control semantics, or the serial fallback.

This patch does not change the downstream task/control/resource contract, so no downstream repository workflow-document update is required.
