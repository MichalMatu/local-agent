# Superchat / Conversation Fabric architecture

Status: design baseline on `feature/conversation-fabric-superchat`. No production runtime behavior is changed by this document.

Production base: `main@474000b5d4b015958fe92be491968dc4625b4a84` (`v4.18.24`).
Canonical reality audit: `docs/conversation_fabric/PREIMPLEMENTATION_REAUDIT.md`.

## 1. Product goal

The missing product layer is a **Superchat** that can decompose one development goal into several bounded ChatGPT work contexts, let independent reasoning proceed in parallel, collect durable evidence, integrate exact outputs and retire child chats when their responsibility is complete.

Target experience:

```text
user
  |
  v
Superchat
  |
  +--> research / architecture child
  +--> implementation child A -----+
  +--> implementation child B -----+--> integration child --> verification child
  |                                |
  +------------------------------- evidence
  |
  v
final integrated result
```

The objective is not raw tab count. The objective is better reasoning quality from smaller contexts and explicit module ownership without losing whole-system consistency.

The quality benefit is a hypothesis to measure, not a guaranteed property of multiple chats.

## 2. Five layers with strict authority boundaries

### Conversation Fabric

Owns ChatGPT conversation topology:

- one Superchat per workflow;
- bounded one-level child chats;
- child roles;
- child request/registration/lifecycle;
- browser mapping and logical retirement;
- no hidden child-to-child communication.

It does not execute project commands.

### Execution Fabric

Owns durable work topology:

- workflow DAG;
- dependencies;
- methods;
- planner/user gates;
- append-only revisions;
- exact project child tasks;
- evidence reconciliation.

It coordinates existing Local Agent tasks rather than replacing them.

### Attention Fabric

Owns low-latency hints:

- project task terminal-result events;
- later workflow/child/checkpoint attention events;
- durable outbox/replay;
- bounded dedupe;
- restart-safe wake delivery.

An attention event never proves success. It says durable evidence should be inspected.

### Chat Bridge

Owns browser actuation:

- exact existing-conversation wake delivery;
- lab child spawn transactions;
- bootstrap injection;
- conversation URL discovery;
- current-tab routing cache;
- logical retirement and optional tab close.

It does not plan repositories and does not get shell/task/rebind authority from child creation.

### Local Agent

Remains deterministic/model-free:

- immutable task contract;
- hard repository binding for Local Agent execution;
- claims/results;
- watchdogs/resource leases;
- exact cancellation;
- self-update/rollback;
- workflow coordination using existing repository workers.

## 3. Durable memory rule

Core rule:

> Conversations reason. Durable records remember.

No correctness may depend on retaining:

- one browser tab;
- full transcript access;
- one MV3 service-worker lifetime;
- one in-memory parent context;
- one Chrome tab id.

GitHub-backed control/evidence is planner-visible durable coordination. Local Agent may keep local durable materializations for restart-efficient execution, but each record type has one authority owner.

## 4. Authority by record type

### 4.1 Orchestration inputs — Git authoritative

A dedicated orchestration control branch/repository should own immutable planner-authored inputs:

- workflow/base request;
- append-only workflow revisions;
- child requests;
- planner continuation decisions;
- explicit user decisions submitted remotely.

Local Agent validates/ingests them and may materialize local state.

### 4.2 Workflow runtime state — derived locally

Effective node states, scheduler/backoff state and reconciliation state are derived from immutable inputs plus exact project evidence.

Local durable state is a materialization/cache. A central Git status projection is planner-visible but should not become a second independently mutable truth.

### 4.3 Project execution evidence — project control plane authoritative

Keep existing authority:

- task payload/digest;
- claim/run/status;
- terminal result;
- cancellation evidence.

Central workflow state references this evidence rather than copying raw logs.

### 4.4 Conversation registration — centrally durable after validation

The durable record resolves:

```text
child request id/digest -> exact ChatGPT conversation URL/id
```

Chrome storage/tab id are routing caches only.

## 5. Superchat authority

Superchat is planner/dispatcher/reviewer, not a generic cross-repository shell.

It may:

- inspect workflow-level evidence;
- create/append workflow graph revisions;
- create bounded child requests;
- decide independent work topology;
- inspect child checkpoints/terminal records;
- resolve planner checkpoints;
- create integration/verification nodes;
- request explicit user gates;
- finalize integrated workflow.

It may not:

- convert an ordinary project conversation into cross-repository execution authority;
- bypass Local Agent repository bindings;
- treat child prose as execution proof;
- silently broaden a child node;
- merge results merely because children say "done".

### Connector capability caveat

Local Agent hard binding constrains Local Agent tasks. It does **not** turn a broad account-level GitHub connector into a technical per-chat sandbox.

Conversation repository restrictions for direct GitHub tool calls remain policy unless narrower connector credentials/scopes are introduced. The design must not claim stronger enforcement than exists.

