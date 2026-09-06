# Deterministic Superchat Supervisor

This document captures the design for a higher-level supervisor that manages long-running ChatGPT worker conversations above Chat Bridge while preserving Local Agent's deterministic execution boundary.

```text
Superchat planner / manager
        |
        v
Deterministic Chat Supervisor
        |
        v
Chat Bridge
        |
        v
Bound worker conversations
        |
        v
Deterministic Local Agent executor
```

The LLM decides what work should happen. Deterministic infrastructure owns lifecycle, binding, retries, rollover, persistence, deduplication and recovery.

## Core invariants

- A ChatGPT conversation remains hard-bound to one immutable `agent_binding` and one repository.
- Repository identity is never inferred or switched from model context.
- Rollover changes ChatGPT conversation identity, not repository identity.
- A long-running goal survives conversation replacement.
- Local Agent remains the deterministic executor; the new supervisor belongs above Chat Bridge.
- Queueing or an LLM summary is never treated as execution proof. Exact repository/task/result evidence remains authoritative.

## Durable goal identity

Each long-running unit of work needs a stable `goal_id` independent of any ChatGPT conversation id.

Example:

```json
{
  "goal_id": "matrix-display-refactor",
  "repository_id": "matrixhub",
  "repository": "MichalMatu/MatrixHub",
  "agent_binding": "<canonical-uuid>",
  "status": "running",
  "active_chat_id": "<bridge-chat-id>",
  "generation": 3,
  "chat_history": ["<g1>", "<g2>", "<g3>"],
  "last_task_id": "matrix-047",
  "last_commit": "a82bc19",
  "next_action": "verify display reconnect",
  "rollover": null
}
```

Recommended goal states:

```text
IDLE
PLANNED
STARTING
RUNNING
HANDOFF_REQUESTED
ROTATING
BLOCKED
COMPLETED
FAILED
NEEDS_SUPERVISOR
```

Use an explicit state machine instead of distributed boolean combinations.

## Worker generations and goal lease

A conversation is one worker generation for a goal:

```text
GOAL
  -> worker generation 1 (retired)
  -> worker generation 2 (active)
  -> worker generation 3 (future)
```

At most one worker may be authoritative for a goal at a time. Creating a replacement does not immediately make it active. Activation happens only after the replacement conversation has been created, bound and durably registered.

This avoids two scheduled chats independently continuing the same goal after a race, duplicate delivery or service-worker restart.

## Idempotent lifecycle operations

Any supervisor operation with external effects must have a durable idempotency key.

Examples:

```text
spawn:matrix-display-refactor:g4
rotate:matrix-display-refactor:g3-to-g4
bootstrap:matrix-display-refactor:g4
retire:matrix-display-refactor:g3
```

Repeating the same operation after restart must resume/reconcile it rather than creating another worker.

This is intentionally stronger than ordinary wake delivery. Duplicate `CREATE_CHAT`, `ROTATE` or `ASSIGN_GOAL` is not acceptable.

## Durable operation journal

Manifest V3 service workers may disappear between asynchronous steps, so rollover progress must not live only in memory.

Persist a journal before the first external side effect:

```json
{
  "operation_id": "rotate:matrix-display-refactor:g3-to-g4",
  "goal_id": "matrix-display-refactor",
  "kind": "rollover",
  "state": "creating_replacement",
  "from_chat_id": "<old-chat>",
  "from_generation": 3,
  "to_generation": 4,
  "started_at": "...",
  "handoff_checkpoint": "...",
  "candidate_tab_id": 123,
  "candidate_chat_url": null,
  "candidate_chat_id": null
}
```

Suggested operation states:

```text
REQUESTED
SNAPSHOTTED
CREATING_REPLACEMENT
BOOTSTRAPPING
WAITING_FOR_CONCRETE_URL
REPLACEMENT_REGISTERED
ACTIVATING
OLD_WORKER_RETIRED
COMPLETED
FAILED
```

On startup, reconcile every non-terminal operation before issuing a new external action.

## Two-phase rollover

Never stop the old worker before a replacement is safely established.

Correct order:

```text
old worker active
      |
      v
persist rollover journal
      |
      v
capture handoff snapshot
      |
      v
create replacement conversation
      |
      v
send continuation bootstrap
      |
      v
observe concrete /c/<new-id>
      |
      v
persist replacement binding record
      |
      v
switch goal.active_chat_id / generation
      |
      v
retire old worker
      |
      v
mark rollover completed
```

Stopping the old worker first can orphan the goal if the browser, extension or network fails while creating the replacement.

## Deterministic conversation exhaustion

The initial implementation should rely on the observed terminal ChatGPT exhaustion state, not on guessed context-window usage.

The canonical DOM contract is documented in [`CHATGPT_DOM_CONTRACT.md`](CHATGPT_DOM_CONTRACT.md). The useful observed signals are:

- `[data-message-author-role="assistant"]`;
- descendant `.text-token-text-error`;
- normalized text containing `You've reached the maximum length for this conversation`;
- exactly one descendant `button` whose normalized visible text is `Start new chat`.

Do not depend on generated utility classes, SVG sprite ids or DOM depth.

The deterministic transition is:

```text
RUNNING
  -> HANDOFF_REQUESTED
  -> ROTATING
```

Predictive rotation based on estimated tokens, message count or conversation age can be added later as an optimization, but it must not be required for correctness.

