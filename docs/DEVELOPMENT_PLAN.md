# Local Agent development roadmap

This roadmap contains only active forward work. Historical rollout detail belongs in release notes, self-diagnostic reports and archived evidence.

## Baseline — complete

- deterministic target-bound `.agent/tasks` execution;
- canonical runtime catalog as mandatory final execution authority;
- exact target `agent_binding` + `execution_enabled` admission;
- bounded parallel multi-repository scheduler and resource admission;
- granular host-maintenance preparation: software-only by default, explicit named resources when needed, and `machine` only for whole-host exclusivity;
- durable task/result/recovery contracts;
- crash-safe parallel dedupe completion reconciliation;
- GitHub-backed Chat Bridge conversation pacing;
- transport-only Superchat conversation identity;
- browser-native same-session Conversation Fabric in the operator's authenticated Chrome;
- reasoning-only Conversation Fabric children;
- durable campaign/result recovery in `chrome.storage.local`;
- terminal Conversation Fabric feedback at-most-once across worker restart;
- stale cross-campaign terminal replay prevention;
- same-browser multi-child live acceptance;
- supported `agentd.py` launcher fails closed when the machine repository registry is absent.

The isolated child-browser/profile path is historical test/development tooling only. It is not the production Conversation Fabric architecture.

## Milestone 1 — complete restart/reload E2E acceptance

Strengthen the browser acceptance so one deterministic scenario exercises the real production routing from parent control to terminal reconciliation:

- parent content discovers a real `LOCAL_AGENT_CF` delegate control;
- 3–4 ordinary child tabs are spawned through the installed extension;
- at least one child completes quickly and another remains active longer;
- stable results are captured and persisted before sibling completion;
- service-worker/extension lifecycle is interrupted while the campaign is active;
- captured results survive recovery;
- transient child observation failure recovers without bootstrap replay;
- final collection uses normal production polling/routing;
- exact owned child tabs are cleaned up;
- terminal feedback reaches the parent exactly once;
- a later reload/poll does not replay the terminal campaign.

Prefer a genuine MV3 worker/extension restart when the browser harness can force it deterministically. If Chrome does not expose a reliable test primitive, use the strongest production-shaped restart available and state the remaining limitation explicitly instead of simulating recovery only through direct helper calls.

### P0/P1 correctness — recover ambiguous post-submit routing

A production incident showed that `spawn_submission_ambiguous` can be a false negative after the bootstrap was actually sent: child tabs were created, received the exact bootstrap, completed their reasoning and produced final answers, but Fabric marked them failed and never collected their results. Fix this before later diagnostic/cosmetic hardening:

- treat post-submit routing ambiguity as recoverable evidence uncertainty, not proof that submission failed;
- never replay an ambiguous bootstrap and never create a replacement child merely because routing/identity proof is late;
- preserve the exact owned `tab_id` plus transaction/request/bootstrap claims while bounded reconciliation continues;
- promote an ambiguous child to `submitted` only after the existing transaction/request/bootstrap/current-route/current-child-URL ownership evidence proves identity; tab id alone is never sufficient;
- after service-worker restart, reconcile an interrupted ambiguous/submitting child from durable ownership evidence when possible instead of immediately terminally failing it;
- collect and persist final results from children successfully recovered after ambiguous submission before exact owned-tab cleanup;
- add a production-shaped four-child browser regression where at least three children initially hit delayed/provisional routing, each bootstrap is sent exactly once, all four later prove identity and return results, no duplicate child is created, terminal feedback is delivered once, and worker restart during ambiguity preserves recovery;
- add the negative case where a truly ambiguous tab never reaches verifiable child identity and bounded recovery eventually fails closed without replay;
- replace or split `campaign_timed_out_after_final_collect` so an ordinary campaign that simply remains running with pending children reports a semantically correct timeout such as `campaign_timed_out_with_pending_children`.

### P1 durability/operations — Result Vault and explicit child recovery

Make completed child work independently recoverable from later campaign/feedback/orchestration failures, and make failed/stuck child handling explicit without weakening no-replay:

- persist every stable child result into a separate bounded Result Vault record before campaign cleanup or terminal feedback;
- keep vault retention independent of the short campaign-history window so removing an old campaign record does not silently discard already-captured child work;
- retain campaign id, child id/role, child conversation URL, assistant identity, capture timestamp, bounded result text, truncation metadata and a content digest;
- provide a read-only `inspect` control for a managed parent to retrieve current child states plus archived/captured results without changing delivery receipts or resubmitting prompts;
- provide an explicit `retire` control for one exact child: close only the exact owned tab when ownership can be proven, mark the child failed/retryable, preserve any already-captured result, and never auto-submit a replacement;
- terminal/pending diagnostics should distinguish transient observation, submission ambiguity, operator retirement, closed/missing tab, ownership conflict and bounded timeout;
- after retirement or terminal child failure, parent feedback should make it clear which child coverage is missing and that a new delegation may intentionally reassign that bounded work with a new child id; the Bridge itself must not replay it;
- before terminal campaign failure/timeout, perform a final salvage observation of children that can still prove exact ownership so completed work is vaulted before cleanup;
- add regressions for: captured result survives campaign-history pruning, inspect returns it later, retire closes only the exact owned child, a closed/missing child becomes clearly retryable, and a later explicit re-delegation does not reuse/replay the retired bootstrap.

### P1 hardening — Conversation Fabric control-surface diagnostics

Immediately after the restart/reload E2E is stable, close the observed silent control-drop case without broadening Conversation Fabric authority:

- define the supported `LOCAL_AGENT_CF` control surface as the parser-owned terminal assistant turn, with the control block as the final non-whitespace content;
- if a visible assistant turn contains a `LOCAL_AGENT_CF` marker but the control is malformed, non-terminal or otherwise rejected, surface a deterministic diagnostic instead of silently treating the turn as if it contained no control;
- propagate worker control responses as explicit accepted/rejected acknowledgements with a stable reason instead of silently deferring every `ok: false` response;
- distinguish retryable transport/readiness failures from deterministic control rejection so invalid controls do not enter an opaque retry loop;
- preserve and expose the existing collect ownership failures, including `conversation_fabric_campaign_missing` and `conversation_fabric_parent_mismatch`;
- add browser regression coverage proving a control outside the supported terminal surface is rejected diagnostically, the same valid trailing control on the supported surface starts the expected children, and stale/foreign collect ids fail with the correct explicit reason;
- keep the model/runtime instruction explicit: delegation and collect blocks belong in the final assistant response and must be the last content in that response.

If an unsupported model channel is not represented in the DOM visible to the extension, the Bridge cannot diagnose that hidden channel directly. In that case the runtime/model instruction is the enforcing boundary; the Bridge diagnostic applies to markers that are actually observable on the page.

## Milestone 2 — runtime parity and timeout semantics — complete

The production contracts are now explicit and regression-protected:

- bounded parallel execution remains the production scheduler and owns full queue coalescing, dedupe reconciliation and crash-recovery semantics;
- serial `agent_multirepo.py` remains a bounded fallback/diagnostic path while reusing the safe shared queued-duplicate admission path; this does not imply full serial/parallel parity;
- `task_timeout` is a stage-admission execution budget anchored before workspace preparation, not a strict total wall-clock deadline; preparation consumes remaining stage budget while checkpoint/cleanup remain separately bounded finalization;
- every new stage must fit its configured timeout plus the finalization reserve inside the remaining task budget or fail before start with `task_budget_exhausted`;
- raw stdout byte/chunk activity now refreshes idle-watchdog activity through a side channel without injecting phantom output, while universal newline semantics remain preserved.

Future parity or timeout-contract expansion requires a concrete production consequence plus a dedicated regression; it must not be introduced merely for symmetry.

## Milestone 3 — operator observability — complete

One normal read-only status surface now combines the existing Local Agent and browser state domains without creating a second authority path:

- the Local Agent supervisor publishes bounded `.agent/status/operator.json` telemetry under the existing control-repository lease on semantic change or heartbeat;
- Local Agent telemetry reports exact `daemon_version` + deployed `self_revision`, Conversation Operator enabled/configured/running state, active `workflow_id`/parent identity/child count, and bounded durable dedupe suppression/rejection/reconciliation counts with reasons;
- crash completion reconciliation marks the existing durable dedupe receipt, so reconciliation is observable without changing admission or replay semantics;
- Chat Bridge runtime schema 3 accepts an optional read-only `operator_status_url`, restricted to `https://raw.githubusercontent.com`, with bounded fetch timeout/cache and no write authority;
- `bridge:get-state` combines that Local Agent snapshot with the installed Bridge manifest version and current Fabric/Vault campaign/result/cleanup/terminal-feedback state;
- the normal Bridge popup renders the combined snapshot as one compact Operator status card;
- Chat Bridge `0.8.4` carries this surface while content protocol `18` and repository execution authority remain unchanged.

Telemetry failure is fail-soft and must never block control reconciliation, scheduling or task execution.

## Milestone 4 — test architecture hardening — complete

The remaining helper-to-production gaps are now covered by focused production-path regressions:

- `tests/test_runtime_admission_matrix.py` drives both real serial and parallel `poll_repository_once()` entrypoints through canonical success, wrong-task-binding rejection, execution-disabled catalog admission and stale registry/control binding;
- `tests/test_parallel_ingestion_dedupe.py` exercises malformed dedupe metadata from a real `.agent/tasks/*.json` manifest and same-intent/same-revision conflicting plans through the production parallel poll/coalescing path;
- runtime-admission hardening and parallel-ingestion dedupe are included in the explicit macOS smoke gate;
- `scripts/conversation_fabric_browser_smoke.cjs` starts delegation from the parent assistant DOM, traverses the installed content-controller/worker route, creates ordinary same-browser child tabs and captures durable state through the production poll alarm; direct helper use is limited to harness setup, forced time advancement and bounded inspection/awaiting, not production delegation/recovery/polling/ownership/terminal-delivery transitions;
- that real-extension smoke stops and wakes the actual MV3 service worker, reconstructs exact child ownership without bootstrap replay, delivers terminal feedback once, restarts again, polls again and proves no completed-campaign replay;
- the same browser proof also covers explicit retire/redelegate recovery and a truly unresolved post-submit ambiguity that times out fail-closed without a second submit or replacement tab.

Do not add another browser harness merely to duplicate this path. A new test layer is justified only by a concrete uncovered production boundary.

## Milestone 5 — sequential delegation-cycle hardening — source closeout

Keep one parent conversation bound to exactly one project/main goal and harden repeated bounded reasoning cycles inside that project:

- delegate 1–4 reasoning-only children for one bounded task, durably capture their results, synthesize them in the parent and close only exact owned tabs before starting the next task;
- require a fresh campaign for each successive task so ownership, result and terminal-delivery state cannot leak from task A into task B;
- prove at least two consecutive delegation cycles in the same parent with no zombie tabs, stale terminal feedback, bootstrap replay or duplicate child creation;
- preserve explicit missing-coverage reporting and fail closed when ownership/result identity cannot be proven;
- make restart, timeout and manual/retained-composer submission recovery deterministic; an exact prompt submitted by the operator must be reconciled rather than inserted again, while delayed automatic submission must either settle exactly once or surface a bounded diagnostic;
- never auto-replace, auto-redelegate or fan out children; a new delegation is always an explicit parent decision;
- keep children reasoning-only and keep all repository/machine execution authority at the parent plus canonical target admission boundary.

Exit: one parent can execute repeated task A -> synthesize/close -> task B -> synthesize/close cycles reliably for one project, including bounded recovery interruptions, without cross-campaign leakage or replay.

## Milestone 6 — complete: Host Ops absorbed into Local Agent

This milestone is closed; no further donor migration is active work. Host Ops absorption is complete: the deterministic capability layer lives under `local_agent.host_ops`, host-maintenance targets `local-agent`, and the standalone execution identity is retired from the canonical catalog.

The architectural decision is fixed:

