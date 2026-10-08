# Local Agent — target product architecture

Status: **canonical long-term target-product direction on `main`**. This is a design decision and acceptance contract, not a statement that the GitHub-first transport is already deployed.

This document defines the desired end state. `CURRENT_PLAN.md` remains the staged execution/checkpoint ledger. Historical Conversation Fabric plans are implementation history, not competing target architectures.

## 1. Product verdict

The target is one user-visible Local Agent product with one repository and one long-lived Operator Chat / Superchat.

The architecture has one non-negotiable control-plane rule:

> **All durable control, coordination, task state, conversation state and execution evidence flow through GitHub-backed Local Agent contracts. There is no MCP server, direct OpenAI API model loop or second control transport in the target architecture.**

The intended end-to-end shape is:

```text
User
  -> Operator Chat / Superchat (ordinary ChatGPT conversation)
    -> GitHub control/evidence plane
      -> Local Agent core
        -> host-ops tool runtime
        -> ChatGPT Browser Driver for child-chat UI lifecycle only
      -> GitHub result/evidence
    -> Operator Chat reads and synthesizes the durable result
```

The product must feel like one system without turning the layers into one unrestricted monolith.

## 2. Hard architecture invariants

These rules are deliberate product decisions, not temporary migration constraints:

1. **GitHub is the only control/evidence plane between ChatGPT reasoning and Local Agent execution.**
2. **No MCP server is part of the target architecture.** MCP must not be introduced as a primary, fallback, optional or future control path unless this canonical architecture is explicitly replaced by a later user decision.
3. **Local Agent does not call the OpenAI API to run the reasoning model.** Reasoning remains in ordinary ChatGPT conversations used by the user.
4. **No direct ChatGPT-to-Local-Agent server transport is authoritative.** Any future convenience integration may only prepare or observe GitHub-backed state; it must not bypass the GitHub contract.
5. **Browser/DOM state is never task, workflow or conversation authority.** It is transport evidence for bounded chat-UI lifecycle effects only.
6. **host-ops never plans.** It remains a deterministic toolbox invoked under Local Agent authority.
7. **Child chats never gain independent machine authority.** They reason within bounded scope and return bounded results through the durable coordination path.

If a proposal violates any invariant above, it is outside the current target architecture.

## 3. One long-lived supervisory chat

The canonical human-facing control surface is one dedicated **Operator Chat / Superchat** in ChatGPT.

It is intended to be long-lived. It owns reasoning and supervision across registered projects and bounded reasoning children:

- retain the top-level goal and compact campaign state;
- decide which repository or reasoning child needs work;
- create bounded child reasoning requests when separate context is useful;
- publish durable Local Agent work requests through GitHub;
- inspect durable task/result evidence from GitHub;
- synthesize results across children and repositories;
- pause, cancel or continue work through explicit durable control state.

The Superchat must not accumulate full child transcripts, build logs or large raw artifacts by default. Children return bounded terminal summaries plus exact evidence references. Raw evidence remains outside the parent context.

Project/child chats are bounded reasoning workers. They are not independent operators competing for machine authority.

The user should not need a separate `host-ops` chat or a second operator binding.

## 4. ChatGPT is the reasoning layer

ChatGPT remains responsible for planning, decomposition, review and synthesis.

This reasoning occurs in ordinary ChatGPT conversations — the Superchat and its bounded child chats. The target does **not** replace those conversations with direct OpenAI API inference owned by Local Agent.

Local Agent remains model-free and deterministic. It must not acquire a hidden planner, local model loop, OpenAI API model client or heuristic autonomous reasoning layer merely to replace the chat.

Conversation Fabric is the durable coordination model between the Superchat and bounded child reasoning contexts. Its authoritative records are persisted through the GitHub-backed Local Agent control/evidence contracts.

## 5. GitHub is the single control and evidence plane

GitHub is not merely a migration baseline. It is the target system boundary between the reasoning layer and Local Agent.

Canonical control flow:

```text
Superchat decides an action
  -> writes or updates exact GitHub-backed control state
  -> Local Agent admits and executes from that durable state
  -> Local Agent publishes bounded result/evidence back to GitHub
  -> Superchat re-reads authoritative GitHub state
  -> Superchat decides the next action
```

Canonical child-reasoning flow:

```text
Superchat
  -> durable ChildRequest / campaign state in GitHub-backed contracts
  -> Local Agent / Conversation Fabric owns exact lifecycle state
  -> Browser Driver or manual fallback creates/attaches the ordinary ChatGPT child
  -> child returns bounded checkpoint/terminal information
  -> durable child state/result is recorded through GitHub-backed contracts
  -> Superchat reads and synthesizes it
```

