# Superchat / Conversation Fabric preimplementation re-audit

Status: architecture/reality audit only. No production runtime behavior is changed by this document.

Branch: `feature/conversation-fabric-superchat`
Production baseline: `main@474000b5d4b015958fe92be491968dc4625b4a84` (`v4.18.24`).

This audit compares the proposed Superchat/Conversation Fabric design against the current Local Agent and Chat Bridge code, the two donor branches, and the concrete browser/executor boundaries that exist today. It exists specifically to remove attractive but false assumptions before implementation begins.

## 1. Executive result

The overall product direction is viable, but the original plan contained several assumptions that are not true in the current implementation.

The most important corrections are:

1. **Current Local Agent cannot execute two tasks concurrently in the same registered repository.** Repository exclusion is a hard production invariant, independent of `work_branch`. Same-repository child chats may reason in parallel and may work on separate GitHub branches, but true concurrent Local Agent execution inside one repository requires a separate, high-risk scheduler/workspace redesign and is not part of the first Conversation Fabric slice.
2. **Current Chat Bridge delivery cannot create/bootstrap a brand-new ChatGPT conversation.** Its identity contract only accepts concrete `/c/<conversation-id>` URLs. New-chat creation therefore needs a separate pre-registration spawn transaction keyed by child request/digest and tab identity until the first accepted prompt creates a durable conversation URL.
3. **The donor Native Messaging host is notification-only.** It accepts handshake and ACK inbound; it cannot currently durably register a newly-created child conversation. Conversation registration must use a new narrowly-scoped authority boundary rather than pretending the current event host already supports it.
4. **Current Bridge `chat-xxxxxxxx` ids are convenience hashes, not durable security identities.** Durable child ownership must use immutable child-request identity/digest plus the exact canonical ChatGPT conversation URL/id once known.
5. **Execution Fabric's durable workflow store is local filesystem state, not GitHub.** GitHub can still be the planner-visible coordination spine, but the design must explicitly assign one authority per record type instead of claiming that all workflow truth is already GitHub-backed.
6. **Current runtime catalog has no `orchestration_enabled` capability.** Adding an infrastructure Superchat is a real runtime schema/protocol migration, not just a configuration entry.
7. **Current command-progress machinery is executor progress, not child-chat reasoning progress.** Conversation checkpoints need a separate bounded planner-evidence contract.
8. **Prompt-level hard binding does not technically restrict the account-wide GitHub connector.** Local Agent execution remains hard-bound, but a ChatGPT conversation with broad GitHub write capability is not a capability sandbox. The design must not claim otherwise.
9. **Browser child creation is inherently UI-sensitive.** A manual attach/recovery path is required from the beginning so one ChatGPT DOM change does not make an otherwise healthy workflow unrecoverable.
10. **The claim that modular chats improve code quality is a product hypothesis.** The first live slice must measure integration/rework/defect outcomes, not merely prove that several tabs can run.

None of these findings invalidate the Superchat idea. They narrow the first implementation into something testable and keep risky executor changes out of the browser-orchestration work.

---

## 2. Current production facts that constrain the design

### 2.1 Repository execution is the concurrency boundary today

Production Local Agent uses repository execution leases. One configured repository has one active repository worker/task at a time. Different repositories may overlap, but two tasks for the same repository cannot currently execute concurrently even when their `work_branch` values differ and `resources: []`.

`work_branch` selects source branch/workspace behavior for a task; it does **not** create a new scheduler identity.

Consequences:

- two implementation child chats for one repository may exist simultaneously;
- they may perform analysis simultaneously;
- they may prepare independent GitHub branches simultaneously if the ChatGPT/GitHub path supports it;
- Local Agent tasks for those children will still serialize per repository;
- true same-repository local build/test/flash concurrency requires a future "workspace lane" design that changes repository lease/status/claim assumptions.

Do not smuggle that scheduler redesign into Conversation Fabric v1.

### 2.2 Current Bridge state begins only after a concrete conversation URL exists

`control_protocol.js::normalizeConversationUrl()` accepts concrete ChatGPT conversation URLs ending in `/c/<id>`. `bridge_state.js` stores configured conversations keyed from that normalized URL. `worker_delivery.js` locates an existing matching tab and refuses delivery if the expected URL does not match the page.

That is correct for wake delivery but incompatible with child creation, because a fresh ChatGPT page may not have a `/c/<id>` identity until after the first prompt is accepted.

