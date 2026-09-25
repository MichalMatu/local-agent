---
name: local-agent-control
description: Use the connected GitHub app to control a bounded Local Agent executor running on the user's own computer. Use this for local builds, tests, device checks, machine-specific commands, and exact Local Agent status/result inspection.
---

# Local Agent control workflow

Use the required GitHub app as the only remote control-plane transport. Local Agent itself remains the deterministic executor on the user's computer.

## Hard safety rules

1. Never invent a target repository, branch, task id, or `agent_binding`.
2. Before any Local Agent write, resolve one explicit GitHub repository and keep that repository fixed for the active task.
3. Read `.agent/binding.json` from the repository's `agent-control` branch before queueing a task. Copy the exact canonical `agent_binding` from that file into the task payload.
4. If the binding file is missing, malformed, or inconsistent with current control/status evidence, stop. Do not guess or substitute another repository.
5. Read `.agent/status/daemon.json` from `agent-control` before queueing. Do not queue a second task for the same active goal while an earlier task is still active.
6. Task files are immutable. Never overwrite or reuse `.agent/tasks/<task-id>.json`. A retry or continuation always uses a new task id.
7. Every task must declare `resources` explicitly. Use `resources: []` unless exact repository/operator policy requires a named resource or whole-machine exclusivity.
8. Prefer `allow_write: false`. Use local write execution only when the requested workflow genuinely requires the machine to modify the checkout and the repository policy permits it.
9. Never treat a queued task, a Git commit, daemon `idle`, or a live run as proof of successful local execution. The exact terminal result is authoritative.
10. Never use the `MichalMatu/local-agent` repository as a project execution target. Infrastructure changes to Local Agent follow that repository's own candidate-branch and release policy.

## Inspect repository instructions first

Before planning a source change or execution task, read the target repository's current instructions when present, especially `AGENTS.md`, Local Agent flow documentation, and branch/testing policy. Follow those instructions unless they conflict with the Local Agent hard safety contract.

## Choose direct GitHub work or Local Agent execution

Use direct GitHub edits for bounded source, configuration, or documentation changes when the exact diff plus repository CI can verify the outcome.

Use Local Agent when the requested evidence requires the user's computer, such as:

- local compilation or tests;
- hardware/device access;
- locally installed SDKs or toolchains;
- machine-specific diagnostics;
- local files or resources intentionally exposed by the task command;
- verification that cannot be established by GitHub state or hosted CI alone.

A hybrid flow is preferred for many development tasks: make the source change through GitHub, then queue a read-only Local Agent verification task for the exact target branch/commit.

## Read the Local Agent control plane

For the selected repository, use the `agent-control` branch and these canonical paths:

```text
.agent/binding.json               repository binding identity
.agent/tasks/<task-id>.json       planner -> executor
.agent/runs/<task-id>.json        live execution evidence
.agent/results/<task-id>.json     terminal execution evidence
.agent/status/daemon.json         repository worker/daemon status
.agent/daemon/control.json        repository control request
.agent/daemon/acks/*.json         control acknowledgements
```

Do not hand-edit any machine-local Local Agent control clone. Remote GitHub state is the transport.

## Queue a bounded task

Create a new unique task file on `agent-control`. Use the exact `agent_binding` read from `.agent/binding.json`.

A minimal read-only command task has this shape:

```json
{
  "id": "verify-unique-id",
  "agent_binding": "00000000-0000-0000-0000-000000000000",
  "mode": "commands",
  "work_branch": "main",
  "allow_write": false,
  "resources": [],
  "command_timeout": 300,
  "task_timeout": 900,
  "commands": [
    "python scripts/verify.py --only tests"
  ]
}
```

Replace every example value with repository-grounded values. Select `work_branch` from the repository's actual branch policy. Keep timeouts bounded and proportional to the command. Do not add broad machine exclusivity merely because the task is a build or test.

When a staged implementation task is appropriate and the repository supports it, follow the canonical Local Agent task contract rather than inventing new fields. Prefer `workflow_policy: "efficient-verification-v1"` for staged coding tasks that explicitly separate work, focused verification, and one final full verification stage.

Commit only the new task/control-plane content intended for this operation. Do not rewrite unrelated control files.

## Monitor execution

After queueing a task:

1. Read `.agent/status/daemon.json` for current repository state.
2. Read `.agent/runs/<task-id>.json` when present for live evidence.
3. Read `.agent/results/<task-id>.json` when present for terminal evidence.
4. Match the exact task id and digest/result evidence; do not borrow evidence from another task.
5. If the task is healthy and active, do not queue another task for the same goal.
6. If no terminal result is available yet, report the exact known state rather than claiming completion.

The evidence order is: exact terminal result, exact live run/progress, current daemon status, referenced source/diff/test evidence, then planner analysis.

## Cancel an active task only with exact evidence

If current run/status evidence proves the active task cannot achieve the intended outcome, write one repository-scoped cancellation request to `.agent/daemon/control.json`:

```json
{
  "id": "cancel-unique-id",
  "action": "cancel_task",
  "task_id": "exact-active-task-id"
}
```

Use a unique control id and the exact active task id. Do not cancel merely because a task is taking longer than expected. After requesting cancellation, inspect the matching acknowledgement and terminal task result before queueing a replacement.

## Fail closed

Treat missing/wrong binding, malformed task data, binding mismatch, invalid resources, and terminal task-contract failures as safety evidence. Do not repair them by guessing alternate routing or silently changing the old task payload.

If GitHub write access is unavailable, the required GitHub app is disconnected, the repository is not authorized, or the necessary branch cannot be accessed, explain the exact missing prerequisite and stop before attempting execution.

## User-facing completion report

When work completes, report the smallest useful evidence set:

- repository and source branch/commit;
- Local Agent task id when local execution was used;
- terminal result status;
- relevant build/test/device outcome;
- any remaining limitation or required user action.

Do not expose internal credentials, tokens, private connector identifiers, or unrelated repository data.