No ephemeral chat text, browser event, DOM state, local socket or external server may silently replace this authority.

## 5a. Durable, device-independent project continuity — product target

**The Superchat is a user interface, not the project database.** The user must be able to
start a project in an ordinary ChatGPT conversation on a Mac, close that chat/browser,
later use a ChatGPT conversation on a phone or desktop, and rehydrate the project from
its **GitHub-backed Local Agent state** without relying on the original ChatGPT DOM or
the model remembering the earlier session. The new ChatGPT session must explicitly
resolve the authorized project/workflow and read its durable state before proposing new
actions; merely opening any chat does not automatically restore model context.

The product view reconstructed from GitHub must show, at minimum:

- **what exists:** canonical project and workflow identity, goal, bounded accepted plan,
  current phase, task/delegation graph and exact causal links;
- **what happened:** append-only, versioned and attributable events for requests,
  admissions, dispatches, child acknowledgments, observations, result capture, local
  task submission and execution, decisions, failures, recoveries and retirement;
- **what is happening:** authoritative per-workflow and per-child state, last confirmed
  checkpoint, required next action, source revision and last observation timestamp;
- **what needs a decision:** explicit pending approvals, ambiguous outcomes, human
  interventions and safe retry/retire options, rather than quietly assuming success;
- **what can be recovered:** bounded immutable request/response evidence or approved
  pointers, content digests, checkpoint snapshots and replay-safe reconciliation
  metadata that allow state reconstruction after chat closure, browser restart,
  network outage or interrupted execution.

Use an **append-only event journal plus materialized bounded snapshots/indexes**.
Every event is bound to a stable workflow/campaign/request identity, actor and authority,
monotonic version/sequence or equivalent conflict-proof ordering, causal predecessor,
timestamp and integrity evidence. A snapshot is a derived cache, not an independent
source of truth. Consumers must detect gaps, duplicates, reordered/conflicting writes
and stale snapshots; reconciliation must never silently erase evidence or replay an
ambiguous side effect.

**Durability guarantee:** once an authoritative write has been acknowledged and
the required immutable evidence is persisted, closing the ChatGPT tab must not make
that accepted state disappear. An unsent browser turn, unacknowledged result or
non-durable in-memory observation can still be lost. Surface such uncertainty as
`pending`, `unconfirmed` or `requires_reconciliation`, not as an invented success.
For bounded disconnected operation, journal local browser evidence durably and
reconcile it on reconnection with exact identity and idempotency checks. Never
automatically resubmit an ambiguous child prompt or machine effect.

**"Full history" means complete auditable history of admitted, recorded
coordination transitions**, not automatic storage of hidden model reasoning,
complete ChatGPT transcripts or arbitrary sensitive user data. Store minimal
summaries, immutable digests and evidence references by default; use an appropriately
authorized private/encrypted evidence store when source material is sensitive.
GitHub repository history alone is not permanent backup: document pruning,
access control, retention, integrity checks, backup/export and recovery procedures
so compaction, force pushes or repository removal cannot silently destroy
the accepted audit trail. The current public `raw.githubusercontent.com` intake
must not receive confidential prompts or raw child transcripts.

**GitHub Actions is not the workflow engine.** GitHub repositories and authenticated
Git-backed records provide coordination/evidence; Local Agent owns long-running
execution, scheduling and recovery, while Chat Bridge performs browser effects.
GitHub Actions may test proposed source changes, but an exhausted Actions quota,
queued CI job or disabled runner must not prevent the installed system from
reading existing workflow state, preserving verified events or presenting a
pending decision. Actions unavailability also does not excuse bypassing
the required CI gate for merging new code.

**Responsiveness target:** retain a safe minute-scale GitHub poll initially for
durable multi-minute work, and surface freshness/last-sync status. Lower-latency
push or notification paths may be explored later as optional wake hints, never
as a competing control-plane authority.

**Migration strategy:** do not rewrite or disable the accepted Chrome Bridge
0.8.13 path in one step. Add an off-by-default GitHub-first read-only channel,
advance through explicit publication/admission, browser-dispatch, trusted
result-writeback and live recovery gates, and retain the existing DOM delegation
as an exclusively arbitrated compatibility fallback until parity and rollback
are proven. DOM is still necessary for ChatGPT UI interactions and bounded
result observation, but it does not define durable workflow truth.

### Acceptance scenario — Mac to phone after chat closure