Therefore `SPAWN_CHILD` cannot be implemented by calling the existing `deliverConversation()` with a fake/unbound URL.

A new pre-registration spawn state is required.

### 2.3 Current content delivery is strong for existing conversations and should remain untouched

The v4.18.24 path has useful invariants that must be reused after child registration:

- exact expected conversation URL;
- preferred-tab validation;
- `generation` and `bindingRevision` checks;
- delivery authorization immediately before submission;
- exact composer preservation;
- assistant-busy and assistant-timeout handling;
- confirmation that the expected user message appeared.

The spawn path should be a small separate lifecycle that converges into this existing path after the child receives a concrete URL and normal hard binding.

### 2.4 Current Bridge persistent state should not be overloaded with workflow truth

`bridgeState` schema v3 owns settings and ordinary configured conversation records. It is already migration-sensitive and production critical.

Conversation Fabric should initially use a separate persisted namespace, for example conceptually:

```text
chrome.storage.local.bridgeState              # existing production state
chrome.storage.local.conversationFabricState  # new lab state
```

The new state may cache:

- spawn transaction id;
- child request id/digest;
- parent exact URL;
- provisional tab id;
- discovered child exact URL;
- registration generation;
- lifecycle state.

It must not become the durable workflow authority.

### 2.5 Tab id is not child identity

Chrome tab ids are useful only as ephemeral routing hints. They may disappear after tab closure/browser restart and cannot be the durable child identity.

Durable identity order should be:

```text
child_request_id + child_request_digest
    -> registered exact ChatGPT conversation URL/id
    -> optional current tab id cache
```

The existing `chat-<fnv32>` id can remain a UI/internal lookup key but must not be used as a security or workflow uniqueness key.

---

## 3. Browser child creation: feasible, but it is a different protocol

### 3.1 Preferred actuation

Do not automate clicking ChatGPT's visible "New chat" navigation button. The extension can create a tab directly on the ChatGPT origin and wait for the composer. This removes one unnecessary DOM dependency.

Conceptual first flow:

```text
exact durable child request exists
-> persist spawn transaction before opening UI
-> create ChatGPT tab
-> wait for generic new-chat composer readiness
-> insert deterministic bootstrap containing request marker/digest
-> submit once
-> observe accepted first user turn
-> allow the page to transition from unregistered new-chat URL to one concrete /c/<id>
-> capture exact canonical child URL
-> persist provisional mapping
-> durably register mapping
-> only then convert child to ordinary bound Bridge conversation
```

### 3.2 Spawn delivery cannot require an already-known conversation URL

The existing content path rejects wrong/missing exact conversation URL. The spawn path therefore needs a separate authorization object, e.g. conceptually:

```text
spawn_id
request_id
request_digest
parent_exact_url
expected_chatgpt_origin
tab_id
spawn_generation
```

The content side may accept bootstrap delivery only when the service worker proves the tab owns that exact active spawn transaction.

### 3.3 Bootstrap must contain a machine-readable request marker

The first user message should include a bounded marker that survives whitespace normalization, for example conceptually:

```text
[LA_CHILD_REQUEST=<id>]
[LA_CHILD_DIGEST=<digest>]
```

The marker lets restart recovery distinguish:

- untouched empty new-chat tab;
- exact bootstrap already accepted;
- unrelated user content;
- wrong child request.

It is not authority by itself; authority remains the pre-existing spawn transaction/request.

### 3.4 Uncertain first-send handling is the highest-risk browser race

If the extension times out while ChatGPT actually accepted the bootstrap and created `/c/<id>`, blindly retrying by creating a second tab would duplicate the child.

Required fail-closed recovery order:

1. inspect the original spawn tab if it still exists;
2. inspect its current URL;
3. inspect the latest user message for the exact child marker/digest;
4. if it has transitioned to one `/c/<id>` with the exact marker, recover that child;
5. if it is still empty, retry the same tab transaction;
6. if state is ambiguous, stop and require manual attach/recovery;
7. never open a replacement tab merely because one response timed out.

### 3.5 Manual attach is a product requirement, not a debug convenience

The browser UI is not a stable execution API. v1 therefore needs an explicit recovery path:

```text
operator opens a fresh ChatGPT conversation
-> Bridge/popup selects an existing pending child request
-> exact request/digest is attached to the current empty/unbound conversation
-> deterministic bootstrap is submitted
-> normal registration continues
```

