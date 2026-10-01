# Conversation Fabric — next chat handoff

Status: ready for a clean new ChatGPT window.

Repository: `MichalMatu/local-agent`
Working branch: `feature/conversation-fabric-superchat`
Production base at design start: `main@474000b5d4b015958fe92be491968dc4625b4a84` (`v4.18.24`)
Draft PR: `#85` — design/validation only; do not merge.

## 1. Goal

Build the first safe foundation for **Superchat / Conversation Fabric**: one parent ChatGPT conversation can create bounded child conversations for separate modules/roles, preserve progress through durable evidence, and later integrate exact child outputs.

Do not start by wiring full Execution Fabric or by making browser automation authoritative.

The immediate work is **Phase 0A + Phase 0B**:

1. freeze pure child-request/identity/lifecycle contracts;
2. prove the fragile new-chat browser assumption in a synthetic Chromium fixture;
3. keep production runtime behavior unchanged until those contracts/spike are proven.

## 2. Read first

Read these in order before editing:

1. `AGENTS.md`
2. `docs/conversation_fabric/PREIMPLEMENTATION_REAUDIT.md`
3. `docs/conversation_fabric/SUPERCHAT_ARCHITECTURE.md`
4. `docs/conversation_fabric/IMPLEMENTATION_PLAN.md`
5. `docs/conversation_fabric/SOURCE_ASSET_MAP.md`
6. relevant current-main Chat Bridge owners:
   - `chat_bridge/control_protocol.js`
   - `chat_bridge/bridge_state.js`
   - `chat_bridge/worker_state.js`
   - `chat_bridge/worker_delivery.js`
   - `chat_bridge/worker_transport.js`
   - `chat_bridge/content.js`
7. donor files only as reference when required:
   - `feature/chat-bridge-event-wake`
   - `feature/openworker-governance`

Current `main` always wins conflicts with donor branches.

## 3. Re-audit decisions that must not regress

Treat these as hard design constraints unless a new audit proves otherwise.

### Current Local Agent repository concurrency

One registered repository executes at most one Local Agent task at a time. `work_branch` does not create another scheduler lane.

Do not implement same-repository Local Agent parallel execution in Conversation Fabric v1.

Same-repository child chats may reason in parallel and may own separate GitHub branches; their Local Agent tasks remain serialized.

### Existing Chat Bridge delivery requires a concrete conversation URL

Current ordinary delivery is exact-URL `/c/<id>` based. Do not weaken it to support a blank new-chat page.

Child creation needs a separate pre-registration **spawn transaction**.

### Identity

Durable child identity is:

```text
child_request_id + canonical request digest
```

and, after registration, the exact canonical ChatGPT conversation URL/id.

Do not use Chrome tab id or `chat-<fnv32>` as durable/security identity.

### State ownership

Do not overload existing production `bridgeState` schema v3.

Conversation Fabric browser/spawn cache should use a separate storage namespace/schema.

### Native Messaging

The event-wake donor Native Messaging host stays notification-only.

Do not add registration writes to it during Phase 0/1.

A later separate bounded conversation-registration host/protocol is the preferred design.

### Workflow/Git authority

Execution Fabric donor workflow state is local durable state, not already a GitHub central database.

Use one authority per record type as defined in the re-audit; do not invent two independently mutable workflow truths.

### Planner progress

Do not repurpose executor `[AGENT_PROGRESS]` for child reasoning checkpoints.

Conversation Fabric will have separate `child_checkpoint` / `child_terminal` contracts.

### GitHub connector limitation

Prompt/hard-binding policy does not technically sandbox a broadly-permissioned GitHub connector. Do not claim connector-level enforcement that does not exist.

## 4. Phase 0A task — pure contract/state only

Implement no browser or daemon side effects yet.

Proposed package ownership (names may be refined during audit):

```text
local_agent/conversation/__init__.py
local_agent/conversation/contract.py
local_agent/conversation/identity.py
local_agent/conversation/state.py
```

Do not add `store.py` until the immutable schema/state semantics are stable enough to persist.