## 6. Child roles

v1 supports one parent level only.

### `research`

- architecture/code-path/API/risk analysis;
- no implementation unless a new node/revision explicitly authorizes it.

### `implementation`

- one bounded component;
- exact repository;
- exact branch ownership;
- implementation + focused verification;
- no merge to integration/main.

### `verification`

- independent candidate review;
- focused/full checks;
- rejects or reports issues rather than silently becoming an implementation chat.

### `integration`

- consumes exact predecessor commits/results/checkpoints;
- reconciles interfaces/conflicts;
- creates one integrated candidate;
- runs integration/full verification.

Children do not spawn children in v1.

## 7. Child request contract

Every child originates from one immutable bounded request with canonical digest.

Conceptual shape:

```json
{
  "schema_version": 1,
  "request_id": "child-...",
  "workflow_id": "litegraph-refactor-017",
  "workflow_revision": 3,
  "node_id": "mqtt-api",
  "role": "implementation",
  "parent_conversation_url": "https://chatgpt.com/c/...",
  "repository_id": "litegraph",
  "repository": "MichalMatu/esp32s3_LiteGraph",
  "agent_binding": "...",
  "work_branch": "wf/litegraph-refactor-017/mqtt-api",
  "depends_on": ["mqtt-audit"],
  "goal": "Refactor only the MQTT catalog API boundary.",
  "scope": {
    "allowed": ["src/mqtt/**", "tests/mqtt/**"],
    "forbidden": ["frontend/**", "storage/**"]
  },
  "required_outputs": [
    "implementation_commit",
    "focused_verification",
    "findings",
    "integration_notes"
  ]
}
```

The request id/digest exists before any browser tab is opened.

Large context is referenced by exact durable artifacts/commits instead of copied into every bootstrap.

## 8. Identity model

Do not use one identifier for all layers.

### Durable workflow identity

```text
workflow_id + revision + child_request_id + request_digest
```

### Durable browser conversation identity after registration

Exact canonical ChatGPT conversation URL/id.

### Ephemeral routing identity

Chrome tab id / preferred tab id.

### Existing Bridge `chat-xxxxxxxx`

May remain a local/UI map key, but its 32-bit hash is not a durable security/workflow identity.

## 9. Two child state machines

### 9.1 Logical workflow lifecycle

Conceptual v1:

```text
requested
-> registration_pending
-> active
-> terminal_pending_evidence
-> terminal_recorded
-> retired
```

This survives browser loss.

### 9.2 Browser spawn transaction

Conceptual:

```text
pending
-> tab_created
-> bootstrap_submitting
-> identity_discovered
-> registration_submitting
-> done
```

with explicit `failed` and `ambiguous` outcomes.

A browser failure cannot resurrect retired workflow work.

## 10. Browser child creation protocol

Current Bridge wake delivery requires a known `/c/<id>` URL. New-chat creation therefore uses a separate pre-registration protocol.

Preferred sequence:

```text
pre-existing exact child request
-> persist spawn transaction
-> open ChatGPT origin directly in a new tab
-> wait for generic composer readiness
-> inject deterministic bootstrap + request marker/digest
-> submit exactly once
-> confirm first user turn
-> observe route transition to one concrete /c/<id>
-> capture exact canonical URL
-> persist provisional mapping
-> durably register request -> child URL
-> convert to ordinary bound Bridge conversation
```

Do not automate a visible "New chat" navigation button unless unavoidable.

### Uncertain first delivery

On timeout/worker restart, reconcile the original tab before any retry:

- exact request marker present + `/c/<id>` => recover registration;
- exact tab still empty => retry same spawn transaction;
- unrelated content or ambiguous state => fail closed/manual attach;
- never create a replacement child solely because delivery confirmation timed out.

### Manual attach

v1 must allow the operator to open a fresh ChatGPT conversation and attach one exact pending child request. UI automation is a convenience layer, not the only recovery path.

### Spawn concurrency

Serialize child creation transactions in v1. Registered child work may continue concurrently.

## 11. Bootstrap prompt

Generated from durable request, not improvised from parent transcript.

Must include:

- machine-readable child request id/digest;
- workflow/revision/node/role;
- parent identity;
- repository/binding;
- work branch;
- bounded goal/scope;
- exact dependency/input references;
- required outputs/checkpoints;
- repository instruction discovery (`AGENTS.md`, handoff docs);
- no merge/finalization outside node contract.

Keep prompt bounded; reference large context instead of embedding it.

## 12. Durable child registration

The donor result-event Native Messaging host remains notification-only.

Conversation registration should use a **separate bounded native protocol/host** rather than silently broadening the event host.

Allowed conceptual messages:

```text
register_child
query_registration
retire_child
```

