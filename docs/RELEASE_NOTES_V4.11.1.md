# local-agent v4.11.1

v4.11.1 is a logging/readability patch release for the bounded-parallel supervisor.

## Changes

- restores an explicit human-readable `IDLE` supervisor line after startup and after real task completion;
- emits the `IDLE` operator heartbeat every 5 minutes while the daemon remains idle, keeping `tail -f` readable even after routine control/status Git publication;
- changes real parallel task execution markers to `TASK START` / `TASK DONE`;
- keeps successful control-plane Git publication quiet so operator logs stay focused on `IDLE`, task and failure events;
- preserves non-empty Git diagnostics and transient-network retry messages when those quiet operations fail;
- handles tracked, staged-new and purely untracked interrupted daemon-owned control metadata with exact-path recovery;
- recovers interrupted daemon-owned control status/run/result/ack files before a control-branch pull, preventing a SIGKILL between write/stage/commit from wedging later recovery;
- refuses to auto-clean unexpected control changes such as tasks or daemon control requests;
- does not change task/resource arbitration, concurrency, leases, or the serial fallback.

This patch does not change the downstream task/control/resource contract, so no downstream repository workflow-document update is required.