This keeps workflow state recoverable when automatic tab creation or a DOM selector breaks.

### 3.6 Creation can be serialized even when child work is parallel

There is little value in creating multiple child tabs at the exact same millisecond. For v1, serialize browser spawn transactions while allowing registered child conversations to work concurrently afterward.

This reduces ambiguity around route discovery, service-worker restart and tab ownership without sacrificing meaningful development parallelism.

---

## 4. Native Messaging and durable child registration

### 4.1 Donor host capability today

The event-wake donor host is deliberately notification-only. Inbound messages are limited to protocol handshake and ACK for already-emitted result events. That security property was a major part of the donor audit.

Therefore the old host cannot simply be described as the child-registration channel.

### 4.2 Recommended authority split

Preserve the event host as notification-only.

Introduce a separate, narrowly-scoped conversation-registration host/protocol only when Phase 4 proves browser creation is worth keeping.

Allowed operations should be tiny and typed, for example:

```text
hello
register_child(request_id, digest, parent_url, child_url, generation)
retire_child(request_id, digest, child_url, generation)
query_registration(request_id, digest)
```

Hard restrictions:

- the exact child request must already exist locally from authoritative orchestration input;
- request digest must match;
- repository/binding/role/branch are read from that request, never accepted as browser-supplied authority;
- browser cannot create workflow nodes;
- browser cannot create Local Agent tasks;
- browser cannot write arbitrary Git paths;
- browser cannot execute shell;
- browser cannot rebind repositories;
- repeated identical registration is idempotent;
- conflicting child URL for an already-registered request fails closed.

A second host adds installation complexity but preserves a much cleaner authority boundary than turning the event host into a general request channel.

### 4.3 Registration record authority

Chrome storage is cache. Durable registration should eventually be an orchestration record owned by Local Agent/Conversation Fabric and published into the planner-visible orchestration control plane.

A registration record is not allowed to modify the immutable child request. It only resolves:

```text
request digest -> exact ChatGPT conversation identity
```

---

## 5. GitHub as coordination spine: corrected authority model

The statement "GitHub is the durable spine" remains useful, but not every runtime byte should be considered GitHub-authoritative.

The donor Execution Fabric stores workflow manifests/state/events under Local Agent application state. Its revision store is local append-only state. Its Git-backed control plane currently publishes/inspects project child tasks, not the central workflow database.

To avoid two competing truths, v1 should assign authority by record type.

### 5.1 Planner-authored immutable inputs

Canonical in a dedicated orchestration Git control plane:

- workflow request/base manifest;
- append-only workflow revisions;
- child conversation requests;
- planner checkpoint continuations;
- explicit user decisions where remote submission is required.

Local Agent ingests and validates these into its local durable store/cache.

### 5.2 Derived workflow runtime state

Canonical meaning is derived by Local Agent from:

- immutable orchestration inputs;
- local admitted workflow lineage;
- exact project task/result/checkpoint evidence.

Local state is the restart-efficient materialization. A GitHub status projection may be published for Superchat visibility, but must be labeled derived/non-authoritative rather than independently mutable truth.

### 5.3 Project execution evidence

Remains authoritative in each project's existing Local Agent control plane:

- task payload/digest;
- claims/runs/status;
- terminal result;
- cancellation evidence.

Do not copy raw task logs into central workflow state.

### 5.4 Conversation registration

Canonical registration should be published centrally after bounded local validation. Chrome state is only a routing cache.

This split gives every record one owner and prevents GitHub/local-store conflict resolution from becoming an undefined protocol.

---

## 6. Execution Fabric donor: what is reusable and what is not

### 6.1 Strong reusable assets

The donor already provides valuable pure/durable semantics:

- bounded workflow schema;
- DAG validation;
- deterministic digests;
- explicit node states;
- planner/user waiting states;
- append-only revisions;
- local fsync/lock discipline;
- exact child task identity/digest reconciliation;
- Git publication conflict/ambiguity handling;
- cancellation paths;
- tests using temporary Git repositories.

These should be transplanted, not rewritten casually.

### 6.2 Donor assumptions that conflict with Superchat v1

The donor coordinator intentionally permits at most one coordinator-owned active/pending child per repository and yields when unrelated work exists. The current Local Agent itself also serializes a repository.

Therefore the donor cannot power the originally proposed "two same-repository Local Agent implementation nodes run in parallel" prototype without a separate execution redesign.

