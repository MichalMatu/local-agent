# Superchat implementation plan

This plan maps the proposed architecture onto the current Chat Bridge codebase.

## Current owners that should remain intact

### `chat_bridge/bridge_state.js`

Current responsibilities:

- schema version 3;
- global settings;
- conversation normalization/sanitization;
- legacy state migration;
- conversation upsert/patch/remove helpers.

Planned change:

- bump to schema version 4;
- add separate bounded `supervisor`, `goals` and `operations` domains;
- add v3 -> v4 migration;
- add state-machine helpers without weakening existing conversation sanitization.

Do not store all Superchat data inside `conversation` objects.

### `chat_bridge/worker_conversations.js`

Current important property:

`upsertConversation()` requires a concrete normalized ChatGPT conversation URL and resolves/validates a hard catalog binding. Existing binding mutation is an explicit operator Rebind path.

Planned change:

- keep normal `upsertConversation()` semantics unchanged;
- add an internal registration function for a conversation created by a validated supervisor operation;
- that function receives a catalog-selected repository/binding from durable operation state, never from model prose;
- preserve operator-only `rebindConversation()`.

### `chat_bridge/worker_transport.js`

Current responsibilities relevant to Superchat:

- find a concrete conversation tab;
- inject/probe content scripts;
- validate sender conversation identity;
- receive exhaustion reports;
- set `conversation_exhausted`, disable the old conversation and clear its alarm.

Planned change:

- keep exhaustion detection/reporting as the terminal signal;
- route an accepted terminal event into goal/rollover state when the conversation belongs to an active goal;
- add separate helpers for new-chat tab reconciliation if that remains transport-owned;
- never make `conversationForSender()` accept an unbound arbitrary page.

### `chat_bridge/dom_contract.js`

Current responsibilities:

- detect the observed maximum-length assistant error;
- require the stable structural/textual signals;
- return the exact `Start new chat` button and assistant identity.

Planned change:

- keep it small and platform-DOM-specific;
- add sanitized fixture-based regression tests;
- add new-chat composer/navigation contracts here only if evidence shows they are stable enough.

### `chat_bridge/exhaustion_guard.js`

Current responsibilities:

- MutationObserver + periodic scan;
- deduplicated exhaustion reporting;
- capability probe for injection/versioning.

Planned change:

- no supervisor intelligence here;
- continue producing one deterministic terminal event;
- optionally include bounded evidence needed by rollover, but never repository identity inferred from DOM.

### `chat_bridge/content.js`

Current important property:

Normal `deliverFeedback()` requires the current page URL to equal an already-known concrete conversation URL before it writes or submits anything.

Planned change:

- do not weaken that invariant;
- create a separate content entry point/module for new-chat bootstrap;
- share composer primitives only where safe.

## New modules

Names are provisional but ownership should remain explicit.

### `chat_bridge/supervisor_protocol.js`

Owns:

- strict parsing/serialization for `[LAS:*]` controls;
- action allowlist;
- bounded identifiers and payload fields;
- deterministic control fingerprint/idempotency-key helpers.

Must not own state mutation.

### `chat_bridge/supervisor_state.js`

Optional if `bridge_state.js` would otherwise become too large.

Owns:

- goal sanitization;
- operation sanitization;
- checkpoint sanitization;
- lifecycle transition validation.

If introduced, `bridge_state.js` remains the top-level schema/migration owner.

### `chat_bridge/worker_supervisor.js`

Owns:

- accepting validated Superchat lifecycle requests;
- starting/pausing/waking/stopping goals;
- requesting checkpoints;
- beginning/reconciling rollover operations;
- fleet snapshot construction;
- circuit-breaker transitions.

It must not parse ChatGPT DOM and must not execute project work.

### `chat_bridge/new_chat.js`

Content-side primitive for a new/unbound ChatGPT page.

Expected responsibilities:

- verify current page is an allowed ChatGPT new-chat surface;
- verify assistant is not generating and composer is clean;
- set one exact bootstrap prompt;
- submit once;
- wait for navigation to a concrete normalized `/c/<id>` URL;
- return that concrete URL and bounded evidence;
- reject ambiguous/repeated submission.

Normal `content.js` remains the concrete-conversation delivery path.

### `chat_bridge/worker_rollover.js`

May be separate from `worker_supervisor.js` if transaction logic becomes large.

Owns:

- operation journal transitions;
- spawn/reconcile candidate tab;
- bootstrap confirmation;
- concrete URL observation;
- replacement registration;
- goal activation;
- old-worker retirement;
- restart recovery.

## Schema v4 details

Implement migration before lifecycle behavior.

Suggested top-level keys:

```text
schemaVersion
settings
conversations
supervisor
goals
operations
```

Required bounds:

- maximum goal id length;
- maximum retained chat history per goal or explicit compaction policy;
- checkpoint string/array bounds;
- maximum operations retained;
- maximum error text length;
- canonical timestamps;
- canonical catalog repository ids and UUID bindings.

Migration rule:

Existing v3 conversations must remain behaviorally identical after migration. No old conversation should become a goal automatically unless there is an explicit, deterministic migration rule. Initial release can leave `goals={}` and require explicit goal creation.

## Checkpoint implementation

A checkpoint should be structured and bounded.

Suggested fields:

```text
revision
objective
completed[]
remaining[]
last_task_id
last_commit
verified_evidence[]
blockers[]
next_action
updated_at
source_chat_id
source_generation
```

Security/lifecycle rules:

- only the active worker generation may update its goal checkpoint;
- revision is monotonic;
- stale generation writes are rejected;
- exact evidence identifiers are separate from prose;
- checkpoint update does not mean the referenced task/commit succeeded;
- final replacement planner must re-check exact current evidence.

Do not make terminal rollover depend on asking an exhausted conversation for one more message.

## New-chat creation transaction

Recommended service-worker sequence:

1. validate requested goal and target generation;
2. persist operation `REQUESTED`;
3. persist snapshot/checkpoint revision and move to `SNAPSHOTTED`;
4. find/reconcile an existing candidate tab for this operation id;
5. if none exists, create one ChatGPT tab and persist `candidate_tab_id`;
6. inject/probe the dedicated new-chat content path;
7. authorize one bootstrap against the exact operation id/generation;
8. submit continuation bootstrap;
9. observe concrete normalized conversation URL;
10. persist candidate URL/chat id;
11. register the conversation using the already-selected catalog binding;
12. atomically update goal active generation/chat;
13. retire old worker when applicable;
14. mark operation `COMPLETED`.

At every step, re-read durable state before performing the next external effect.

## Hard exhaustion path

Current behavior immediately disables an exhausted conversation. Keep that safe behavior.

When an exhausted conversation belongs to an active goal:

```text
conversation_exhausted
  -> mark old chat terminal/disabled
  -> ensure one rollover operation exists for goal generation
  -> use latest durable checkpoint
  -> create replacement
  -> activate replacement
```

There is no requirement to reactivate the exhausted chat.

## Proactive rotation path

Later optimization:

```text
rotation requested
  -> request fresh checkpoint
  -> keep old worker authoritative
  -> create/register replacement
  -> atomically switch active generation
  -> disable/retire old worker
```

This path has stronger handoff quality because the old conversation can still answer.

## Service-worker restart reconciliation

Add a startup pass before issuing new supervisor effects.

For every non-terminal operation:

- inspect whether `candidate_tab_id` still exists;
- inspect its current URL;
- if it already has the expected concrete URL, continue registration;
- if the candidate is a clean new-chat page and bootstrap was not authorized/submitted, resume;
- if submission may have happened but outcome is ambiguous, do not submit a second time blindly;
- attempt to reconcile by tab/url/message evidence;
- if still ambiguous, set operation `FAILED` and goal `NEEDS_SUPERVISOR`.

## Protocol design

Keep two namespaces:

- `[LAB:*]` — existing same-chat controls;
- `[LAS:*]` — future privileged supervisor lifecycle controls.

Do not extend `[LAB:*]` to cross-chat actions.

Initial `[LAS:*]` implementation should carry references to existing deterministic state, not arbitrary repository strings. For example a `goal_id` may reference a goal whose repository/binding was already created from the runtime catalog.

## Fleet snapshot

The supervisor should receive bounded summaries, not complete child transcripts.

Suggested per-goal projection:

```json
{
  "goal_id": "...",
  "repository_id": "...",
  "status": "running",
  "generation": 3,
  "active_chat_id": "...",
  "chat_status": "sent",
  "checkpoint_revision": 42,
  "checkpoint_age_seconds": 120,
  "last_task_id": "...",
  "last_commit": "...",
  "blockers": [],
  "operation": null
}
```

## Tests to add

### State

- v3 -> v4 migration;
- malformed supervisor/goal/operation data;
- goal lifecycle transition validation;
- operation idempotency;
- stale generation checkpoint rejection;
- bounded history/strings.

### DOM and content

- sanitized real exhaustion fixture positive case;
- near-match negative cases;
- multiple buttons/ambiguous DOM fail-closed cases;
- new-chat composer ready/not-ready cases;
- navigation to `/c/<id>` success;
- no double-submit after uncertain delivery.

### Service worker

- one rollover operation per goal generation;
- hard exhaustion creates/resumes rollover;
- repeated terminal event is idempotent;
- crash/restart after every operation state;
- replacement registered before goal activation;
- child cannot mutate another goal/chat;
- stale supervisor binding/revision rejected;
- catalog mismatch rejected;
- circuit breaker after bounded failures.

### Real browser smoke

Extend Chromium smoke with a controlled test page or fixture harness for:

- exhaustion detection;
- create/bootstrap/navigation transaction;
- restart/reconciliation where feasible.

## Verification sequence

Use the repository verification policy:

1. focused Chat Bridge JS tests while implementing each phase;
2. fixture/Chromium smoke for DOM-dependent changes;
3. `python scripts/verify.py --only bridge` when available/appropriate;
4. exact-candidate full `python scripts/verify.py` before release;
5. downstream documentation audit if planner-facing behavior changes.

## Proposed first implementation slice

Do not start with the full Superchat LLM protocol.

The safest first code PR after the design PR is:

1. add schema v4 with empty `supervisor/goals/operations`;
2. add bounded goal + operation models and tests;
3. add sanitized exhaustion fixture test;
4. add a deterministic internal `beginRollover(goal_id, reason)` state transition with no browser creation yet.

That creates the durable foundation and allows later browser automation to be tested against a stable transaction model.
