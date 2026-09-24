# Unified development direction — Conversation Fabric

Status: canonical architecture for `develop/conversation-fabric` after branch consolidation and re-audit on 2026-09-23; synchronized with production `main` on 2026-09-24.

Production baseline for this development line is `main@3e3ce9c3e5e8b12b7945a3e07030050b9b1febc6`. Operational state/control branches remain `chat-bridge-state` and `operator-control`; this synchronization does not make Conversation Fabric production-active.

## 1. Verdict

The direction is coherent and technically feasible.

The product should not become another autonomous executor. ChatGPT remains the reasoning/planning layer. Local Agent remains deterministic execution/control infrastructure. Conversation Fabric adds durable parent/child reasoning orchestration and bounded context composition on top of the existing execution model.

The key feasibility result is that most difficult execution primitives already exist:

- exact repository identity and immutable `agent_binding` checks;
- deterministic task identity/digest;
- durable workflow DAG/state/revisions/evidence;
- exact child task publication and cancellation;
- restart reconciliation and fail-closed ambiguity handling;
- per-repository execution leases;
- bounded transient Chat Bridge recovery;
- durable task-result event outbox and notification-only native transport substrate.

The largest unproven dependency is browser child creation/registration. It is intentionally isolated behind a synthetic feasibility gate and a manual-attach fallback.

## 2. Concrete product problem

The motivating workload is a long campaign such as a 44-node code audit.

A single chat doing node 1 through node 44 accumulates all previous reports and tool history even when later nodes need only a small subset of earlier facts. Conversation Fabric should instead operate as:

```text
parent campaign
  -> durable bounded work ledger
  -> child request 01 -> bounded child context -> compact terminal record
  -> child request 02 -> bounded child context -> compact terminal record
  -> ...
  -> child request 44 -> bounded child context -> compact terminal record
  -> parent cross-cutting synthesis
```

The parent must never receive complete child transcripts by default.

## 3. Context-budget contract

The parent owns:

- immutable campaign goal/rubric;
- work DAG and state;
- finding-ID namespace and compact global finding index;
- dependency/relevance metadata;
- exact evidence references;
- final integration/synthesis.

Each child receives only:

- exact request id + canonical digest;
- parent/campaign identity;
- exact repository/ref/binding;
- one bounded scope;
- rubric/role;
- explicitly selected dependencies/cross-cutting facts;
- bounded output schema.

Each child returns a bounded terminal record, conceptually:

```text
status
scope
summary
findings[]
positive_guarantees[]
checks[]
evidence_refs[]
followups[]
context_for_later_children[]
```

Raw logs, full transcripts and large diffs are referenced, not copied.

Promotion of reusable child knowledge is explicit. Nothing enters later child context merely because it appeared earlier in a conversation.

## 4. Bounded concurrency, not tab explosion

Forty-four logical children do not mean forty-four simultaneously active tabs.

Conversation Fabric v1 requires separate limits for:

- queued logical child requests;
- active child conversations;
- browser spawn transactions;
- Local Agent execution.

Browser spawn is serialized initially. Active child reasoning uses a small bounded window. Same-repository Local Agent tasks remain serialized by the existing repository lease. Different registered repositories may run concurrently under the existing supervisor.

This preserves resource bounds and keeps recovery tractable.

## 5. Durable identities and state ownership

Required identities are distinct:

1. `Campaign/Workflow` identity.
2. immutable `ChildRequest` id + canonical digest before any browser action;
3. `ChildRegistration` resolving that exact request to one canonical ChatGPT `/c/<id>` URL;
4. ephemeral Chrome tab id as cache only;
5. deterministic Local Agent child task id/digest where execution is needed.

A tab id or `chat-<fnv32>` hash is never durable authority.

Logical child lifecycle and browser spawn lifecycle must be separate.

Logical lifecycle:

```text
requested
-> registration_pending
-> active
-> terminal_pending_evidence
-> terminal_recorded
-> retired
```

Spawn transaction lifecycle:

```text
pending
-> tab_created
-> bootstrap_submitting
-> identity_discovered
-> registration_submitting
-> done
```

with explicit `failed` and `ambiguous` outcomes.

## 6. Existing Execution Fabric is the correct execution substrate

The transplanted `local_agent/workflow/` core is retained and remains inert from production entrypoints.

Its useful existing properties include:

- bounded workflow size (currently up to 64 nodes, enough for the motivating 44-node campaign);
- exact repository id + `agent_binding` validation;
- coordinator-owned deterministic child task identity;
- one workflow-owned dispatched/running child reserved per repository;
- deferral when unrelated repository work exists;
- remote-evidence reconciliation before publication;
- recovery when publication succeeded but local state transition did not;
- refusal to replay a dispatched/running child whose authoritative evidence disappeared;
- digest mismatch fail-closed behavior.

Conversation Fabric should add reasoning-child identity/evidence around this substrate, not replace its execution semantics.

## 7. Chat Bridge boundary

The latest transient/timeout recovery path is authoritative.

Do not copy old Event Wake worker/content/delivery files over it.

Current safe Event Wake assets on the branch are:

- durable Local Agent result-event outbox;
- notification-only Chrome Native Messaging host;
- pure persisted Event Wake state model + tests.

`chat_bridge/event_wake_state.js` is intentionally not imported by the production service worker yet. This is not a half-enabled feature; it is an inert verified model waiting for explicit integration against current Bridge owners.

Future wake integration must retain:

- scheduled reconciliation as correctness fallback;
- transient/assistant-timeout recovery;
- exact conversation/binding/task ownership;
- event-as-hint semantics: the event is never success evidence.

## 8. Child creation feasibility gate

Existing Bridge delivery requires an already-known concrete conversation URL, so a fresh child cannot use normal delivery immediately.

Implement a separate pre-registration spawn transaction:

```text
persist exact ChildRequest/digest
-> open one ChatGPT new-chat tab
-> submit one deterministic bounded bootstrap
-> verify accepted user marker
-> observe transition to exact /c/<id>
-> persist provisional identity
-> durably register exact request -> child URL
-> converge into normal bound-conversation delivery
```

Highest-risk race: timeout after ChatGPT accepted the first prompt but before the exact URL was persisted.

Recovery must inspect the original tab/URL/marker before any retry. Ambiguous state fails closed to manual attach. It must never create a second child merely because acknowledgement was uncertain.

Manual attach is mandatory from v1.

## 9. Native authority split

Keep the existing event host notification-only.

If automatic child registration survives the browser feasibility spike, use a separate narrowly typed registration protocol. Browser input may carry only identity-resolution data for an already-admitted request. It must not create tasks, choose repositories/branches, rebind authority, run shell commands, or mutate arbitrary Git paths.

Repeated identical registration is idempotent. Conflicting URL/digest/generation fails closed.

## 10. Planner evidence vs executor evidence

Conversation reasoning progress is not `[AGENT_PROGRESS]`.

Add separate bounded append-only records:

- `child_checkpoint` for meaningful planner progress only;
- `child_terminal` for final bounded reasoning output/evidence references.

A model statement such as "tests passed" is not authoritative unless it references exact CI/task/result evidence.

The parent wakes on meaningful durable transitions, not every heartbeat.

## 11. Implementation order

### Phase 1 — pure Conversation Fabric contracts

Implement bounded schemas/digests/state transitions for:

- `ChildRequest`;
- `ChildRegistration`;
- logical child lifecycle;
- spawn transaction state;
- `child_checkpoint`;
- `child_terminal`.

Add strong negative tests: malformed/oversized values, stale generations, duplicate/conflicting registration, cross-parent/binding mismatch, digest stability, invalid transitions.

No Chrome or production runtime effects.

### Phase 2 — synthetic Chromium spawn/attach proof

Prove exactly-once/recoverable child creation in a disposable synthetic ChatGPT fixture, including MV3 restart and uncertain first-send races. Prove manual attach.

No production `SPAWN_CHILD` yet.

### Phase 3 — campaign/workflow integration

Bind registered reasoning children to workflow/campaign nodes while keeping Local Agent execution leases unchanged. Add compact parent ledger/projection and context selection.

### Phase 4 — current Bridge attention routing

Integrate Event Wake behavior into current Bridge owners, not donor files. Route task/child/workflow attention to the exact owning conversation with durable reconciliation fallback.

### Phase 5 — bounded live slice

Run a small same-repository modular campaign first, then the real 44-node audit acceptance campaign. Measure context growth, recovery, integration conflicts, rework and result quality.

### Phase 6 — automatic workflow scheduling only if needed

Only after manual/end-to-end child lifecycle is stable, add a bounded supervisor trigger invoking existing workflow logic. Do not create a second worker pool or model loop.

## 12. Hard invariants

- ChatGPT plans; Local Agent stays model-free.
- `main` and operational branches are untouched until explicit release/migration.
- project chats cannot gain orchestration authority from prompt markers.
- child creation is not execution authority.
- per-repository execution lease remains authoritative in v1.
- interrupted/ambiguous execution is never blindly replayed.
- browser state is cache/recovery state, not workflow truth.
- no whole child transcript is injected into the parent by default.
- all collections/payloads have explicit bounds.
- one record family has one authority; avoid independently mutable duplicate truths.
- Native Messaging authority stays minimal and typed.
- browser ambiguity fails closed to manual recovery.

## 13. Go/no-go criteria

The direction remains GO if:

- pure contracts can be made deterministic and bounded;
- synthetic browser tests can prove duplicate-safe spawn/attach or manual attach is acceptable;
- current Bridge transient recovery stays green during attention integration;
- parent context growth tracks compact ledger size rather than child transcript size.

Stop or redesign automatic spawning if exact child identity cannot be recovered deterministically after uncertain first-send/restart. Conversation Fabric can still proceed with manual attach because the durable workflow/context-isolation model does not depend on automatic tab creation.

## 14. Historical material

Deleted donor branches and old planning PRs are superseded. Their exact snapshots were captured in commit `fdf5d099df39788655f5b41325b8e769fc668981` and remain reachable in branch history. Superseded design documents are under `docs/conversation_fabric/history/`.

Do not restore donor trees into the active working tree. Port only an explicitly audited behavior/test when current owners need it.