### 6.3 Same-repository workspace lanes are a separate future project

If measured value justifies true same-repository Local Agent concurrency, design it separately with explicit review of:

- repository execution lease keying;
- repository status schema that currently represents one task;
- claims/results/control branch concurrency;
- work/checkpoint directory identity;
- branch/worktree ownership;
- cancellation ownership;
- descendant/resource leases;
- cleanup/checkpoint recovery;
- global control probing;
- diagnostics and operator expectations.

Do not weaken the existing repository lease just because different branch names are available.

---

## 7. Child progress: do not reuse command progress as planner progress

`local_agent/runtime/progress.py` parses bounded `[AGENT_PROGRESS]` emitted by executing commands and asynchronously publishes executor progress. It does not represent a ChatGPT child finishing architectural analysis, discovering a contract issue or handing an implementation commit to its parent.

Conversation Fabric needs a different record type, e.g. `planner_checkpoint` / `child_checkpoint`.

Properties:

- create-only/append-only sequence;
- request/workflow/node identity + digest;
- bounded summary/findings;
- exact branch/commit/task/result references;
- no transcript/log dump;
- terminal record separate from non-terminal progress;
- idempotent retries;
- no claim that a model-authored summary proves tests passed without exact referenced evidence.

For the first user-facing prototype, the child can publish these records through the same GitHub connector path already used by ChatGPT to manipulate Git-backed control data, provided deployment preconditions and repository scope are explicit. A later bounded local protocol may remove that dependency if needed.

---

## 8. Superchat authority and GitHub connector limitation

Local Agent can hard-enforce repository binding on Local Agent tasks. Chat Bridge can hard-enforce which configured conversation it wakes. Neither mechanism turns the general ChatGPT GitHub connector into a per-conversation capability sandbox.

If the connected GitHub app/token can write several repositories, a prompt instructing Superchat or a child not to write elsewhere is policy, not kernel-level enforcement.

Therefore:

- never describe ordinary child hard binding as restricting all possible connector writes;
- use exact repository policy and audits for connector operations;
- keep consequential execution behind Local Agent hard binding;
- prefer a dedicated orchestration control repository/branch for Superchat records;
- if stronger tool capability isolation is later required, use narrower GitHub credentials/app scopes rather than pretending prompt text is a sandbox.

This is an existing product limitation, not introduced by Conversation Fabric.

---

## 9. Runtime catalog / orchestration identity migration

Current runtime schema is v3 and each agent has only `execution_enabled`. The `local-agent` infrastructure binding is execution-disabled, but there is no `orchestration_enabled` field or orchestration command family.

Adding Superchat requires a deliberate later schema/protocol change, including:

- runtime config schema bump;
- runtime validator migration;
- backward/fallback behavior;
- Bridge state/control command authorization;
- exact distinction between project chat, infrastructure/operator chat and orchestration chat;
- tests proving a project chat cannot gain orchestration privileges merely by emitting a marker.

Do not add `orchestration_enabled` to JSON before the consuming code has an audited meaning for it.

---

## 10. Child lifecycle corrections

Use two related state machines, not one overloaded state field.

### 10.1 Durable logical child state

Conceptual:

```text
requested
-> registration_pending
-> active
-> terminal_pending_evidence
-> terminal_recorded
-> retired
```

This is workflow meaning.

### 10.2 Ephemeral browser spawn transaction

Conceptual:

```text
pending
-> tab_created
-> bootstrap_submitting
-> identity_discovered
-> registration_submitting
-> done
```

with explicit failure/ambiguous states.

Browser failure must not rewrite logical workflow completion. A retired/terminal child never becomes active again merely because its old tab reappears.

---

## 11. First vertical slice: corrected scope

The previous prototype claimed two same-repository implementation children plus integration with two Local Agent worktrees in parallel. That is incompatible with production repository exclusion.

Use two complementary prototypes instead.

### Slice A — prove Conversation Fabric itself

One repository, two child chats, two separate source branches, one integration child.

Allowed concurrency:

- both child chats may reason concurrently;
- direct GitHub branch edits may occur independently when safe;
- Local Agent execution for that repository remains serialized;
- integration consumes exact commits/evidence.

This proves the central product hypothesis without changing executor isolation.

### Slice B — prove true end-to-end execution parallelism

