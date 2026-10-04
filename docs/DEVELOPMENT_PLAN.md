# Local Agent development roadmap

This roadmap contains only active forward work. Historical rollout detail belongs in release notes, self-diagnostic reports and archived evidence.

## Baseline — complete

- deterministic target-bound `.agent/tasks` execution;
- canonical runtime catalog as mandatory final execution authority;
- exact target `agent_binding` + `execution_enabled` admission;
- bounded parallel multi-repository scheduler and resource admission;
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

## Milestone 2 — runtime parity and timeout semantics

Close remaining correctness gaps only where current production behavior is confirmed:

- define whether serial fallback must share production parallel dedupe semantics or is intentionally a reduced recovery mode;
- make any intended parity explicit in tests and operations docs;
- decide whether `task_timeout` is a command-budget concept or a full task wall-clock contract including prepare/checkpoint/cleanup, then make implementation + docs agree;
- ensure idle-output activity is measured at the byte/chunk boundary if commands that emit progress without newline are supported.

Do not change these semantics merely for symmetry; require a production consequence and a regression first.

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
