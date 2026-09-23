# Superchat roadmap

This roadmap intentionally delivers deterministic lifecycle infrastructure before adding broad autonomous behavior.

## Phase 0 — Evidence and contracts

Status: in progress.

Goals:

- preserve the observed maximum-length DOM contract;
- keep a sanitized regression fixture derived from a real exhausted ChatGPT page;
- document current Chat Bridge boundaries and failure semantics;
- define the durable goal and operation models before runtime changes.

Deliverables:

- `docs/superchat/` documentation set;
- canonical `docs/CHATGPT_DOM_CONTRACT.md` kept current;
- minimal sanitized exhausted-conversation HTML fixture;
- DOM contract unit tests using that fixture;
- inventory of current Chat Bridge lifecycle owners.

Exit criteria:

- terminal exhaustion detection is covered by a fixture-based regression test;
- no implementation step depends on unstable generated CSS classes or SVG ids;
- the state and protocol design has explicit fail-closed rules.

## Phase 1 — State schema v4

Goal: introduce durable supervision state without changing chat creation behavior yet.

Work:

- extend `bridge_state.js` with `supervisor`, `goals` and `operations` domains;
- add sanitizers and bounded schemas for each domain;
- add v3 -> v4 migration;
- preserve all current conversation behavior after migration;
- add goal lifecycle state-machine helpers;
- add idempotent operation-journal helpers.

Exit criteria:

- old v3 state migrates losslessly;
- malformed goal/operation state fails closed or is dropped according to a documented rule;
- existing Chat Bridge tests still pass unchanged where behavior is not intentionally affected.

## Phase 2 — Checkpoints

Goal: make long-running goal continuity independent from a final message in an exhausted chat.

Work:

- define a bounded structured checkpoint contract;
- add deterministic storage/update rules;
- allow a bound child planner to publish/update only its own goal checkpoint;
- record exact evidence references separately from prose summary;
- add periodic checkpoint policy and an explicit checkpoint request path.

Important rule:

A hard maximum-length event must be recoverable from the last durable checkpoint plus current repository/Local Agent evidence. The old chat is not required to answer again.

Exit criteria:

- a goal can be reconstructed after deleting all in-memory service-worker state;
- stale child generations cannot overwrite a newer checkpoint;
- checkpoint size and retained history are bounded.

## Phase 3 — Replacement chat creation primitive

Goal: create one new ChatGPT conversation safely from a known catalog binding and bootstrap.

Work:

- add a dedicated new-chat content path rather than weakening normal `bridge:feedback` URL checks;
- open/navigate a tab to the ChatGPT new-chat UI;
- wait for a clean composer;
- submit one bounded continuation bootstrap;
- observe transition to a concrete `/c/<id>` URL;
- register the conversation with the selected existing catalog binding;
- return exact evidence of the created conversation id/url.

Exit criteria:

- duplicate invocation with the same operation id cannot create two authoritative workers;
- unknown or ambiguous page state fails closed;
- current normal conversation delivery remains hard URL-bound.

## Phase 4 — Deterministic rollover

Goal: replace one worker generation with another using an explicit transaction.

Work:

- add rollover operation state machine;
- support both proactive rotation and terminal exhaustion;
- reconcile incomplete rollover after service-worker/browser restart;
- activate the new generation only after durable registration;
- retire the old conversation according to the correct hard-exhausted/proactive path;
- keep history immutable.

Exit criteria:

- simulated restart at every transaction boundary either resumes safely or stops in `NEEDS_SUPERVISOR`;
- no test can produce two authoritative active workers for the same goal;
- repeated rollover event is idempotent.

## Phase 5 — Superchat control protocol

Goal: let one configured supervisor conversation request bounded lifecycle actions.

Work:

- add a separate strict `[LAS:*]` parser/module;
- configure exactly one supervisor conversation or explicit supervisor identity;
- validate sender, URL, frame, baseline, binding revision and generation;
- implement lifecycle requests over known `goal_id` and catalog entries;
- keep `[LAB:*]` same-chat semantics unchanged.

Initial actions:

```text
START_GOAL
WAKE_GOAL
PAUSE_GOAL
REQUEST_CHECKPOINT
ROTATE_GOAL
STOP_GOAL
```

Exit criteria:

- a normal child cannot control another child;
- Superchat cannot rebind an existing conversation;
- malformed or replayed controls have no external effect.

## Phase 6 — Fleet snapshot and supervision loop

Goal: give the Superchat planner enough bounded state to make useful decisions.

Work:

- aggregate goal state, active generation, chat status, checkpoint freshness and exact evidence pointers;
- provide a bounded fleet snapshot to the supervisor conversation;
- wake the supervisor on meaningful lifecycle transitions rather than every low-level event;
- add explicit `COMPLETED`, `BLOCKED`, `NEEDS_SUPERVISOR` transitions.

Exit criteria:

- supervisor prompts remain bounded as the number of historical chats grows;
- historical chat text is not copied wholesale into supervisor context;
- exact evidence pointers remain available for verification.

## Phase 7 — Predictive rotation

Goal: rotate before hard exhaustion as an optimization.

Possible signals:

- total conversation character/message count;
- conversation age;
- checkpoint age;
- explicit worker request;
- future reliable platform signal if one becomes available.

Rules:

- predictive context estimation is advisory only;
- hard DOM exhaustion remains the correctness fallback;
- thresholds must be configurable and bounded;
- false positives may cause an early rollover but must not lose work.

## Phase 8 — Multi-goal scheduling policy

Goal: allow Superchat to coordinate several repositories/goals without turning the LLM into an unsafe scheduler.

Work:

- deterministic active-goal limits;
- goal priority and pause/resume semantics;
- bounded spawn rate;
- repository-aware policy;
- circuit breakers for repeated blocked/failed goals;
- operator visibility and emergency disable.

This phase should begin only after single-goal rollover and restart recovery are proven in production.