Browser supplies only identity discovered in UI plus exact request id/digest/generation. Local side loads repository/binding/role/branch from the pre-existing request.

No generic shell/Git/task/rebind API is exposed.

## 13. Planner progress is structured evidence, not transcript sync

Do not reuse command `[AGENT_PROGRESS]` as child-chat reasoning progress.

Conversation Fabric records:

```text
child_checkpoint
child_terminal
```

A checkpoint is append-only and bounded, with:

- request/workflow/node identity;
- sequence/stage;
- summary/findings;
- exact commit/task/result/CI references;
- contract changes/integration notes.

No full transcript or raw log dump.

Parent reads exact referenced authoritative evidence before consequential decisions.

## 14. Same-repository parallelism: important v1 limitation

Current Local Agent guarantees one active worker/task per registered repository. Different `work_branch` values do not create independent scheduler lanes.

Therefore v1 distinguishes:

### Conversation parallelism

Two same-repository child chats may reason simultaneously and may own separate GitHub source branches.

### Local Agent execution parallelism

Still serialized inside that repository.

### Existing true execution parallelism

Available across different registered repositories under current `max_workers`/resource policy.

True same-repository Local Agent concurrency is a future separately-audited **workspace lane** project, not a hidden requirement of Conversation Fabric v1.

## 15. Integration is first-class

Children are not merged because they all succeeded locally.

Integration consumes exact predecessor evidence and checks:

- conflicts;
- shared APIs/contracts;
- contradictory abstractions;
- error handling;
- isolated-test assumptions;
- architecture drift;
- final diff ownership.

It produces its own exact integrated commit/result. Optional verification then audits the integrated candidate from a fresh context.

## 16. Attention routing

Two bounded event families eventually share one notification substrate.

Project task:

```text
task_result_ready(repository, binding, task_id, digest)
```

routes to exact project conversation/watch.

Workflow/Conversation Fabric:

```text
child_terminal_recorded(workflow, node, request)
workflow_waiting_planner(...)
workflow_waiting_user(...)
workflow_failed(...)
workflow_completed(...)
```

routes to exact Superchat/workflow owner.

Events carry identifiers, not result bodies.

## 17. Restart/failure model

### Chrome/service-worker restart

- spawn transactions persist separately from existing Bridge state;
- exact registered URLs survive through durable registration;
- provisional tab ids are revalidated or discarded;
- ambiguous pre-registration operations fail closed;
- no duplicate child is created because memory was lost.

### Local Agent restart

- current no-replay task rule remains;
- workflow state reconstructs from admitted inputs + exact project evidence;
- conversation identity is not execution authority;
- attention events replay/reconcile.

### Child tab manually closed

- durable child record survives;
- terminal/retired child is not reopened;
- active missing child requires explicit recovery policy/manual attach rather than silent duplicate reasoning.

## 18. Runtime orchestration capability

Current runtime schema v3 has `execution_enabled` only. Superchat needs an explicit later schema migration, e.g. conceptually:

```text
execution_enabled = false
orchestration_enabled = true
```

Do not add the JSON field before code defines and tests its authorization semantics.

An ordinary project chat must never become orchestration-enabled because it emitted a control marker.

## 19. Security invariants

1. Child cannot change workflow/request/parent/repository binding/role.
2. Child cannot create siblings in v1.
3. Browser registration can only satisfy a pre-existing exact request/digest.
4. Project Local Agent tasks keep existing hard binding.
5. Superchat orchestration does not become generic project shell authority.
6. Event Native Messaging remains notification-only.
7. Conversation registration native protocol remains narrow and separate.
8. Planner checkpoints are bounded/schema-validated.
9. Integration trusts exact commits/results, not child self-assertion.
10. Global Local Agent disable remains authoritative.
11. Interrupted claimed tasks are never automatically replayed.
12. Current repository execution lease is not weakened by Conversation Fabric v1.
13. Do not claim broad GitHub connector writes are technically sandboxed by chat binding.

## 20. v1 non-goals

- recursive child delegation;
- unbounded child counts;
- whole-transcript streaming;
- hidden model-to-model channels;
- automatic merge without integration/review;
- true concurrent Local Agent tasks in one repository;
- generic desktop/browser automation outside exact ChatGPT lifecycle;
- generic browser-to-Local-Agent command API;
- distributed runners;
- automatic deletion of ChatGPT history.

## 21. Product validation

Two first slices are deliberately different:

### Same-repository modularity slice

Two child chats + separate source branches + integration; local Local Agent tasks remain serialized. Measures reasoning/integration quality.

### Multi-repository execution slice

Two child chats in different registered repositories; Local Agent tasks may genuinely overlap using the existing scheduler. Measures end-to-end parallel orchestration.

Success is measured through integration conflicts, rework, tests, unrelated churn, recovery interventions and context overhead — not tab count.
