# Autonomous Chat Planner Loop

This document defines the optional autonomous planning loop that connects ChatGPT conversations to the deterministic `local-agent` executor through the Chrome Chat Bridge and the Git-backed control plane.

Each configured conversation remains one independent planner loop for its own active goal. Chat Bridge v0.3 can schedule several such conversations at the same time. The bridge is only a wake-up and control transport: it does not understand a conversation, choose work, inspect source, or execute commands. ChatGPT remains the planner. `local-agent` remains the deterministic executor.

## Roles

```text
user goal in one ChatGPT conversation
        |
        v
ChatGPT planner
- understands the active goal
- inspects source/status/results
- decides the next bounded task
- writes task JSON to agent-control
        |
        v
local-agent
- validates the immutable task payload
- runs the declared commands locally
- enforces time/output/RSS/process limits
- publishes progress/status/result evidence
        |
        v
Chat Bridge
- waits for that conversation's configured interval
- wakes the same ChatGPT conversation
- never plans or interprets local-agent work
        |
        +----> ChatGPT evaluates evidence and continues or stops
```

The planner and executor contracts remain separate. Autonomous planning must not add an LLM or heuristic decision layer to the deterministic executor.

## Bridge bootstrap and compact wake prompts

The bridge prompt is a wake-up policy, not the complete operating manual. Chat Bridge v0.3 separates prompt delivery into two phases:

1. a one-time bootstrap prompt establishes the bridge policy, optional repository-id routing hint and compact control protocol for that conversation;
2. later wake-ups use a short wake prompt that tells ChatGPT to continue the already active goal from current repository evidence without restating unchanged history.

This keeps repeated bridge turns substantially smaller than the previous design that resent the complete policy on every wake. A migrated v0.2 conversation receives one new bootstrap after upgrade and then switches to compact wake mode.

The wake-up policy still requires the next ChatGPT turn to:

1. inspect the latest daemon status and exact task result evidence for the target repository;
2. avoid queueing another task while the task for this active goal is running;
3. continue with only the next necessary bounded task after the previous one finishes;
4. stop when the active autonomous goal is complete;
5. pause when user action is required;
6. keep no-change bridge turns terse instead of repeatedly summarizing the same status.

A new conversation still needs an explicit active goal and access to the relevant GitHub repositories. The bridge prompt alone cannot reconstruct an unstated goal or hidden project context.

Canonical execution rules remain in `AGENTS.md` and `docs/OPERATIONS.md`.

## Multi-conversation scheduler model

The extension stores conversation-scoped state. Each configured conversation has its own enabled state, alarm, optional repository id, interval override, last/next-run timestamps and control-marker dedupe state.

A `STOP`, `PAUSE`, `RESUME`, `NEXT` or `INTERVAL` command from one conversation must never change another conversation. The global master switch may suspend all bridge alarms, but it preserves the individual conversation configuration so scheduling can resume without reconstructing it.

The extension scheduler is independent from Local Agent execution concurrency. Multiple ChatGPT conversations may be awake or waiting concurrently while `agent_parallel.py` still enforces the executor's repository/resource admission contract.

## Control-plane locations

For a repository using the standard control branch:

```text
branch: agent-control

.agent/tasks/<task-id>.json       planner -> executor
.agent/runs/<task-id>.json        live execution evidence
.agent/results/<task-id>.json     terminal execution evidence
.agent/status/daemon.json         repository worker/daemon status
.agent/daemon/control.json        maintenance/status controls
.agent/daemon/acks/*.json         maintenance/status acknowledgements
```

Normal coding or verification work is queued by creating a unique file under `.agent/tasks/` on the target repository's `agent-control` branch. Do not hand-edit local control clones.

## Autonomous turn algorithm

Every bridge wake-up must follow this order:

1. Identify the active autonomous goal from the conversation.
2. Identify the target repository for that goal and read its latest daemon status.
3. If `current_task_id` is non-null or status/result evidence shows the task for this goal is still active, do not queue another task.
4. If the previous task has a terminal result, inspect the exact result before deciding what comes next.
5. On success, compare the evidence with the remaining goal and queue only the next necessary bounded task.
6. On failure, diagnose the published failure evidence. Queue a new task only when there is a concrete next action. Never replay or mutate the old task payload.
7. If user action is required, end the assistant response with the bridge `PAUSE` marker.
8. If the goal is complete, end the assistant response with the bridge `STOP` marker.
9. Otherwise end the response with a one-shot `NEXT` marker at an appropriate cadence. `NEXT` is the durable keep-alive: it arms or re-arms this conversation even if an earlier conversation-local `STOP`/`PAUSE` disabled it.

The autonomous planner loop is sequential per active conversation goal, not globally serial. While this conversation is following a running task for that goal, do not queue another task for the same goal. The production executor may still run unrelated tasks from other conversations or repositories concurrently when resource admission permits it. Resource classification remains conservative, and repository-specific status/run/result evidence determines whether the task this conversation is following is active.

## Post-queue liveness pacing

Immediately after queueing a new task, prefer one short Chat Bridge re-check after about 30 seconds instead of waiting for the normal long-task cadence. In v0.3 this should normally be expressed as a one-shot marker:

```text
[LAB:NEXT=30s]
```

The purpose of this first wake is only to catch start-up failures quickly: rejected task payloads, wrong expected SHA, missing branch/worktree, resource admission problems, syntax/import errors, commands that fail immediately, or a daemon that never claims the task.

On that first re-check:

