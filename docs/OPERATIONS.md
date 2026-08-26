# Local Agent Operations

This file is the canonical workflow for the established local-agent deployment. Multi-repository details are defined in `MULTI_REPOSITORY.md`.

## Roles

The planner chooses exact changes and commands. The daemon executes deterministic tasks, records real output and publishes machine-readable evidence. It does not invent fixes.

Validated default pairing:

- target repository: `MichalMatu/esp32s3_LiteGraph`
- target source branch: `main`
- target control branch: `agent-control`
- daemon repository: `MichalMatu/local-agent`
- daemon branch: `main`

Multi-repository mode generalizes the target side to a machine-local registry while preserving the same task format and execution core.

## Control data

Each repository `agent-control` branch contains queued tasks, live runs, terminal results, daemon/repository status and durable control acknowledgements under `.agent/`.

Task ids and payloads are immutable within one repository. Claimed or interrupted work is never replayed automatically. Final results are durably spooled before remote publication. Result publication may be retried; execution may not.

In multi-repository mode, task/result/claim identity is repository-scoped. Two repositories may safely contain the same task id.

Repository stale-claim recovery runs only while the worker owns inherited OS leases for the configured id, remote and workspace identities. If an earlier worker or command is still alive after a crash, a restarted supervisor defers that repository without recovering or replaying its task.

## Runtime limits

Current canonical defaults are:

- command timeout: 900 seconds
- maximum command/stage timeout: 7200 seconds
- no-output timeout: 300 seconds
- maximum no-output timeout: 3600 seconds
- whole-task admission budget: 1800 seconds, maximum 21600 seconds
- finalization reserve: 60 seconds
- process-group RSS limit: 4096 MiB
- maximum configurable RSS limit: 16384 MiB

Set `memory_limit_mb` to `0` only when a task intentionally needs the RSS watchdog disabled. Memory enforcement requires two consecutive over-limit samples to avoid reacting to a single transient or measurement anomaly.

Command stdout is transported through a bounded handoff queue with bounded read chunks. The raw output retained in each command result is strictly limited to the newest 60,000 characters, while live-log diff collapsing remains independent from result capture.

Runtime timeout configuration is read once at daemon startup; restart the daemon after changing it. The six variables are `LOCAL_AGENT_COMMAND_TIMEOUT_DEFAULT`, `LOCAL_AGENT_COMMAND_TIMEOUT_MAX`, `LOCAL_AGENT_IDLE_TIMEOUT_DEFAULT`, `LOCAL_AGENT_IDLE_TIMEOUT_MAX`, `LOCAL_AGENT_TASK_TIMEOUT_DEFAULT`, and `LOCAL_AGENT_TASK_TIMEOUT_MAX`. Their default/maxima pairs are 900/7200 seconds, 300/3600 seconds, and 1800/21600 seconds. A heavy task can use `command_timeout=3600`, `idle_timeout=1200`, and `task_timeout=7200`.

Long work should use named sequential stages. The whole-task budget is checked before a stage starts and must not terminate an already-running stage solely because the global budget expires.

## Efficient verification workflow

Structured staged tasks may opt in with
`workflow_policy: "efficient-verification-v1"`. Under this policy, every item in
`steps` and `verify_steps` declares a `verification_level` of `work`, `focused`
or `full`. Legacy `commands` and `verify_commands` fields are not allowed in an
opted-in task, including empty declarations of those fields.

The canonical coding workflow is:

1. Use a primary `work` stage for implementation or editing and run only the
   smallest focused checks needed while editing.
2. Use a primary `focused` stage to audit the exact diff and run only affected
   regression and static checks.
3. Use `focused` for any additional pre-final `verify_steps`. A verification
   stage may never use `work`.
4. Declare exactly one `full` stage, as the last `verify_steps` item and therefore
   the final stage in the plan. Its declared command runs the repository-mandated
   broad suite once, followed by the final build or release gate once.
5. If the full gate exposes a defect, fix it and rerun only the affected focused
   gate first. Then rerun the full gate because source changed after the previous
   full-gate attempt.

