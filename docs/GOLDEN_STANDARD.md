# Local Agent Golden Standard v4.5

This file records the current validated infrastructure invariants for `MichalMatu/local-agent` and its established `MichalMatu/esp32s3_LiteGraph` workflow. Operational details live in `OPERATIONS.md`; machine-specific setup lives in `SESSION_BOOTSTRAP.md`.

## Invariants

- `agentd.py` is the only daemon entry point.
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

## Required daemon release gate

For non-trivial daemon changes:

1. stage from current `main` on an isolated `v*-staging` branch;
2. change only intended source/tests/docs;
3. pass Python compile validation;
4. pass Ruff lint validation;
5. pass unit tests;
6. review the exact diff;
7. require green GitHub CI on the exact staging SHA;
8. fast-forward `main` to the validated SHA;
9. allow the idle daemon to self-update;
10. verify the reported daemon revision;
11. run a real queue smoke task when runtime behavior changed.

## Current audit disposition

The v4.5 hardening removes two remaining execution-layer weaknesses from the v4.4 baseline: unbounded stdout handoff and implicit global runner replacement. It centralizes process lifecycle primitives, strictly bounds stdout memory, adds a process-group RSS watchdog, keeps the existing stage-boundary task budget semantics and adds a pinned Ruff quality gate to CI.

The v4.4 baseline established stage-boundary task-budget admission, explicit per-stage timeouts, tighter command/no-output limits and terminal `task_budget_exhausted` evidence for stages that cannot safely start. Earlier v4.x hardening established durable claims, replay safety, remote progress/control, structured sequential stages, telemetry, dirty-workspace checkpointing, malformed-task terminal handling, isolated release staging and impact-driven verification.

### Historical reference: `v4.2.4-staging`

The historical `v4.2.4-staging` branch contains commit `d11be42` (`Bound command memory and output buffering`). Its useful safeguards were reviewed and manually adapted to the current v4.5 architecture rather than cherry-picked across the newer v4.4 runtime-budget work.

Keep the historical branch as reference. It is not the canonical runtime and should not be merged directly into current `main`.