- Local Agent remains the sole brain/orchestrator and owns repository identity, canonical admission, scheduling, resource arbitration, watchdogs and durable task/run/result evidence;
- Host Ops contributes deterministic host/remote capability execution only;
- no planner, queue, scheduler, repository binding authority, Conversation Fabric policy or second daemon/control plane moves from the donor;
- preserve the donor's `core -> capabilities -> workflows -> cli` ownership and its JSON contract before attempting redesign;
- migrate production code/tests/docs separately from isolated prototypes;
- preserve `work/cpu-gpu-routing` (or export its research history) before donor retirement;
- keep the standalone `MichalMatu/host-ops` repository frozen/history-only; preserve `work/cpu-gpu-routing` until that research is intentionally closed.

The detailed migration and exit criteria are in `docs/HOST_OPS_ABSORPTION_PLAN.md`.

## Milestone 7 — active: consolidate Host Ops into a complete multi-tool runtime

The next development phase is deliberately ordered. Do not skip ahead to capability expansion or a ChatGPT plugin before the existing tooling baseline is understood and hardened.

### Phase A — inventory and normalize what already exists

- build one canonical inventory of every maintained Host Ops capability/workflow/CLI surface plus the deterministic browser/chat-UI primitives that may belong in the tool layer;
- record for each operation its owner, inputs, structured result, external dependency, side-effect/risk class, timeout/output bounds, resource needs and current test/live-smoke coverage;
- identify duplicate concepts, CLI-only glue, hidden cross-capability coupling and capabilities whose current boundary is artificially narrow;
- make no behavior change merely to make the inventory look uniform.

### Phase B — debug, test and harden the existing tools

- exercise each existing tool through focused unit/integration tests and, where physical I/O matters, bounded live smoke;
- fix correctness, timeout, cleanup, result-contract and recovery defects before adding broad new authority;
- keep failures explicit and evidence bounded;
- preserve the existing `cli -> workflows -> capabilities -> core` dependency direction unless a later contract change explicitly replaces it.

### Phase C — define the Local Agent <-> Tool Runtime contract

Only after the existing tooling is understood and hardened, introduce a small internal tool contract/registry shared by Local Agent and Host Ops. The contract should describe stable tool identity, validated arguments/results, effect/risk class, resource requirements, execution bounds and artifact behavior.

The contract is internal to Local Agent execution. It must not create a second scheduler, planner, daemon or control plane. GitHub remains the sole durable ChatGPT <-> Local Agent control/evidence plane.

### Phase D — expand into a complete reusable multi-tool surface

After the contract is proven on existing tools, broaden reusable capabilities such as ADB, SSH, filesystem/process, network, browser and device operations. Capability breadth should not be artificially restricted when a general deterministic boundary can be validated and governed by Local Agent policy.

Risk/authorization policy belongs above the primitive capability where practical: a capability may support a general deterministic operation while Local Agent admission decides whether a specific invocation is read-only, mutating, arbitrary-code-like or requires an exclusive/named resource.

### Phase E — prepare the future ChatGPT plugin without changing transport authority

A future Local Agent ChatGPT plugin is an ergonomic product surface over the same GitHub-backed contracts. It must not introduce MCP, a direct ChatGPT-to-Local-Agent execution server or any parallel control transport.

The intended shape remains:

```text
ChatGPT / future plugin
    -> GitHub control + evidence
        -> Local Agent admission / scheduling / policy
            -> Host Ops Tool Runtime
                -> machine / device / browser / remote effects
```

Conversation Fabric remains Local Agent orchestration. It owns child-request semantics, campaign ownership, result collection, retry/retire policy and synthesis. Deterministic browser/chat-UI lifecycle primitives may move into or be exposed through Host Ops tooling, but "delegate children and reconcile their reasoning" must not become a Host Ops workflow or planner responsibility.

Exit for this milestone: existing tools are inventoried and hardened, the Local Agent/tooling boundary is explicit and regression-protected, and new capabilities can be added without inventing one-off execution contracts.

## Not current work

Do not reopen legacy repository-bound chat routing, isolated-profile production control, bounded multi-goal parent supervision, a second executor/scheduler, child machine authority, cookie migration, direct OpenAI API reasoning loops or predictive autonomous fan-out. Those directions conflict with the accepted architecture or add authority outside the current safety model.
