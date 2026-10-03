# Conversation Fabric — current execution plan

Status: the end-to-end MVP and GitHub-backed operator-visible intake are accepted. The current milestone is a controlled production rollout/release decision.

## Current baseline

Production remains unchanged:

- `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`
- Local Agent v4.19.12
- Chat Bridge 0.6.2
- production checkout: `/Users/michal/local-agent`

Canonical Conversation Fabric development:

- branch: `develop/conversation-fabric`
- accepted operator-visible CODE: `37e480d3b36a5c15db89c944ef46f01225a4b379`
- tree: `02910eadc544a87cd9fcb5287abd26e1a05d7688`
- clean exact-SHA CI: `37085317848`, 5/5 green
- underlying accepted MVP CODE: `93494b2a99162eef5bcf44caae087b71459233b4`
- DEV checkout: `/Users/michal/local-agent-dev`

Documentation-only commits may advance the canonical branch. Runtime/effect work must always identify accepted CODE `37e480d...` separately from the current docs head.

## What is complete

Conversation Fabric now has both layers required for the bounded product slice:

1. accepted child lifecycle from durable request through spawn, exact bootstrap identity, registration, observation, terminal evidence, adoption, retirement and exact owned-tab close;
2. accepted GitHub-backed operator boundary using `.agent/conversation/requests/<id>.json` and `.agent/conversation/results/<id>.json`.

The operator adapter calls the accepted `run_mvp_campaign()` rather than duplicating lifecycle semantics. `.agent/tasks` remains a separate executable repository-work contract. No MCP control path, second scheduler or alternate durable authority was added.

## Operator intake safety

- one to four bounded children per request;
- immutable canonical request digest and same-ID conflict rejection;
- local durable spool before result publication;
- default-disabled supervisor integration requiring explicit runtime configuration;
- long browser work outside repository/resource leases;
- inherited lease descriptors stripped before campaign spawn;
- active campaign blocks full control/self-update service;
- disable preserves staged recovery authority;
- error-bearing terminal children map to failed rather than permanent waiting;
- request identity is rechecked after pull/rebase before publication push;
- every spool deletion requires fresh origin fetch and exact request/result proof;
- disabled `--once` performs publication-only flush without staging new work or running normal control/self-update.

## Acceptance evidence

- final focused gate: compile + Ruff + 121 tests + 6 package-layout tests passed;
- final review: `OPERATOR_FINAL_FRESH_ORIGIN_OK`;
- clean CI: `37085317848`, all five jobs passed;
- clean live request: `operator-clean-final-request-20261003-v1`;
- clean live child: `https://chatgpt.com/c/6ac057fc-b140-83ed-b74f-61f1b8de94d7`;
- clean live result: `OPERATOR_CLEAN_FINAL_OK 37e480d3b36a5c15db89c944ef46f01225a4b379`;
- production stayed unchanged.

## Permanent architecture boundaries

- GitHub is the durable control/evidence plane.
- Local Agent is deterministic/model-free orchestration.
- ChatGPT conversations are the reasoning layer.
- Chat Bridge is a bounded browser transport/actuator, not durable workflow authority.
- Browser DOM state is transport evidence, not scheduler state.
- Child chats have no independent machine execution authority.
- No direct OpenAI API model loop for Conversation Fabric.
- No MCP or Native Messaging control plane for this architecture.
- No production Chrome-profile mutation.

## Current product milestone: controlled release decision

Do not add another operator-intake layer. The next work should decide whether and how to ship accepted CODE `37e480d...` to production.

Preferred sequence:

1. refresh production/main and release/version/changelog state;
2. define the exact production configuration for the default-disabled operator runtime and its rollback path;
3. decide whether the release contains only Local Agent code or also requires Chat Bridge/runtime desired-state changes;
4. prepare a bounded release candidate and exact-SHA CI;
5. require an explicit user release decision before mutating production;
6. install code while intake remains disabled, verify health, then enable only the intended operator configuration;
7. record post-release evidence and rollback checkpoint.

Broad fleet scheduling, rollover and large fan-out remain later product work.

For operational continuation, use `docs/CURRENT_HANDOFF.md`. A ready-to-paste continuation prompt is maintained in `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`.
