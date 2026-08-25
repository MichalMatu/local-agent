# Local Agent Golden Standard v4.9

This file records the current production invariants for `MichalMatu/local-agent`. Operational details live in `OPERATIONS.md`; multi-repository details live in `MULTI_REPOSITORY.md`; machine-specific setup lives in `SESSION_BOOTSTRAP.md`.

## Execution and recovery invariants

- The daemon is a deterministic executor, not a coding model.
- Machine-generated execution content is English-only.
- One OS-locked daemon or supervisor instance is allowed.
- Every task has an immutable payload digest and one durable attempt claim.
- Interrupted tasks are never automatically replayed.
- Malformed or oversized task JSON is terminal `invalid_task_file`.
- Task fields use exact JSON types and bounded list, command, patch and write sizes.
- Command and no-output watchdogs are mandatory.
- The whole-task limit is an admission budget: a stage that cannot fit with finalization headroom is not started, but an already-running stage is not killed solely because the global budget elapsed.
- Default/max timeout pairs are command 900/7200 seconds, no-output 300/3600 seconds and task 1800/21600 seconds.
- Timeout configuration is loaded from `LOCAL_AGENT_*` environment variables at startup and invalid configuration is terminal.
- Command stdout transport and retained output are strictly bounded.
- Runtime commands use process groups. Residual descendants after a successful parent exit are terminated and reported as `background_process_leak`.
- Host telemetry, RSS sampling and remote progress publication never execute blocking work in the command watchdog loop.
- Remote progress is asynchronous and coalesced; daemon health status does not duplicate every command transition.
- Opt-in `efficient-verification-v1` tasks use structured stages with explicit
  `work`, `focused` and `full` intent, exactly one final full verification stage,
  and visible verification-level metadata.
- Every declared command executes independently, including identical command strings.
- Final results are atomically and durably spooled before remote publication.
- Publication failure leaves the claim and spool intact; recovery republishes the result without re-executing commands.
- Self-update requires a clean `main`, accepts fast-forwards only, validates in an isolated temporary home and rolls back validation failure.

## Workspace checkpoint invariants

- Dirty tracked changes and untracked files are checkpointed outside the worktree before destructive cleanup.
- Checkpointing runs on every task exit, including command failure, timeout, budget exhaustion and daemon exceptions that reach task finalization.
- Checkpoint creation has bounded time, file count and bytes, checks free space, copies files as streams and durably syncs files and directories.
- A checkpoint failure skips cleanup and preserves dirty state.
- A cleanup failure is terminal evidence and preserves both the original task failure and the finalization failure.
- `prepare_work` checkpoints dirty state before any reset or clean.
- Ignored caches remain preserved by normal cleanup.

## Multi-repository invariants

- One long-lived supervisor owns scheduling and the global daemon lock.
- Global execution concurrency remains exactly one.
- Every normalized control/work/checkpoint path is disjoint; equal, aliased and ancestor/descendant overlaps are rejected.
- Claims, result spools, corrupt claims, runs and status are repository-scoped.
- Repository globals are bound only inside short-lived workers.
- One repository control or worker failure does not block polling other repositories.
- Worker turns are bounded by the configured maximum task budget plus finalization grace.
- Polling never implicitly clones, repairs or overwrites a checkout.
- Provisioning is explicit and validates repository identity.
- Repository workers reject supervisor-wide `restart` and `self_update` actions.

## Required release gate

For non-trivial daemon changes:

1. stage from current `main` on an isolated `v*-staging` branch;
2. pass compile and pinned Ruff validation for every release module and tests;
3. pass focused unit/integration tests and full unittest discovery;
4. review the exact diff;
5. require green GitHub CI on the exact staging SHA;
6. pass an isolated macOS two-repository smoke on that exact SHA;
7. confirm the production daemon/worktree remained unchanged during smoke;
8. fast-forward and push `main` only after every gate is green;
9. deploy/restart the matching local installation;
10. verify live supervisor/worker version, revision and a real queued task.

Historical design notes and staging branches are references only and are not runtime contracts.
