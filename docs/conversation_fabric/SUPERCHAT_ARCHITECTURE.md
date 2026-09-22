# Superchat / Conversation Fabric architecture

Status: design baseline on `feature/conversation-fabric-superchat`. No production runtime behavior is changed by this document.

Production base: `main@474000b5d4b015958fe92be491968dc4625b4a84` (`v4.18.24`).

## 1. Product goal

The missing product layer is a **Superchat** that can decompose one development goal into several deep, isolated ChatGPT work contexts, run independent parts in parallel, collect durable evidence, integrate the results, and retire child chats when their responsibility is complete.

The target experience is:

```text
user
  |
  v
Superchat
  |
  +--> architecture/research child
  +--> implementation child A ----+
  +--> implementation child B ----+--> integration/review child
  +--> verification child --------+
  |
  v
final integrated result
```

The objective is not merely more parallelism. The objective is **higher reasoning quality through smaller contexts and explicit module ownership**.

A child chat should spend most of its context and reasoning budget on one bounded problem instead of carrying every unrelated design decision, test log, repository subsystem and historical conversation turn.

## 2. One architecture, five layers

The target system has five distinct layers.

### Conversation Fabric

Owns ChatGPT conversation topology:

- one Superchat per active workflow;
- bounded child chats with explicit roles;
- parent/child ownership;
- chat lifecycle and routing;
- child bootstrap and terminal handoff;
- no hidden child-to-child communication.

### Execution Fabric

Owns durable work topology:

- workflow DAG;
- node dependencies;
- methods;
- planner checkpoints;
- user gates;
- append-only workflow revisions;
- exact repository child tasks;
- evidence reconciliation.

### Attention Fabric

Owns low-latency wake hints:

- task terminal-result events;
- later workflow/checkpoint attention events;
- durable outbox/replay;
- bounded dedupe;
- restart-safe notification delivery.

An attention event is never authoritative evidence. It means only that new durable evidence is available.

### Chat Bridge

Owns browser actuation:

- exact conversation/tab activation;
- creation of a new ChatGPT conversation from a durable child request;
- bootstrap prompt injection;
- current-page delivery/recovery;
- exact parent/child browser mapping;
- logical child retirement and optional tab close;
- no repository planning and no shell authority.

### Local Agent

Remains the deterministic execution substrate:

- existing immutable task contract;
- repository binding;
- claims/results;
- watchdogs/resource leases;
- exact cancellation;
- self-update/rollback;
- workflow coordination using existing repository workers.

ChatGPT remains the planner. Local Agent remains model-free.

## 3. GitHub is the durable coordination spine

ChatGPT tabs and browser state are ephemeral. GitHub-backed evidence is durable.

The core rule is:

> Conversations reason. GitHub-backed state remembers.

No workflow correctness may depend on retaining a browser tab, a full chat transcript, a Chrome service-worker instance, or one in-memory parent context.

The control/evidence model is split deliberately.

### Project-owned evidence

A child chat working on repository `R` may write only to `R`'s permitted project/control surfaces. It must not gain permission to inspect or mutate unrelated project control planes merely because it belongs to a multi-repository workflow.

Child progress/checkpoint evidence should therefore be repository-scoped and exact, for example conceptually:

```text
<project control branch>/.agent/workflows/<workflow-id>/nodes/<node-id>/
    progress/<sequence>.json
    terminal.json
```

The exact path/schema is a contract decision, not fixed by this document.

### Central orchestration evidence

Execution Fabric owns a central workflow view containing:

- immutable workflow/revision identity;
- node definitions and dependencies;
- child conversation requests and registrations;
- current effective state;
- references to exact repository-owned task/progress/result evidence;
- planner/user decisions;
- integration readiness.

A dedicated orchestration control branch/repository is preferred over mixing these records into production source `main` or operator-control state.

The workflow contract must not depend on one specific Git transport so the control branch can be changed later without changing workflow meaning.