1. inspect terminal result first if one already exists;
2. otherwise inspect the exact run/attempt plus daemon status;
3. if the task failed, diagnose it immediately and continue only with a new bounded task when the evidence supports a concrete fix;
4. if the task is actively producing output or healthy heartbeats, use a later one-shot `NEXT` appropriate to the expected remaining duration, or simply return to the configured interval;
5. do not replace the normal interval with a persistent 30-second cadence across a multi-minute or multi-hour healthy task.

`NEXT` arms or re-arms this conversation and changes only its next bridge alarm. It does not enable the global master switch, change the persistent interval, alter Local Agent polling, permit duplicate task execution, or change the rule that only one task for the active conversation goal is followed at a time.

## Task rules

Task ids are immutable within a repository. Every autonomous continuation task must use a new unique id.

A minimal read-only task looks like:

```json
{
  "id": "example-readonly-001",
  "mode": "commands",
  "work_branch": "main",
  "allow_write": false,
  "resources": [],
  "command_timeout": 60,
  "task_timeout": 180,
  "commands": [
    "git status --short && git rev-parse --short HEAD"
  ]
}
```

A bounded write task can declare `writes`, `deletes`, or `patch` with `allow_write: true`, followed by explicit commands and verification. Structured coding tasks should use the `efficient-verification-v1` policy described in `docs/OPERATIONS.md` when verification cost and intent need to be explicit.

The planner must not assume that a command succeeded because it was queued. The published terminal result is the source of truth.

## Evidence rules

Use evidence in this order:

1. terminal result for the exact task id and digest;
2. live run/progress for the exact attempt when still running;
3. current repository daemon status;
4. source/diff/test output referenced by those results;
5. planner analysis.

Important result fields include:

- `status`;
- `task_digest`;
- `attempt_id`;
- command `exit_code` and captured `output`;
- timeout, idle-timeout, memory-limit and background-process-leak flags;
- `git_status` and `git_diff`;
- finalization/checkpoint failure evidence when present.

Do not infer success from stale status alone when a terminal result should exist.

## Bridge control protocol

A bridge command is accepted only when it is the final non-empty line of the latest assistant message in the same configured conversation. Controls are conversation-scoped.

Preferred compact markers:

```text
[LAB:STOP]
[LAB:PAUSE]
[LAB:RESUME]
[LAB:NEXT=30s]
[LAB:NEXT=10m]
[LAB:INTERVAL=30m]
[LAB:INTERVAL=AUTO]
```

The older full prefix remains accepted for compatibility:

```text
[LOCAL_AGENT_BRIDGE:STOP]
[LOCAL_AGENT_BRIDGE:PAUSE]
[LOCAL_AGENT_BRIDGE:RESUME]
[LOCAL_AGENT_BRIDGE:NEXT=30s]
[LOCAL_AGENT_BRIDGE:INTERVAL=30]
[LOCAL_AGENT_BRIDGE:INTERVAL=AUTO]
```

Use the markers as follows:

- `STOP`: autonomous goal complete; disable only this conversation and clear its assistant interval override.
- `PAUSE`: user or external manual action is required; disable only this conversation while preserving its interval override.
- `RESUME`: explicitly re-enable only this conversation and schedule a near-term retry.
- `NEXT=<duration>`: arm or re-arm this conversation and set its next wake time. It does not override the global master switch or persistent interval. Supported durations are seconds (`s`) or minutes (`m`), bounded from 30 seconds through 24 hours.
- `INTERVAL=<minutes>`: set a persistent pacing override for this conversation.
- `INTERVAL=AUTO`: remove this conversation's override and return to the remote/fallback interval.

Do not put a real control marker as the final line of explanatory examples unless the command is intended to execute.

## Completion criteria

An autonomous goal is complete only when the requested outcome is supported by execution evidence. Depending on the goal, that can require source changes, focused verification, repository-wide gates, publication, or hardware interaction.

Do not continue generating cleanup or improvement tasks merely because the executor is idle. Idle means capacity is available; it does not create new scope.

When the requested scope is complete, summarize the evidence briefly and stop that conversation's bridge loop.

## Failure and manual-action policy

Pause instead of guessing when progress requires information or action that ChatGPT cannot safely perform, for example:

- reconnecting or physically manipulating hardware;
- approving an external account action;
- selecting between materially different product or design choices not resolved by the stated goal;
- restoring credentials or access that are unavailable to the planner/executor.

A deterministic task failure does not automatically require user intervention. If the published evidence gives the planner enough information to create a safe next task, the planner may continue autonomously with a new unique task id.

## End-to-end validation

One configured conversation loop is considered operational when all of the following have been demonstrated in the real deployment:

1. ChatGPT can queue a task through the repository control branch.
2. `local-agent` executes it and publishes a terminal result.
3. The Chat Bridge wakes the same conversation without user input.
4. ChatGPT reads the real result and queues a second task only after the relevant task is no longer active.
5. The second result is inspected on a later bridge wake-up.
6. ChatGPT terminates that conversation's loop with `STOP` after the goal is complete.

Multi-conversation bridge validation additionally requires two configured conversations to retain separate alarms and control state, including proof that pausing/stopping one does not pause/stop the other.

This validates the coordination loop. It does not remove the requirement for task-specific verification or user intervention when the goal itself needs external/manual actions.

## Planner output policy

For substantial autonomous coding tasks, prefer `efficient-verification-v1` with work/focused stages and exactly one final full stage. Long successful test/build stages should normally use `output_policy: "summary"` when their line-by-line output is not useful; terminal result evidence remains authoritative.

Bridge wake responses should also avoid repeated narrative when evidence is unchanged. The compact wake exists to trigger a decision, not to grow the conversation with redundant status summaries.
