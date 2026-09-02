# Local Agent v4.13.1

## Re-audit fixes

- Repository remote idle heartbeats are now derived from fetched remote status rather than the locally rewritten status-file mtime, so stale daemon versions/status cannot persist indefinitely.
- Explicit retry deadlines override normal adaptive repository polling, so continuous-mode resource and worker backoff follows the configured retry schedule instead of being silently stretched to the idle poll cadence.
- Supervisor-wide `status` control preserves parallel/serial execution metadata instead of publishing a generic daemon status that drops the execution model and worker limit.
- Repository execution lease descriptors and external resource-lock descriptors use separate inherited environment channels, preventing resource locks from being misinterpreted as repository identities in nested Local Agent code.

## Documentation

- Current docs no longer label the production scheduler as a v4.11-only path.
- The v4.11 parallel execution record now clearly marks its conservative resource policy as historical and superseded by v4.13.
- Registry v1 documents that the first enabled repository is the global supervisor control source.

## Verification

- Adds focused regression coverage for remote status freshness, continuous retry deadlines and status-control metadata.
- Real registered-repository overlap remains a separate deployment gate and is intentionally not part of this code-audit task.