1. A parent conversation accepts a bounded request and receives a verified
   durable GitHub receipt for its exact project/workflow identity.
2. The operator closes the Mac ChatGPT tab; ongoing Local Agent tasks can continue,
   and any browser-only child work is honestly marked suspended or awaiting an
   available authenticated Browser Driver if needed.
3. On the phone, the user opens ChatGPT and explicitly selects/resolves that
   workflow; the authorized integration reads GitHub event/snapshot records.
4. The new view shows completed, running, failed, waiting and decision-required
   items with evidence references and last-sync age. Unknown outcomes remain
   unknown, not silently marked done.
5. When the browser driver and Local Agent reconnect, they reconcile exact
   identities and previously acknowledged work without duplicate child prompts,
   tasks or notifications. An intentional retry requires a new explicit identity
   and operator/parent decision.

Successful end-to-end recovery must be demonstrated across independently
restarted ChatGPT/Chrome, Local Agent and network connections before this
becomes a release-level durability claim.

## 6. Local Agent is the control and execution core

Local Agent owns:

- repository catalog and canonical repository identity;
- immutable per-repository execution bindings;
- task admission and immutable task digests;
- scheduling, repository leases and shared-resource arbitration;
- watchdogs, bounded execution and process cleanup;
- durable task/run/result evidence;
- cancellation, emergency disable and recovery;
- conversation lifecycle records used by Conversation Fabric;
- selection and invocation of approved tool capabilities;
- synchronization with the GitHub-backed control/evidence plane.

The Superchat requests high-level work through durable GitHub state. It should not need to know whether a task ultimately requires ADB, SSH, browser inspection, serial, storage or another low-level capability.

Per-repository `agent_binding` remains an internal execution-safety authority. Removing extra user-facing bindings must never weaken exact target-repository admission.

## 7. host-ops becomes the internal tool runtime

The current `host-ops` capability model is retained, but its target product role changes from a separately operated repository/product to the internal deterministic tool layer of Local Agent.

It owns bounded capabilities such as:

- host/tool inspection;
- network probes;
- artifact inspection/deployment;
- browser inspection and explicitly authorized bounded effects;
- ADB/device operations;
- serial transport;
- macOS/removable-storage operations;
- SSH and remote-host operations;
- exact-revision remote Git execution.

It must not own planning, repository routing, task scheduling, chat supervision or durable workflow decisions.

Desired dependency direction:

```text
GitHub-backed Local Agent task authority
  -> Local Agent application/control services
    -> tool interface
      -> host-ops capabilities
```

A capability returns structured evidence. Local Agent decides how that evidence affects durable task state. ChatGPT decides what to do next only after reading authoritative GitHub-backed evidence.

## 8. One repository, preserved module boundaries

The target source layout is a monorepo. Exact package names may evolve, but ownership should remain equivalent to:

```text
local-agent/
  local_agent/
    conversation/            # Conversation Fabric durable coordination
    repository/              # repository identity and binding
    runtime/                 # task lifecycle, watchdogs, results
    supervisor/              # scheduling and resources
    operator/                # explicit local/remote controls
    tools/                   # Local Agent-facing tool abstraction
    workflow/                # GitHub-backed control/workflow contracts

  host_ops/                  # deterministic capability implementation
    core/
    capabilities/
    workflows/

  chat_browser/              # narrow ChatGPT Browser Driver

  tests/
  docs/
```

There is intentionally no `integrations/openai` or MCP server required by the target product architecture.

The separate `MichalMatu/host-ops` repository is archived and retained only as donor/history and preserved research evidence. Maintained Host Ops runtime ownership is exclusively `local_agent.host_ops` inside Local Agent; the donor is not an execution target.

## 9. Chat Bridge target role: narrow ChatGPT Browser Driver

Chat Bridge is **retained**, but its target responsibility is deliberately reduced.

It is not the planner, scheduler, repository router, campaign owner, control plane or source of conversation truth. Those responsibilities belong to Superchat + Conversation Fabric + Local Agent with GitHub-backed authority.

The retained Bridge/browser layer owns only bounded ChatGPT UI lifecycle effects:

- open a fresh ordinary ChatGPT conversation when a child is requested;
- insert one exact prepared bootstrap prompt;
- verify that submission was actually accepted;
- discover and return the canonical `/c/<id>` conversation identity;
- reopen/select an exact known conversation when required for lifecycle work;
- close or retire an exact child conversation only after durable retirement authority exists;
- expose bounded readiness/recovery evidence for those operations.

The Bridge must preserve proven safety mechanisms where useful:

- exact conversation targeting;
- do not overwrite operator-authored composer content;
- do not submit while ChatGPT is visibly generating;
- re-resolve the live Send control at the submission boundary;
- confirm the exact submitted user turn;
- recognize only explicitly supported retry/error states;
- fail closed on ambiguity;
- recover restart/lost-ack state without blindly duplicating a child or prompt.

These mechanisms are valuable and should be reused rather than rewritten casually.

## 10. What Chat Bridge must no longer own

The following are removed from the target Bridge authority even if compatibility code exists during migration:

- task planning or decomposition;
- repository selection or rebinding decisions;
- Local Agent scheduling;
- campaign/workflow truth;
- parent/child semantic ownership;
- durable status/result authority;
- autonomous timing policy for the whole system;
- interpreting arbitrary assistant text as execution authority;
- acting as an alternative to GitHub for control or result transport.

DOM state is transport evidence only. It never proves task success, workflow success or parent/child lifecycle completion by itself.

## 11. Conversation lifecycle model

Local Agent/Conversation Fabric owns the logical graph:

```text
Superchat / parent
  -> durable ChildRequest
  -> child lifecycle record
  -> exact child registration
  -> bounded child reasoning
  -> child_checkpoint / child_terminal
  -> compact parent ledger
  -> parent synthesis
```

The browser driver owns only the physical UI transaction needed to realize lifecycle steps in ChatGPT.

Durable identities stay distinct:

1. campaign/workflow identity;
2. immutable `ChildRequest` id + digest;
3. canonical child registration to one ChatGPT conversation id/URL;
4. ephemeral browser tab id used only for routing/recovery;
5. exact Local Agent task ids where machine execution is needed.

A browser tab id is never authority.

## 12. Manual lifecycle is a first-class fallback

The architecture must work even when automatic child creation is unavailable or intentionally disabled.

Manual fallback flow:

```text
Superchat prepares exact ChildRequest + bootstrap prompt
  -> user opens a new ChatGPT conversation
  -> user pastes the prepared prompt
  -> child conversation is manually attached/registered
  -> normal Conversation Fabric lifecycle continues
```

This is not an error path. It is a supported baseline and a recovery path for browser ambiguity.

Automatic Chromium/Bridge creation is an ergonomic layer over the same durable lifecycle contract. It must never introduce a second semantic or control path.

## 13. Binding model in the target product

The user-facing model becomes one Operator Chat supervising one Local Agent installation through GitHub-backed control state.

Internally:

- Local Agent keeps a validated catalog of repositories;
- every executable repository keeps its own canonical `agent_binding`;
- every execution task targets exactly one validated repository binding;
- Superchat may supervise multiple catalog repositories without rebinding itself for each target;
- `host-ops` is not a separately bound planner target after monorepo migration;
- tool capabilities execute under the Local Agent task that authorized them;
- child chats inherit bounded reasoning scope, not independent machine authority.

This removes repeated operator binding work without collapsing repository isolation.

## 14. Normal target flows

Interactive execution flow:

```text
User on ChatGPT phone/desktop
  -> Superchat decides next action
  -> Superchat writes exact GitHub-backed control request
  -> Local Agent admits exact repository task
  -> Local Agent invokes host-ops tools as needed
  -> Local Agent records bounded result/evidence in GitHub-backed state
  -> Superchat reads authoritative result and continues reasoning
```

Multi-chat reasoning flow:

```text
User
  -> Superchat
     -> ChildRequest A -> durable state -> Browser Driver/manual attach -> child chat A
     -> ChildRequest B -> durable state -> Browser Driver/manual attach -> child chat B
     -> exact Local Agent tasks through GitHub-backed authority
     -> compact durable ledger
  -> final synthesis
```

The Superchat is the supervisor. Child chats do not independently own the machine.

## 15. Explicitly rejected architecture

The following design is not part of this project direction:

```text
ChatGPT
  -> MCP server / custom model-tool server
  -> Local Agent
```

Neither is this:

```text
Local Agent
  -> OpenAI API
  -> model reasoning loop
```

Nor any hybrid where MCP/API and GitHub are parallel authorities.

Reasons:

- it creates two competing control planes;
- it makes product behavior depend on a separate server/API transport instead of the existing durable GitHub contract;
- it risks moving reasoning out of the user's ordinary ChatGPT conversations;
- it complicates recovery, auditability and exact source-of-truth rules;
- it is unnecessary for the desired phone/desktop Superchat workflow.

MCP or direct OpenAI API model execution may be discussed historically, but must not be presented in current documentation as an implementation option, fallback or planned future phase.