### Define bounded schema for `ChildRequest`

At minimum:

- schema version;
- request id;
- workflow id;
- workflow revision;
- node id;
- role;
- exact parent conversation URL;
- repository id/name;
- canonical `agent_binding`;
- work branch when role requires it;
- dependencies/input references;
- bounded goal/scope;
- required outputs;
- created timestamp;
- canonical deterministic request digest.

Do not allow browser-discovered child URL/tab id in the immutable request.

### Define `ChildRegistration`

At minimum:

- exact request id + digest;
- exact parent URL;
- exact child URL;
- lifecycle generation;
- registration timestamp.

All repository/binding/role/work-branch authority comes from the already-admitted request, not from browser input.

### Define logical child lifecycle

Starting point:

```text
requested
registration_pending
active
terminal_pending_evidence
terminal_recorded
retired
```

Define exact allowed transitions and idempotent repeats.

Browser spawn states are separate and should not be merged into this state machine.

### Required tests

Add focused pure tests for:

- canonical digest stable across JSON formatting/key order;
- malformed/oversized ids/text/arrays;
- invalid role;
- invalid parent/child URL;
- invalid/cross-binding identity;
- registration with wrong request digest;
- conflicting second child URL for one request;
- idempotent identical registration;
- stale lifecycle generation;
- invalid lifecycle transitions;
- terminal/retired non-regression;
- one-level parent semantics;
- same-repo branch requirement for implementation/integration roles if the final contract keeps it.

No Chrome, Git or subprocess dependency in these tests.

## 5. Phase 0B task — synthetic browser feasibility spike

After pure contract tests are coherent, build a disposable Chromium/synthetic-page spike. Keep it lab/test-only; do not expose a production `SPAWN_CHILD` command yet.

The synthetic ChatGPT fixture must model the important route behavior:

```text
https://chatgpt.com/   # no concrete conversation identity
-> composer available
-> first user prompt submitted
-> same tab transitions to https://chatgpt.com/c/<generated-id>
-> first user message remains observable
```

Prove a prototype spawn transaction can:

1. persist exact request/digest before tab actuation;
2. open/use a new tab;
3. inject one bootstrap containing request id/digest markers;
4. confirm the accepted first user turn;
5. capture the new exact `/c/<id>` URL;
6. recover after service-worker restart;
7. not duplicate a child when delivery confirmation is lost after actual acceptance.

### Mandatory negative cases

- tab closed before identity exists;
- unrelated text appears in composer;
- unexpected route/origin after send;
- duplicate spawn request;
- worker restart after tab created;
- worker restart after user turn accepted but before registration cache write;
- send timeout where page actually transitioned;
- second queued spawn while first is unresolved.

Serialize spawn actuation in this spike.

### Important implementation rule

Do **not** modify `worker_delivery.js` so existing ordinary delivery accepts an unknown/new-chat URL.

Use a separate test/lab spawn path. Once the child has a concrete exact URL, normal current-main delivery semantics can take over.

## 6. Manual attach fallback design

During Phase 0B, document and preferably model a recovery path where the operator opens a new ChatGPT conversation and explicitly attaches one pending exact child request.

The first production-capable implementation must not depend on automatic new-tab UI behavior as the only way to continue a workflow.

## 7. Donor code policy

### `feature/chat-bridge-event-wake`

Use later for:

- result outbox;
- notification Native Messaging;
- `WAIT_TASK`;
- event/restart tests.

Do not copy old central Bridge files over current main.

### `feature/openworker-governance`

Use later for:

- workflow schemas/state/revisions;
- Git task publication/cancellation;
- shared control-Git lock;
- disposable-Git tests.

Do not assume it supports same-repository concurrent tasks or GitHub-central workflow state.

## 8. Boundaries for this next chat

Do not:

- modify `main`;
- merge PR #85;
- restart Local Agent;
- release/bump production version;
- modify live Chat Bridge runtime/config branch;
- enable a real `SPAWN_CHILD` control in production;
- perform a live ChatGPT child-creation test without explicit operator approval;
- transplant full Execution Fabric;
- weaken repository execution leases;
- expand Native Messaging authority.