## 4. Superchat authority

The Superchat is a planner, dispatcher and reviewer. It is not a generic cross-repository shell.

It may:

- inspect workflow-level evidence;
- define or revise a workflow graph;
- create bounded child-chat requests;
- decide which independent nodes may run in parallel;
- inspect child checkpoints and terminal summaries;
- resolve planner checkpoints;
- create integration/review nodes;
- ask for explicit user decisions at durable gates;
- finalize the integrated workflow.

It may not:

- silently convert an ordinary project chat into a cross-repository chat;
- bypass repository bindings;
- directly grant a child broader scope than its node contract;
- treat child prose as authoritative execution evidence;
- merge results simply because every child says "done".

The final integration step must inspect exact commits/results/tests and reconcile shared contracts.

## 5. Child chat roles

Version 1 supports one parent level and a small role set.

### `research`

Purpose:

- architecture audit;
- code-path tracing;
- API/contract analysis;
- risk analysis;
- no implementation unless explicitly promoted by a new node/revision.

### `implementation`

Purpose:

- one bounded module/component;
- exact repository;
- exact work branch/worktree;
- focused implementation plus focused verification;
- no merge to the workflow integration branch.

### `verification`

Purpose:

- inspect a candidate implementation independently;
- run/check focused or full verification;
- audit diff/contract behavior;
- avoid silently repairing implementation unless a new implementation node is created.

### `integration`

Purpose:

- consume exact outputs of predecessor nodes;
- reconcile overlapping files/interfaces;
- combine branches/commits into one integration branch;
- run integration/full verification;
- report conflicts or architecture drift back to Superchat.

Version 1 does not allow child chats to recursively spawn their own child chats. One central planner keeps the topology understandable and auditable.

## 6. Child node contract

Every child is created from an immutable, digest-pinned node specification. A conceptual shape is:

```json
{
  "schema_version": 1,
  "workflow_id": "litegraph-refactor-017",
  "workflow_revision": 3,
  "node_id": "mqtt-api",
  "role": "implementation",
  "parent_chat_id": "...",
  "repository_id": "litegraph",
  "repository": "MichalMatu/esp32s3_LiteGraph",
  "agent_binding": "...",
  "work_branch": "wf/litegraph-refactor-017/mqtt-api",
  "depends_on": ["mqtt-audit"],
  "goal": "Refactor only the MQTT catalog API boundary.",
  "allowed_scope": ["src/mqtt/**", "tests/mqtt/**"],
  "forbidden_scope": ["frontend/**", "storage/**"],
  "required_outputs": [
    "implementation_commit",
    "focused_verification",
    "findings",
    "integration_notes"
  ]
}
```

The schema must be bounded. Large free-form context should be referenced by exact durable artifacts/commits rather than copied repeatedly into every child bootstrap.

## 7. Bootstrap prompt

The browser bootstrap is generated from the durable child spec, not improvised from parent-chat prose after the tab opens.

It must include:

- workflow id/revision;
- node id and role;
- parent identity;
- exact repository/binding;
- exact work branch;
- bounded goal;
- dependencies/inputs;
- allowed and forbidden scope;
- required outputs/checkpoints;
- instruction to read repository `AGENTS.md` / relevant handoff docs;
- instruction to publish structured progress at meaningful stage boundaries;
- instruction not to merge/finalize outside the node contract.

The child may reason freely inside this boundary. It may not silently broaden it.

## 8. Progress is structured evidence, not transcript synchronization

The parent should not need the full child transcript.

At meaningful stage boundaries the child publishes a bounded progress record, conceptually:

```json
{
  "schema_version": 1,
  "workflow_id": "litegraph-refactor-017",
  "workflow_revision": 3,
  "node_id": "mqtt-api",
  "sequence": 4,
  "stage": "implementation_complete",
  "status": "waiting_verification",
  "source_revision": "abc123...",
  "summary": "Refactored MQTT catalog API behind one adapter.",
  "findings": ["Legacy caller X still assumes old enum values."],
  "contract_changes": [],
  "verification": {
    "focused": "pending"
  },
  "next_action": "Run focused MQTT host tests."
}
```

