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

## Milestone 3 — operator observability

Expose one concise normal status surface for:

- Conversation Operator enabled/configured/running state;
- active parent goal and child count;
- current campaign id/state and captured-result count;
- terminal feedback delivery state;
- queue dedupe suppression/reconciliation counts and reasons;
- exact deployed Local Agent and Chat Bridge revisions.

This should remove the need to infer operator readiness from scattered files.

## Milestone 4 — test architecture hardening

Reduce the gap between helper-level confidence and production-path confidence:

- shared serial/parallel runtime-admission acceptance matrix;
- real worker-path wrong-binding, execution-disabled and stale-registry cases;
- production-ingestion dedupe collision/malformed-metadata cases;
- browser smoke that goes through content → worker event routing → durable state instead of calling Fabric helpers directly;
- explicit restart/reload regression for terminal at-most-once delivery.

## Milestone 5 — bounded multi-goal supervision

Only after the complete restart/reload E2E remains stable:

- deterministic active-goal limit;
- explicit priorities and pause/resume;
- bounded spawn rate;
- repository-aware policy;
- circuit breakers for repeated blocked/failed goals;
- compact fleet snapshot for the parent.

## Not current work

Do not reopen legacy repository-bound chat routing, isolated-profile production control, a second executor/scheduler, child machine authority, cookie migration, direct OpenAI API reasoning loops or predictive autonomous fan-out. Those directions conflict with the accepted architecture or add authority outside the current safety model.