Use two different registered repositories, one child per repository. Existing Local Agent parallel scheduling can then run both tasks concurrently under current production invariants.

This proves Superchat can coordinate genuinely concurrent executor work without first redesigning repository leases.

Only after both slices provide value should a separate same-repository workspace-lane project be considered.

---

## 12. Quality hypothesis and measurable success criteria

Do not define success as "three tabs were opened".

For a representative modular task, record at least:

- number of unrelated files each child touched;
- integration conflicts;
- interface contradictions discovered at integration;
- focused/full test failures after integration;
- amount of rework required by integration/verification;
- duplicate abstractions introduced by independent children;
- parent context size/recap overhead compared with a single-chat run;
- time spent waiting versus useful parallel work;
- number of manual recovery interventions;
- any duplicate child/task caused by restart/retry.

The architecture is justified if bounded children improve local reasoning depth without creating enough integration/recovery cost to erase the benefit.

---

## 13. Concurrency and service limits

Conversation Fabric must have explicit bounded admission even if ChatGPT itself permits more simultaneous activity.

Initial defaults should be conservative:

- one active spawn transaction at a time;
- at most two concurrently active implementation/research child chats in the first live slice;
- bounded total registered children per workflow;
- workflow backpressure when a required child is generating, ambiguous or awaiting evidence;
- no assumption that account/UI/model service will accept unlimited simultaneous generations.

External throttling should become a visible wait state, not a reason to duplicate work.

---

## 14. Reliability prerequisites retained

Before unattended child orchestration is enabled, keep the earlier reliability work:

- current-turn-only exhaustion detection;
- inactive-tab wake reproduction/repair;
- eliminate known manual `Ctrl+R` dependencies;
- retain v4.18.24 assistant timeout recovery;
- repair orphan Local Agent descendant/resource lease recovery before long-lived autonomous concurrency is relied upon.

These are not prerequisites for writing pure contracts or a synthetic spawn harness, but they are prerequisites for declaring live automation reliable.

---

## 15. Updated implementation ordering

Recommended order after this audit:

```text
0A. freeze corrected authority/identity/lifecycle contracts
0B. browser feasibility spike for new-chat creation + URL discovery + restart recovery
1. pure Conversation Fabric contract/state package
2. production Bridge reliability fixes
3. Attention Fabric task-result events
4. lab child spawn transaction + manual attach fallback
5. durable child registration through a separate bounded native protocol
6. planner child-checkpoint/terminal evidence contract
7. transplant Execution Fabric core and add GitHub orchestration input/projection model
8. Superchat orchestration capability/runtime schema migration
9. two vertical slices: same-repo modular reasoning + multi-repo true execution parallelism
10. integration/verification child roles
11. bounded automatic workflow scheduler
12. optional future same-repository workspace-lane project, only if measured benefit justifies it
```

Governance/self-protection hardening moves before any phase that materially broadens unattended execution authority; it does not need to block pure schemas or a no-execution browser spike.

---

## 16. Go/no-go gates before large implementation

Do not proceed to broad code transplant until all are true:

1. child identity/request/digest authority is documented unambiguously;
2. exact new-chat bootstrap/recovery behavior has a synthetic browser proof;
3. one live new-chat experiment confirms the basic ChatGPT route/composer assumptions or manual attach is accepted as the operational fallback;
4. same-repository Local Agent serialization is explicitly preserved in v1;
5. durable registration authority is chosen (separate bounded native host recommended);
6. GitHub-vs-local authority ownership is frozen per record type;
7. planner progress is separate from executor progress;
8. no design claims connector-level repository sandboxing that does not exist;
9. old donor branches are used selectively rather than merged wholesale;
10. rollback boundaries remain small enough to remove child-spawn capability without removing unrelated Local Agent improvements.

## 17. Final conclusion

Proceed with Conversation Fabric, but start from the corrected contracts and a browser feasibility spike rather than immediately transplanting Execution Fabric or expanding Local Agent scheduling.

The main product architecture remains sound:

```text
Superchat = planner/integrator
Conversation Fabric = bounded reasoning contexts
Execution Fabric = durable work graph
Attention Fabric = low-latency wake hints
Chat Bridge = browser actuator
Local Agent = deterministic executor
GitHub = planner-visible immutable coordination/evidence spine
```

The key correction is that these layers must keep their existing authority boundaries. In particular, Conversation Fabric v1 must not weaken repository execution leases simply to make the demo appear more parallel.