Properties:

- append-only sequence per node;
- deterministic workflow/node identity;
- bounded text/array sizes;
- exact commit/result references where applicable;
- no raw chat transcript;
- no secrets/log dumps;
- progress cannot rewrite earlier records.

Superchat reads the newest valid checkpoint plus exact referenced evidence when it needs to make a decision.

## 9. Same-repository parallelism requires branch/worktree isolation

Two implementation children must never concurrently edit the same checkout/branch.

For parallel nodes in one repository:

```text
workflow
  +-- node A -> branch wf/<workflow>/A -> isolated worktree
  +-- node B -> branch wf/<workflow>/B -> isolated worktree
  +-- node C -> branch wf/<workflow>/C -> isolated worktree
```

The integration node owns the deliberate combination step.

The system must detect overlapping intended file/contract scope before dispatch where possible, but overlap is not automatically forbidden: sometimes two branches legitimately change a shared interface. In that case the graph must make the integration/reconciliation responsibility explicit.

## 10. Browser child creation protocol

Creating a ChatGPT conversation is the most UI-sensitive part of the design, so desired state must exist before UI actuation.

Recommended sequence:

```text
Superchat creates durable child request
        |
        v
request receives immutable id + digest
        |
        v
Bridge receives SPAWN_CHILD(request-id, digest)
        |
        v
Bridge validates exact parent conversation + request
        |
        v
open new ChatGPT tab/conversation
        |
        v
wait for composer readiness
        |
        v
inject deterministic bootstrap
        |
        v
confirm accepted user message / conversation identity
        |
        v
persist browser mapping
        |
        v
register child conversation against the pre-existing request
```

Bridge must never create an unbound generic child and decide later what it belongs to.

### Registration durability

A browser mapping should include at least:

- workflow id/revision;
- node id;
- child-request id/digest;
- parent conversation id;
- child conversation id and exact URL;
- repository/binding identity;
- lifecycle generation;
- created timestamp.

Chrome storage is useful for immediate recovery but is not sufficient as the sole workflow record.

A future bounded Native Messaging conversation-registration protocol may let Bridge register the mapping through Local Agent into the orchestration control plane. Such a protocol may only acknowledge/register a pre-existing exact child request. It must not grant the browser generic Git write, task creation, shell or rebind authority.

## 11. Child lifecycle

Canonical v1 lifecycle:

```text
requested
  -> creating
  -> bootstrapping
  -> active
  -> waiting_dependency | waiting_evidence | active
  -> terminal_ready
  -> terminal_recorded
  -> retired
```

Failure substates must distinguish at least:

- browser creation failed before a child identity existed;
- bootstrap delivery uncertain;
- child conversation exists but registration is incomplete;
- child work failed;
- child completed but terminal evidence is not durable;
- browser tab disappeared after durable registration.

Idempotency is required. Replaying a child request must discover/reuse the exact registered child or fail closed; it must not silently create duplicate active children.

## 12. Logical retirement before physical tab close

A finished child must first become logically inert:

```text
node terminal evidence durable
-> child accepts no further workflow wake
-> lifecycle generation closed
-> parent/integration ownership advances
```

Only then may Bridge optionally close the browser tab.

Correctness must not depend on ChatGPT conversation archive/delete UI.

The conversation may remain in ChatGPT history as audit/debug context, but it is no longer an active workflow participant.

## 13. Integration is a first-class node

Parallel children are not merged merely because they all succeeded locally.

An integration node receives exact predecessor evidence:

```text
node A -> commit/digest/tests
node B -> commit/digest/tests
node C -> commit/digest/tests
```

It must inspect:

- merge/rebase conflicts;
- shared APIs/contracts;
- duplicate or contradictory abstractions;
- cross-module error handling;
- tests that passed only in isolation;
- architecture drift from the parent decision;
- final diff size/ownership.

The integration node produces its own exact commit and verification evidence. A later independent verification node may review that integrated candidate before Superchat declares completion.

## 14. Attention routing

The same notification substrate should eventually carry two families of bounded events.

### Project task attention

Example:

```text
task_result_ready(repository, binding, task_id)
```

Routes to the exact project child conversation that owns the watch.

### Workflow attention

Examples:

```text
workflow_waiting_planner(workflow_id, revision, node_id)
workflow_waiting_user(...)
workflow_failed(...)
workflow_completed(...)
child_terminal_recorded(workflow_id, node_id)
```

Routes to the exact Superchat/workflow owner.

Neither event family contains authoritative result bodies. They identify durable evidence that must then be read.

## 15. Failure and restart model

### Chrome or Chat Bridge restart

- durable workflow/child requests remain in GitHub-backed state;
- browser mappings are restored from bounded extension state and reconciled against durable registrations;
- pending child creation or wake operations are idempotently resumed/reclassified;
- no new child is created solely because the service worker forgot an in-memory flag.

### Local Agent restart

- existing project tasks remain governed by current no-replay rules;
- Execution Fabric reconstructs from workflow state plus exact project evidence;
- child conversation identity is not execution authority;
- missed attention events replay from durable outbox/reconciliation.

### ChatGPT child tab closed manually

- durable child/node state survives;
- if work is terminal, nothing is reopened;
- if active and policy permits recovery, Bridge may require explicit Superchat/operator decision before recreating a UI context;
- do not silently create a replacement reasoning context that could duplicate work.

## 16. Security/authority rules

1. A child cannot alter its own workflow id, parent, repository binding or node role.
2. A child cannot create a sibling in v1.
3. A browser/native registration message can only satisfy a pre-existing exact child request.
4. Project children keep exact repository hard binding.
5. Cross-repository orchestration authority exists only at the infrastructure workflow layer.
6. Native Messaging does not expose generic shell/filesystem/Git commands.
7. Progress/evidence is bounded and schema-validated.
8. Integration uses exact commits/digests/results, not child self-assertion.
9. Global Local Agent disable remains authoritative over execution.
10. Interrupted claimed project tasks are never automatically replayed.

## 17. Explicit v1 non-goals

Do not mix into the first Conversation Fabric implementation:

- recursive child-of-child delegation;
- arbitrary numbers of child chats without workflow bounds;
- streaming whole transcripts between chats;
- hidden model-to-model messaging outside durable evidence;
- automatic merging without integration/review;
- generic desktop/browser automation beyond exact ChatGPT conversation lifecycle;
- arbitrary browser-to-Local-Agent commands;
- automatic cross-repository authority for ordinary project chats;
- distributed remote runners;
- automatic deletion of ChatGPT history.

## 18. V1 success criteria

A successful first end-to-end demonstration is:

1. one Superchat creates a workflow with two independent implementation nodes and one integration node;
2. two exact child requests are durably recorded before browser actuation;
3. Bridge opens two new ChatGPT conversations and injects different bounded bootstrap prompts;
4. each child is hard-bound to its exact repository/branch/node;
5. each child publishes at least one structured progress checkpoint and one terminal record;
6. both may run concurrently without sharing a checkout/branch;
7. Superchat wakes only on meaningful child/workflow transitions, not polling spam;
8. integration child receives exact predecessor commits/evidence and produces one integrated candidate;
9. independent verification checks the integrated result;
10. completed children become logically retired and can have their tabs closed without losing workflow state;
11. Chrome or Local Agent restart during a controlled test does not create duplicate child work or lose durable workflow evidence.

That demonstration proves the product direction: a durable team of specialized ChatGPT contexts coordinated by one Superchat, with GitHub-backed evidence and Local Agent as the deterministic execution substrate.