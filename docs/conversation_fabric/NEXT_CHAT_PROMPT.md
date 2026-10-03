# Conversation Fabric continuation prompt

Use this prompt to start the next ChatGPT conversation. Repository state, durable documentation and fresh `host-ops` state are authoritative; do not rely on previous chat memory.

---

Continue Conversation Fabric in repository `MichalMatu/local-agent`.

Do not rely on memory from the previous chat. Repository state, durable docs and fresh `host-ops` state are the source of truth.

Read first:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/conversation_fabric/CURRENT_PLAN.md`
4. `docs/DEVELOPMENT_PLAN.md`
5. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`
6. `docs/OPERATIONS.md`

Then refresh and verify `main`, `develop/conversation-fabric`, `host-ops:agent-control`, daemon state, `/Users/michal/local-agent-dev`, and `/Users/michal/local-agent`.

Production baseline is still `main@979ef080ddb69d6e18aaf81510e3175bac2f33d2`, Local Agent 4.19.12 / Chat Bridge 0.6.2. Production and the production Chrome profile must remain untouched unless the user makes a separate explicit release decision.

Accepted Conversation Fabric CODE is now:

- `37e480d3b36a5c15db89c944ef46f01225a4b379`
- commit `Add operator-visible Conversation Fabric intake`
- tree `02910eadc544a87cd9fcb5287abd26e1a05d7688`
- clean exact-SHA CI `37085317848`, 5/5 green
- underlying accepted end-to-end MVP `93494b2a99162eef5bcf44caae087b71459233b4`

The operator-visible slice is COMPLETE. Do not rebuild it. The accepted durable boundary is:

```text
Superchat / Operator Chat
  -> .agent/conversation/requests/<id>.json
  -> optional/default-disabled supervisor intake
  -> existing run_mvp_campaign() child lifecycle
  -> .agent/conversation/results/<id>.json
  -> Superchat synthesis
```

`.agent/tasks` remains the executable repository-work contract and was not repurposed. No MCP control plane or second scheduler was introduced. Long child campaigns run outside repository/resource leases. Result publication is restart-safe and fail-closed: request identity is rechecked after pull/rebase, and local result spool is deleted only after a fresh origin fetch proves both the exact request and exact result.

Final clean live proof:

- request `operator-clean-final-request-20261003-v1`
- workflow `operator-clean-final-workflow-20261003-v1`
- child `https://chatgpt.com/c/6ac057fc-b140-83ed-b74f-61f1b8de94d7`
- result `OPERATOR_CLEAN_FINAL_OK 37e480d3b36a5c15db89c944ef46f01225a4b379`
- operator state `completed`, 1/1 child completed, failures 0
- production unchanged

Documentation-only commits may advance `develop/conversation-fabric` beyond accepted CODE. Always distinguish accepted CODE `37e480d...` from the current docs head.

Current priority is a controlled production rollout/release decision. Start with a read-only release audit: current version/changelog/tag/release procedure, exact production delta from accepted CODE, whether Chat Bridge/runtime desired-state changes are required, exact default-disabled Conversation Fabric runtime configuration, rollback path, and the smallest safe release sequence.

Do not mutate production until the user explicitly approves release. If release is selected, prepare a bounded release candidate, exact-SHA CI and rollback evidence first; install code with Conversation Fabric operator intake still disabled, verify health, and only then enable the intended operator configuration deliberately.

Do not start another abstract lifecycle/intake hardening milestone unless real use exposes a concrete defect. Broad fleet scheduling, rollover and large fan-out remain out of scope.