Primary stages may be `work` or `focused`, never `full`. The daemon validates
declared intent before execution and publishes `verification_level` in stage
results and live progress/status data. It does not inspect command text to infer
cost, deduplicate commands or skip identical declarations.

## Development loop

1. Read `AGENTS.md` and applicable target-repository rules.
2. Inspect source plus current daemon/run/result evidence for the exact repository.
3. Prepare the smallest deterministic change.
4. Select verification that can detect realistic regressions from that diff.
5. Queue a unique task through that repository's remote `agent-control` branch.
6. Follow the same attempt id and task digest while it runs.
7. Diagnose real output and iterate with the next smallest change.
8. Review the exact diff and publish only validated source.
9. Treat source publication and hardware flashing as separate gates.

Verification is impact-driven. Broad suites are used only for shared/cross-cutting changes, uncertain dependency impact, explicit repository requirements or explicit user requests.

## Multi-repository operation

The registry is stored at:

```text
~/Library/Application Support/local-agent/repositories.json
```

Inspect and validate it with:

```bash
python agent_repo_admin.py list
python agent_repo_admin.py validate
```

Provision one new repository explicitly with:

```bash
python agent_repo_admin.py provision --repository-id <id>
```

Provisioning is never an implicit poll-loop action. It refuses existing non-Git destinations, validates origin identity and may initialize a missing `agent-control` branch only in a newly created control clone.

The multi-repository supervisor schedules repositories round-robin and starts one short-lived worker at a time. Global execution concurrency remains one even when several chats/projects queue tasks concurrently. Between worker turns, due supervisor control runs first and a periodic full scan runs before another hot poll. Running stages are not preempted, but a continuously active repository cannot permanently starve another repository or maintenance.

Each repository turn holds non-blocking OS execution leases for the case-insensitive repository id and remote plus normalized control, work and checkpoint paths. The descriptors are inherited by the worker and every command. Lease contention is a normal deferral, not a stale-claim recovery opportunity. The worker also rejects a dispatch if the exact registry entry changed after selection.

Repository ids and remote identities must be unique case-insensitively. Workspace validation rejects normalized, aliased, case-insensitive and ancestor/descendant collisions. Run `python agent_repo_admin.py validate` after every registry edit.

SIGTERM to the supervisor or worker first stops active task work, quiesces asynchronous control-Git publication and then terminates all remaining registered process groups with bounded escalation. This ordering prevents graceful shutdown from leaving a partially published control checkout. SIGKILL cannot run cleanup handlers; inherited repository leases remain the safety boundary until every surviving descendant exits.

Repository-local `status` control is supported. Global `restart` and `self_update` are intentionally not executed by repository workers; use explicit supervisor/launchd administration for those maintenance operations.

## Release flow

Non-trivial daemon changes are prepared on an isolated `v*-staging` branch. Python compile checks, Ruff lint and unit tests must pass, and GitHub CI must be green on the exact staging SHA before `main` is fast-forwarded. The live daemon checkout is never used as the staging workspace.

Multi-repository changes additionally require real temporary-Git integration tests, real SIGTERM/SIGKILL recovery coverage and an isolated macOS two-repository smoke test on the exact candidate SHA. The smoke test must clean up its staging worktree and leave the running production daemon healthy.

After a runtime release, verify the reported daemon revision/status and run a real queue smoke task when execution behavior changed.

## Activation and rollback

The multi-repository launchd file is a replacement template, not a second service. It uses the same launchd label and daemon lock as the single-repository entry point.

Do not load both entry points simultaneously. Stop/unload the existing service before replacing its launchd configuration. Rollback means stopping the supervisor, restoring the previous plist and starting the service again; the legacy LiteGraph workspace remains intact.

## Legacy cautions

- `expected_head` is not implemented; verify an expected source SHA explicitly when required.
- Every declared command executes independently, including identical command strings.
- Disposable-workspace cleanup preserves ignored caches.
- Historical design documents and historical staging branches are not runtime contracts.

## Source of truth

1. real local-agent command/result output
2. target source and tests
3. remote run/status evidence
4. analysis