Allowed:

- branch-only docs/code/tests on `feature/conversation-fabric-superchat`;
- pure contract/state implementation;
- synthetic/disposable Chromium test harness work;
- exact donor-code inspection;
- CI/focused tests on the branch.

## 9. Expected end state of the next chat

The next chat should finish with:

- coherent Phase 0A contract/state code + focused tests;
- documented schema decisions and any deviations from provisional design;
- synthetic Phase 0B spawn feasibility evidence, or a precise blocker if the model cannot be proven;
- no production runtime behavior change;
- no main merge;
- updated handoff/status describing the next safest step.

If Phase 0B exposes a wrong assumption, change the architecture before proceeding rather than forcing the implementation to match the old plan.

## 10. Copy/paste prompt for the new ChatGPT window

```text
Continue work on MichalMatu/local-agent, but ONLY on branch `feature/conversation-fabric-superchat`.

Do not touch or merge `main`, do not restart/update the live Local Agent, do not modify the live `chat-bridge-state` runtime branch, and do not enable any production child-spawn behavior.

Start by reading, in this order:
1. AGENTS.md
2. docs/conversation_fabric/PREIMPLEMENTATION_REAUDIT.md
3. docs/conversation_fabric/SUPERCHAT_ARCHITECTURE.md
4. docs/conversation_fabric/IMPLEMENTATION_PLAN.md
5. docs/conversation_fabric/SOURCE_ASSET_MAP.md
6. docs/conversation_fabric/HANDOFF_NEXT_CHAT.md

Goal for this clean session: execute Conversation Fabric Phase 0A and then the test-only Phase 0B feasibility spike.

Phase 0A:
- implement pure bounded ChildRequest / ChildRegistration identity+digest contracts and the logical child lifecycle state machine;
- keep browser spawn state separate from logical workflow state;
- add strong positive/negative pure tests;
- no Git/Chrome/subprocess side effects in the pure modules.

Phase 0B:
- create a synthetic/disposable Chromium fixture that models a blank ChatGPT new-chat page becoming `/c/<id>` after the first accepted user prompt;
- prototype a LAB/test-only spawn transaction that persists request/digest before actuation, injects one bootstrap marker, captures the resulting exact child URL, survives service-worker restart, and does not duplicate a child after uncertain delivery;
- serialize spawn creation for v1;
- design/test a manual attach fallback;
- do NOT weaken the existing exact-URL `worker_delivery.js` path.

Critical re-audit facts you must preserve:
- current Local Agent executes only one task per registered repository at a time; `work_branch` is not a parallel scheduler lane;
- same-repo child chats may reason on separate branches in parallel, but Local Agent execution stays serialized in v1;
- current Bridge ordinary delivery requires a concrete `/c/<id>` URL, so new-chat creation needs a separate pre-registration spawn transaction;
- durable child identity is request id+digest, then exact child URL; tab id and `chat-<fnv32>` are not durable identities;
- existing `bridgeState` schema v3 should not be overloaded; use a separate Conversation Fabric state namespace later;
- the donor event Native Messaging host remains notification-only; do not add registration writes to it;
- Execution Fabric donor state is local, not already a GitHub-central workflow database;
- planner child checkpoints are separate from executor `[AGENT_PROGRESS]`;
- do not claim ChatGPT GitHub connector permissions are technically sandboxed by hard binding.

Use `feature/chat-bridge-event-wake` and `feature/openworker-governance` only as donor/reference branches. Current main/v4.18.24 behavior wins conflicts.

Before coding, verify the current branch HEAD and re-audit the exact files you will touch. If any assumption in the handoff is contradicted by current code, stop that implementation direction, document the contradiction, and adjust the plan first.

When done, run focused tests plus the appropriate branch verification for the changed scope, record exact HEAD/evidence, update Conversation Fabric status/handoff docs, and stop before any live ChatGPT or production release action.
```
