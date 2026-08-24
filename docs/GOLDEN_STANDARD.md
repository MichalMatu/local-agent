# Local Agent Golden Standard v4.5 + v4.6 staging addendum

This file records the validated v4.5 production invariants for `MichalMatu/local-agent` and the additional invariants required before the v4.6 multi-repository staging line may replace it. Operational details live in `OPERATIONS.md`; multi-repository details live in `MULTI_REPOSITORY.md`; machine-specific setup lives in `SESSION_BOOTSTRAP.md`.

## v4.5 production invariants

- `agentd.py` is the validated production daemon entry point.
- The daemon is a deterministic executor, not a coding model.
- Machine-generated execution content is English-only.
- One OS-locked daemon instance is allowed.
- Every task has an immutable payload digest and one durable attempt claim.
- Interrupted tasks are never automatically replayed.
- Corrupt durable claims are converted to terminal evidence for known queued tasks.
- Malformed task JSON is terminal `invalid_task_file` and is not retried.
- Command and no-output watchdogs are mandatory.
- The whole-task limit is an admission budget: a stage that cannot fit with finalization headroom is not started, but an already-running stage is not killed solely because the global budget elapsed.
- Default command timeout is 900 seconds; maximum command/stage timeout is 1500 seconds.
- Default no-output timeout is 300 seconds; maximum is 900 seconds.
- Whole-task budget is 1800 seconds with a 60-second finalization reserve.
- Command stdout handoff uses a bounded queue and bounded read chunks; retained raw result output is strictly capped at 60,000 characters.
- Runtime commands have a configurable process-group RSS limit: 4096 MiB by default, 16384 MiB maximum, and `0` disables the memory watchdog.
- The RSS watchdog requires two consecutive over-limit samples before terminating a process group.
- Low-level shell spawning, bounded stdout transport and process-group termination are centralized in `agent_process.py`.
- Runtime execution is injected explicitly into `agent_core.process_task`; production execution does not replace the global `agent_core.run_command` function.
- Process-group termination is used for timed-out, interrupted or memory-limited commands and preserves the group identity even if the original shell process exits first.
- Result publication may be retried; command execution may not.
- Self-update requires a clean `main` checkout, accepts fast-forward updates only, validates before restart and rolls back validation failure.
- Release staging happens outside the live daemon checkout.
- The user's product checkout is never reset or cleaned by normal daemon execution.
- Dirty disposable workspaces are checkpointed before destructive cleanup.
- Progress/status/results remain remotely observable on the target control branch.
- Target verification is impact-driven; broad regression suites are not automatic final gates.
- Green focused evidence may be reused while covered code and relevant dependencies remain unchanged.
- Secrets never belong in task/result/run/status files or repository documentation.
- Publishing source and flashing hardware are separate gates.

## v4.6 multi-repository staging invariants

All v4.5 execution/watchdog/replay invariants continue to apply inside each repository worker. In addition:

- one long-lived supervisor owns scheduling and the same global daemon lock;
- v4.5 and v4.6 entry points must never execute concurrently;
- global local execution concurrency remains exactly one;
- every configured repository has unique control/work/checkpoint paths;
- durable claims, corrupt claims, local runs and local status are repository-scoped;
- the same task id may exist in different repositories without collision;
- repository paths are bound only inside short-lived worker processes, never by mutating globals in the long-lived supervisor;
- one repository failure before execution does not block polling of other repositories;
- scheduling uses deterministic round-robin order after each processed task;
- polling never implicitly clones, repairs or overwrites a repository checkout;
- provisioning is explicit, validates `origin`, refuses existing non-Git paths and may safely initialize a missing `agent-control` branch;
- repository-local `status` is supported and idle remote status is heartbeat-throttled;
- repository workers reject global `restart` and `self_update` because those operations are supervisor-wide maintenance actions;
- multiple remote planners/chats may queue work independently, while local execution remains serialized;
- multi-repository changes require temporary-Git integration coverage in addition to unit tests;
- activation requires an exact-SHA macOS smoke test without modifying the running production checkout.

## Required daemon release gate

For non-trivial daemon changes:

1. stage from current `main` on an isolated `v*-staging` branch;
2. change only intended source/tests/docs;
3. pass Python compile validation;
4. pass Ruff lint validation;
5. pass unit and required integration tests;
6. review the exact diff;
7. require green GitHub CI on the exact staging SHA;
8. for multi-repository changes, pass an isolated macOS two-repository smoke on that same exact SHA;
9. confirm smoke cleanup and production daemon health;
10. fast-forward `main` only after an explicit release decision;
11. activate the matching launchd entry point/configuration;
12. verify reported daemon/repository status and run a real queued task after activation.

## Current audit disposition

The v4.5 production hardening removed unbounded stdout handoff and implicit global runner replacement, centralized process lifecycle primitives, added a process-group RSS watchdog and added a pinned Ruff quality gate.

The v4.6 staging line adds process-isolated multi-repository scheduling without rewriting that validated execution core. Its registry, isolated worker, round-robin scheduler, repository-scoped state/control, explicit provisioning and two-repository temporary-Git integration path are implemented and tested. `main` remains v4.5 until the exact final staging SHA completes the release gate and activation is explicitly chosen.

### Historical reference: `v4.2.4-staging`

The historical `v4.2.4-staging` branch contains commit `d11be42` (`Bound command memory and output buffering`). Its useful safeguards were reviewed and manually adapted to the v4.5 architecture rather than cherry-picked across newer runtime-budget work.

Keep the historical branch as reference. It is not the canonical runtime and should not be merged directly into current `main`.