## Creating the replacement conversation

Opening a tab is easy; making the operation recoverable is the important part.

Expected sequence:

```text
open/navigate to new ChatGPT UI
      |
      v
wait for usable composer
      |
      v
inject continuation bootstrap
      |
      v
submit first message
      |
      v
wait until ChatGPT assigns concrete /c/<new-id>
      |
      v
persist new Bridge conversation record
```

A root/new-chat page may not yet have a concrete `/c/<id>` URL. Do not make the replacement authoritative before the first message is confirmed and the concrete URL is observed.

When rollover starts from the exhaustion UI, use `Start new chat` only when the exact DOM contract is satisfied. Missing or ambiguous controls must fail closed.

## Binding rules during rollover

The replacement receives:

- a new ChatGPT conversation id;
- a new Bridge conversation record;
- a fresh assistant baseline;
- the same `repository_id`;
- the same repository name;
- the same immutable `agent_binding`;
- the same `goal_id` with an incremented worker generation.

Never copy the old `LA_CHAT` identity into the replacement. Never use rollover as an implicit Rebind mechanism.

## Structured handoff checkpoint

The handoff should be structured and bounded rather than relying only on free-form model prose.

Example:

```json
{
  "goal_id": "matrix-display-refactor",
  "generation": 3,
  "objective": "...",
  "completed": [],
  "remaining": [],
  "last_commit": "...",
  "active_task_id": null,
  "verified_results": [],
  "blockers": [],
  "next_action": "..."
}
```

The continuation bootstrap should include this bounded state plus pointers to authoritative repository/Local Agent evidence.

The replacement worker must verify current source, task status and terminal result evidence before continuing. The previous worker's handoff is context, not proof.

## Superchat versus deterministic supervisor

The AI superchat may decide:

- what goal to work on next;
- whether a failed direction should be abandoned or diagnosed;
- whether a goal should be split;
- whether user input is needed;
- whether work requires another separately bound repository worker.

The deterministic supervisor owns rules such as:

```text
if conversation exhausted -> begin idempotent rollover
if replacement registered -> activate replacement
if old worker still scheduled after activation -> retire old worker
if operation interrupted -> reconcile journal
if retry limit exceeded -> NEEDS_SUPERVISOR
if worker reports terminal completion -> wake superchat planner
```

Do not let the superchat directly mutate raw Bridge binding state.

## Retry and circuit breaker

Lifecycle retries must be bounded. A simple first policy is sufficient:

```text
max_spawn_attempts = 3
max_rollover_attempts = 2
bounded/exponential backoff
```

After the limit, transition to `NEEDS_SUPERVISOR` or another explicit blocked state. Never loop forever creating tabs or replacement chats.

Retries for the same logical operation must reuse the same idempotency identity.

## Crash/restart recovery

After extension/service-worker/browser restart:

1. load durable goals and operation journals;
2. inspect non-terminal operations;
3. reconcile known tabs/conversation URLs where possible;
4. determine whether a candidate replacement was already created/registered;
5. resume the next safe state transition;
6. never create another replacement merely because in-memory state was lost.

Prefer duplicate prevention over aggressive automatic repair.

## Failure policy

Fail closed when required identity or lifecycle evidence is ambiguous, including:

- repository/binding changed during the operation;
- no exact exhaustion/new-chat control is found;
- multiple candidate controls match;
- composer is unavailable or changed during delivery;
- first bootstrap submission cannot be confirmed;
- concrete `/c/<new-id>` is not observed;
- replacement record cannot be durably persisted;
- two different workers appear authoritative for one goal.

Old worker records remain immutable history and are not deleted during normal rollover.

## Bridge state evolution

A future schema should separate per-conversation transport state from cross-conversation supervisor state:

```json
{
  "schemaVersion": 4,
  "settings": {},
  "conversations": {},
  "goals": {},
  "operations": {}
}
```

`conversations` owns per-chat transport, binding and scheduling. `goals` owns continuity across conversations. `operations` owns crash-recoverable lifecycle transactions.

## Suggested implementation boundary

Most implementation belongs in Chat Bridge, not Local Agent runtime:

- `bridge_state.js` — schema migration and durable `goals` / `operations` state;
- new `worker_supervisor.js` — deterministic goal/lifecycle state machine;
- `worker_conversations.js` — privileged create/register primitives that do not weaken normal hard binding;
- `worker_delivery.js` — bootstrap delivery and reconciliation support;
- `content.js` — exact exhaustion/new-chat/readiness signals;
- tests — state machine, idempotency, restart recovery, duplicate prevention and real Chromium rollover smoke.

The existing Local Agent execution boundary should remain deterministic and unchanged unless the supervisor later needs a small explicit status/control primitive.

## Saved exhausted-page fixture

A locally saved ChatGPT page captured at terminal conversation length is valuable test evidence. Do not commit the entire raw saved page blindly because it may contain unrelated conversation text, account-specific data, volatile application assets and large generated markup.

Instead:

1. keep the raw capture outside the repository as source evidence;
2. extract a minimal sanitized DOM fixture containing only the exhaustion assistant message and the exact required surrounding structure;
3. remove conversation content, account/session data, scripts, asset URLs and generated classes that are not part of the contract;
4. add browser/unit regression coverage against that fixture;
5. keep one real Chromium smoke test for the integration path.

The fixture should prove the contract while minimizing privacy leakage and brittleness.