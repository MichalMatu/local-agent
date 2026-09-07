# Local Agent 4.18.12

## macOS four-worker deployment fix

Release 4.18.11 correctly raised the runtime scheduler cap to four repository workers, but the macOS LaunchAgent generator still contained its historical independent `1..3` validation. As a result, `scripts/macos_launchd.py restart --mode parallel --max-workers 4` failed before writing the plist and production remained on the previous two-worker launchd configuration.

The macOS launcher no longer owns a duplicated numeric worker limit. It imports `MAX_MAX_WORKERS` directly from `local_agent.supervisor.scheduling`, so runtime admission and generated LaunchAgent validation share one source of truth.

Regression coverage now verifies both the direct macOS argument builder and the actual CLI render path with `--max-workers 4`; the next value above the scheduler cap remains rejected.

No repository lease, named-resource/machine exclusion, worker ordering, watchdog, control synchronization, task/result schema, binding or downstream planner contract changes are included.
