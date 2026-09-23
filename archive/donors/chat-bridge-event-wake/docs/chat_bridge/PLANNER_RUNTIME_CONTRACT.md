# Chat Bridge planner runtime contract

This document defines the planner-facing prompt contract for Chat Bridge. It is intentionally separate from transport, executor and operator implementation detail: recurring wake payloads are a hot path and must stay small, while the first bootstrap is allowed to teach the operating model once.

## Goals

The planner-facing protocol must satisfy all of these at the same time:

1. preserve exact repository/conversation identity on every automatic wake;
2. teach the planner enough to choose direct GitHub work versus bounded Local Agent execution;
3. prefer event-driven `WAIT_TASK` for exact Local Agent task completion while retaining alarm fallback;
4. keep `NEXT` available for genuine time/external checks;
5. treat `task_result_ready` only as a wake hint and require exact terminal-result inspection;
6. never require a project-bound conversation to inspect another repository merely to learn the Bridge protocol;
7. avoid repeating static policy on every wake.

## Layering

Planner prompts have three layers.

### 1. Hard binding — every wake

Every automatic Bridge message carries the exact identity envelope:

```text
[LA_AGENT=<canonical UUID>] [LA_REPO=<repository id>] [LA_REPOSITORY=<owner/name>] [LA_CHAT=<conversation id>]
```

The accompanying binding policy is deliberately compact but remains fail-closed. It tells the planner to work only in the bound repository, never inspect/queue/cancel/execute/switch/rebind another repository, and to `PAUSE` when another repository is actually required.

For executable repositories it also repeats the exact required `agent_binding` for any Local Agent task. For the `local-agent` infrastructure binding it instead states that project task files must not be created.

This identity/policy layer is not removed for token savings. It is the routing safety boundary visible to the planner.

### 2. Bootstrap — once per add/rebind

The first actual wake after adding or explicitly rebinding a conversation is the teaching turn. The bootstrap is self-contained and establishes the durable operating model:

- ChatGPT is the planner;
- Local Agent is a deterministic bounded Mac/build/test/device executor, never a local Codex planner;
- stay inside the bound repository;
- read that repository's `AGENTS.md` and active handoff/development docs before edits;
- check active local tasks before same-branch writes;
- use direct GitHub edits when exact diff plus relevant CI are sufficient;
- use Local Agent when machine-local execution is required;
- verify the exact committed SHA for hybrid work;
- cancel only an exact task whose current evidence proves it cannot succeed;
- keep no-change turns terse.

The bootstrap must not tell a project-bound conversation to open `MichalMatu/local-agent` documentation. The full Local Agent docs are the implementation/developer source of truth; they are not a runtime dependency for another hard-bound repository.

The extension appends its capability-owned scheduling policy after the remote bootstrap so a stale production runtime cannot override event-driven pacing:

```text
one exact task -> WAIT_TASK -> event-driven wake + alarm fallback
NEXT -> time/external recheck only
task_result_ready -> wake hint; exact terminal result remains authoritative
```

The supported conversation-scoped schedule controls may be listed on bootstrap because this is the one-time teaching payload.

### 3. Recurring wake — compact continuation

A normal alarm/manual continuation after bootstrap contains only:

- exact binding envelope + compact hard-binding policy;
- short `[LA_WAKE]` continuation guidance;
- compact extension-owned `WAIT_TASK`/fallback/NEXT/event-hint policy.

It must not repeat the full bootstrap, command catalog explanations, Native Messaging architecture, control-plane file layout or Local Agent documentation pointers.

### 4. Terminal event wake — minimal action payload

When a non-bootstrap conversation receives a matching result event, it does **not** need the generic recurring wake text or another explanation of how to register `WAIT_TASK`: the watched event already happened.

The payload therefore contains only:

```text
<hard binding envelope + compact policy>
[LA_WAKE]
[LA_EVENT=task_result_ready]
[LA_TASK=<exact-task-id>]
Wake hint only. Read the exact result before deciding the next action; continue the active goal in this bound repository.
```

If the event arrives while `bootstrapPending` is still true, Bridge includes the one-time bootstrap first so a newly configured conversation is never asked to act on an event before learning its operating model.

## Hybrid wake model

The final model is deliberately hybrid:

```text
exact Local Agent task
  -> WAIT_TASK
  -> task_result_ready native event
  -> immediate conversation wake
  -> exact terminal result inspection

Native event unavailable/lost/restart race
  -> retained scheduled reconciliation alarm

time/external condition without a Local Agent task event
  -> NEXT=<duration>

normal recurring pacing
  -> INTERVAL / AUTO

operator demand
  -> Run now
```

Event-driven wake reduces unnecessary completion polling; it does not remove time-based/manual scheduling.

## Payload budgets

`chat_bridge/planner_pacing_contract.test.js` enforces character budgets for the generated prompt, using a representative executable repository binding:

- one-time bootstrap: **<= 1600 characters**;
- ordinary recurring wake: **<= 1100 characters**;
- non-bootstrap terminal event wake: **<= 700 characters**.

Character budgets are deterministic and tokenizer-independent. A rough English estimate of `characters / 4` is useful only for human comparison, not as a test oracle.

Before this compaction the observed representative payloads were approximately:

- normal wake: ~1674 characters (~418 rough tokens);
- event wake: ~1874 characters (~468 rough tokens).

The compact design targets roughly:

- normal wake: ~900 characters (~225 rough tokens);
- event wake: ~525 characters (~130 rough tokens);
- bootstrap: ~1325 characters (~330 rough tokens), paid once per add/rebind rather than on every continuation.

The exact generated length may vary with repository name/id/task id. The enforced character ceilings include representative identity values and are regression guards, not billing/tokenizer guarantees.

## Ownership of policy text

To avoid duplication and rollout coupling:

- remote runtime `bootstrap_prompt`/`wake_prompt` own generic planner/executor workflow guidance;
- `worker_binding.js` owns exact binding text and candidate capability-specific event-wake policy;
- `control_protocol.js::COMMAND_CATALOG` remains the source of truth for supported assistant controls;
- Local Agent developer docs own detailed execution/control semantics;
- target-repository `AGENTS.md`/handoff docs own repository-specific development rules.

A candidate extension must remain safe when production `chat-bridge-state` still serves an older runtime prompt. Capability-specific `WAIT_TASK` semantics are therefore appended by the extension after the remote runtime text until the production runtime is deliberately synchronized.

## Regression rules

Changes to planner prompts must preserve all of the following:

- every automatic wake retains all four identity envelope fields;
- hard binding remains fail-closed;
- executable tasks still receive the exact binding requirement;
- `local-agent` infrastructure binding remains non-executing;
- `WAIT_TASK` remains preferred for one exact active/queued Local Agent task;
- alarm reconciliation remains available as fallback;
- `NEXT` remains available for genuine time/external checks;
- event wake remains non-authoritative and requires exact result inspection;
- non-bootstrap event wake does not repeat generic recurring wake context;
- project-bound onboarding does not require cross-repository Local Agent doc inspection;
- prompt-size budget tests stay green.

Do not trade these invariants away merely to save more tokens.