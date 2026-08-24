# Local Agent Operations

This file is the canonical workflow for the established local-agent deployment.

## Roles

The planner chooses exact changes and commands. The daemon executes deterministic tasks, records real output and publishes machine-readable evidence. It does not invent fixes.

Default pairing:

- target repository: `MichalMatu/esp32s3_LiteGraph`
- target source branch: `main`
- target control branch: `agent-control`
- daemon repository: `MichalMatu/local-agent`
- daemon branch: `main`

## Control data

The `agent-control` branch contains queued tasks, live runs, terminal results, daemon status and durable control acknowledgements under `.agent/`.

Task ids and payloads are immutable. Claimed or interrupted work is never replayed automatically. Result publication may be retried; execution may not.

## Runtime limits

Current canonical defaults are:

- command timeout: 900 seconds
- maximum command/stage timeout: 1500 seconds
- no-output timeout: 300 seconds
- maximum no-output timeout: 900 seconds
- whole-task admission budget: 1800 seconds
- finalization reserve: 60 seconds
- process-group RSS limit: 4096 MiB
- maximum configurable RSS limit: 16384 MiB

Set `memory_limit_mb` to `0` only when a task intentionally needs the RSS watchdog disabled. Memory enforcement requires two consecutive over-limit samples to avoid reacting to a single transient or measurement anomaly.

Command stdout is transported through a bounded handoff queue with bounded read chunks. The raw output retained in each command result is strictly limited to the newest 60,000 characters, while live-log diff collapsing remains independent from result capture.

Long work should use named sequential stages. The whole-task budget is checked before a stage starts and must not terminate an already-running stage solely because the global budget expires.

## Development loop

1. Read `AGENTS.md` and applicable target-repository rules.
2. Inspect source plus current daemon/run/result evidence.
3. Prepare the smallest deterministic change.
4. Select verification that can detect realistic regressions from that diff.
5. Queue a unique task through the remote control branch.
6. Follow the same attempt id and task digest while it runs.
7. Diagnose real output and iterate with the next smallest change.
8. Review the exact diff and publish only validated source.
9. Treat source publication and hardware flashing as separate gates.

Verification is impact-driven. Broad suites are used only for shared/cross-cutting changes, uncertain dependency impact, explicit repository requirements or explicit user requests.

## Release flow

Non-trivial daemon changes are prepared on an isolated `v*-staging` branch. Python compile checks, Ruff lint and unit tests must pass, and GitHub CI must be green on the exact staging SHA before `main` is fast-forwarded. The live daemon checkout is never used as the staging workspace.

After a runtime release, verify the reported daemon revision and run a real queue smoke task when execution behavior changed.

## Legacy cautions

- `expected_head` is not implemented; verify an expected source SHA explicitly when required.
- Repeating an identical command string inside one task may reuse the earlier result.
- Disposable-workspace cleanup preserves ignored caches.
- Historical design documents and historical staging branches are not runtime contracts.

## Source of truth

1. real local-agent command/result output
2. target source and tests
3. remote run/status evidence
4. analysis