## 16. Migration plan

### Phase A — freeze the target architecture

- treat this document as the canonical end-state direction;
- keep `CURRENT_PLAN.md` as the implementation checkpoint only;
- enforce the GitHub-only control-plane invariant;
- remove current-documentation language suggesting MCP or direct OpenAI API model execution as a target path;
- do not add new long-lived competing architecture plans.

### Phase B — define the Local Agent tool interface

Define stable typed Local Agent-facing capability contracts around the useful host-ops surface before moving source trees.

### Phase C — monorepo host-ops migration — complete

- maintained Host Ops source, tests and documentation live under Local Agent;
- capability ownership and security invariants remain preserved;
- Local Agent is the only product/release owner and host-maintenance execution target;
- the standalone donor is archived after parity/cutover smoke, with `work/cpu-gpu-routing` preserved as research history.

### Phase D — GitHub control-plane consolidation

- preserve one exact GitHub-backed control/evidence contract for Superchat <-> Local Agent interaction;
- keep Local Agent deterministic and model-free;
- ensure task, workflow, conversation and result state have one durable authority;
- remove or quarantine any experimental direct-server path that could be mistaken for a second control plane.

### Phase E — Superchat + Conversation Fabric lifecycle

Make one long-lived Superchat the normal supervisory surface. Keep compact durable parent state and bounded child contexts.

First prove the manual `prepare -> open/paste -> attach -> run -> terminal -> retire` lifecycle.

### Phase F — narrow automatic ChatGPT Browser Driver

Adapt the strongest existing Chat Bridge mechanisms to automate only the physical child-chat lifecycle:

```text
prepare -> create -> bootstrap -> identify -> register
...
terminal authority -> retire
```

Require exact identity, duplicate suppression, restart recovery and fail-closed ambiguity. Manual attach remains the fallback.

### Phase G — remove obsolete Bridge responsibilities

After the narrow driver is proven, delete or quarantine Bridge code that duplicates planning, schedule ownership or durable status authority. Keep only the minimal browser lifecycle driver and its tests.

If ChatGPT later gains a supported native capability to create/register/retire ordinary child conversations from the supervising chat, that capability may replace the physical Browser Driver only after explicit user approval and live parity proof. It must still use the same GitHub-backed durable Conversation Fabric authority and must not introduce a second control plane.

## 17. Non-goals

The target explicitly does **not** mean:

- an MCP server;
- a direct OpenAI API reasoning loop inside Local Agent;
- one unrestricted Python module containing everything;
- exposing shell/ADB/browser internals directly to ChatGPT;
- weakening per-repository bindings because the user sees one chat;
- giving child chats independent machine authority;
- creating another local AI planner inside Local Agent;
- making browser DOM state authoritative;
- deleting proven Bridge recovery/delivery mechanisms that remain useful to the narrow lifecycle driver;
- making Chat Bridge the system scheduler again;
- merging host-ops source before defining its stable internal API boundary.

## 18. Decision rules for future work

When a proposed feature appears, place it by ownership:

- reasoning, decomposition, synthesis -> Superchat / ordinary ChatGPT conversations;
- durable cross-chat reasoning coordination -> Conversation Fabric records under GitHub-backed authority;
- repository/task identity, scheduling, execution lifecycle -> Local Agent core;
- deterministic machine/device/remote-host effect -> host-ops tool runtime;
- Superchat-to-Local-Agent control/results -> GitHub-backed control/evidence plane only;
- physical ordinary-ChatGPT child conversation UI lifecycle -> ChatGPT Browser Driver or manual fallback;
- durable source/task/result evidence -> validated Local Agent/GitHub contracts.

If a feature would place the same authority in two layers or introduce a second control transport, redesign it before implementation.

## 19. Success state

The migration is complete when the user can open one long-lived Superchat in the ChatGPT app on phone or desktop, supervise work across registered repositories, delegate local-machine/device tasks, receive authoritative results and coordinate bounded child reasoning without separately operating `host-ops` or manually maintaining repository/chat bindings beyond the supported fallback.

Where ordinary ChatGPT child conversations still require browser UI lifecycle operations, the retained ChatGPT Browser Driver performs only those narrow bounded effects. The rest of the system remains independent of DOM state.

From the user's perspective it is one product:

```text
ChatGPT reasons and supervises in ordinary conversations.
GitHub carries authoritative control, coordination and evidence.
Local Agent controls deterministic execution and durable conversation state.
host-ops performs bounded machine effects.
ChatGPT Browser Driver performs only missing chat-UI lifecycle effects.
```
