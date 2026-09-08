# Local Agent 4.18.11

## Four-way repository concurrency

The bounded parallel supervisor now accepts up to four concurrent repository workers instead of three. The default remains one worker, and the operator-selected value remains explicit through `--max-workers` or `LOCAL_AGENT_MAX_PARALLEL_WORKERS`.

This is intentionally a narrow scheduling-cap change. Repository identity leases, named-resource and machine exclusion, worker admission ordering, watchdog semantics, control synchronization, task contracts and result schemas are unchanged.

The new boundary is covered directly: four workers are accepted through both CLI and environment configuration, while five remains rejected. Existing parallel, lease, resource, watchdog, process-lifecycle and macOS smoke suites remain release gates.

Production must not be restarted or switched to four workers until the operator explicitly authorizes deployment after candidate CI is green.
