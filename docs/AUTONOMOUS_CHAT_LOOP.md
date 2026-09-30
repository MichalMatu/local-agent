# Autonomous Chat Planner Loop

This document defines the current autonomous loop connecting one ChatGPT conversation, Chat Bridge 0.6.0, GitHub desired state and deterministic Local Agent execution.

## Ownership

```text
ChatGPT             planner / coding decisions
GitHub              durable task + conversation desired state
Chat Bridge          browser wake transport
Local Agent          deterministic bounded executor
Target repository    source/work result
```

The ChatGPT DOM is not a scheduling source of truth.

## Conversation binding and planner scope

Every configured conversation has one canonical Bridge binding:

```text
conversation id
repository id + owner/name
canonical agent_binding
binding revision
```

`planner_scope=repository` limits planning to that repository. `planner_scope=multirepo` may target only repositories in the current validated runtime catalog while keeping the conversation binding unchanged.

The canonical `host-ops` conversation is the multirepo operator workspace. Every delegated Local Agent task still uses the exact canonical `agent_binding` of its **target** repository. An execution-disabled target such as `local-agent` may be inspected/edited through direct GitHub operations but must not receive a Local Agent task.

Do not use normal work to Rebind between catalog repositories in a multirepo conversation.

## Schedule/status control: GitHub only

For a conversation with an exact `conversation_controls` record in `chat-bridge-state/chat_bridge/runtime.json`, GitHub is authoritative for:

- `STATUS`;
- `PAUSE`;
- `RESUME`;
- `NEXT`;
- `INTERVAL`.

The planner must inspect/update that record through GitHub. Every schedule mutation increments `control_generation`; status reads do not.

Do **not** emit assistant LAB schedule markers for a GitHub-managed chat. They are legacy compatibility no-ops.

Example desired state:

```json
{
  "conversation_id": "chat-e8ad8275",
  "repository_id": "host-ops",
  "repository": "MichalMatu/host-ops",
  "agent_binding": "16d688b6-b0ef-4905-a5bd-24e59c99cfb4",
  "binding_revision": 1,
  "control_generation": 4,
  "enabled": false,
  "interval_minutes": 5,
  "next_wake_at": null,
  "updated_at": "2026-09-30T01:41:54+02:00"
}
```

The global Bridge Master switch is independent manual operator state and must never be changed by conversation desired state.

## Planner turn

At every user or Bridge wake:

1. identify the conversation binding and authorized planner scope;
2. identify the active goal; do not create unrelated work;
3. inspect only the repository/task/run/result evidence needed for the next decision;
4. check for an already-active task before writing the same branch or queueing equivalent work;
5. choose direct GitHub work when a precise diff plus CI is sufficient;
6. use Local Agent only when local commands, builds, tests, devices or machine state are required;
7. never launch or delegate to local Codex/another coding-agent CLI from a Local Agent task;
8. verify exact commit/result evidence before declaring completion;
9. choose one continuation state: complete, pause, next wake, or exact-task cancellation.

## Local Agent task discipline

One autonomous conversation follows at most one active Local Agent task for its current goal. This does not serialize unrelated repositories globally; the parallel supervisor may run unrelated tasks when resource/lease policy permits.

Every task must use the target repository's exact runtime-catalog binding. Never guess repository ids or bindings.

If a healthy active task is still running, do not poll at 30-second cadence. A first liveness re-check should normally be no sooner than about two minutes; use 5-10 minutes for multi-minute builds/tests unless evidence supports a nearer completion.

If evidence already proves an active task cannot achieve its goal, issue repository-scoped cancellation for that exact task id, then wait for cancellation/result evidence before replacing it.

Resource/capacity waiting is a continuation state, not completion.

## Scheduling continuation

When unfinished work needs a future wake, update the exact GitHub conversation control:

```text
control_generation += 1
enabled = true
next_wake_at = exact offset-aware future timestamp
```

`NEXT` is one-shot desired timing. After it fires, normal interval behavior may resume. Do not repeatedly rewrite the same generation.

For recurring pacing:

```text
control_generation += 1
enabled = true
interval_minutes = bounded minutes or null for runtime default
next_wake_at = null
```

When the goal is complete or operator attention is required:

```text
control_generation += 1
enabled = false
next_wake_at = null
```

Leave the conversation PAUSED after validation/release work unless continued automation is explicitly needed.

## Wake delivery

Chat Bridge polls GitHub desired state with a dedicated MV3 alarm, reconciles exact binding/generation state and schedules the conversation alarm. At wake time it must:

1. select the exact preferred ChatGPT tab/conversation;
2. fail closed if ChatGPT is generating;
3. preserve any operator-authored composer content;
4. write the exact Bridge prompt;
5. re-resolve the live enabled Send control immediately before submission;
6. click the live control (with `requestSubmit()` only as bounded fallback);
7. confirm the exact submitted user turn.

The extension never stores a GitHub credential and never writes desired state itself.

## Binding and maintenance migration surface

Binding and maintenance have not yet moved to the GitHub desired-state model. Explicit migration paths remain:

- `ADD`, `REBIND`, `REMOVE`;
- content/Bridge reload and worker maintenance;
- narrow diagnostics not replaced by GitHub status.

These paths must not be used for ordinary schedule/status operations.

## Assistant errors and exhaustion

DOM inspection remains valid for structured browser facts that GitHub cannot provide:

- visible generation Stop state;
- submitted-user confirmation;
- recognized terminal Retry cards;
- conversation-length exhaustion.

Automatic Retry remains restricted to exact preferred tab/conversation, current binding revision/generation, enabled state and Bridge ownership of the triggering prompt. Unknown Retry-looking errors fail closed.

## Release/verification loop

For a Bridge/runtime behavior change:

1. isolate a branch from current `main`;
2. add focused positive/negative tests;
3. run exact-SHA full CI including real-extension browser and macOS smoke;
4. live-test the candidate with a bounded GitHub control sequence;
5. end live validation PAUSED;
6. update release notes/changelog/current contracts;
7. re-run exact-SHA CI;
8. explicitly merge/advance `main`;
9. restore a clean installed checkout, self-update/restart and verify live revision/version;
10. remove obsolete candidate branches/worktrees only after production proof.

## Canonical references

- `docs/GITHUB_BRIDGE_CONTROL.md` — conversation desired-state contract;
- `chat_bridge/README.md` — extension surface and installation;
- `docs/HOST_OPS_MULTIREPO.md` — multirepo planner scope;
- `docs/CHATGPT_DOM_CONTRACT.md` — remaining DOM compatibility boundary;
- `docs/GOLDEN_STANDARD.md` — release/runtime invariants;
- `docs/OPERATIONS.md` — Local Agent operations and recovery.
