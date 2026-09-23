# Superchat supervisor

This directory is the working design area for the higher-level ChatGPT supervisor that sits above Chat Bridge.

Superchat is not a replacement for Local Agent and must not become another executor. Its purpose is to supervise long-running planner conversations, preserve goal continuity across ChatGPT conversation boundaries, start and retire worker chats, and coordinate progress using deterministic lifecycle rules.

```text
Superchat planner / manager
        |
        v
Deterministic Chat Supervisor
        |
        v
Chat Bridge
        |
        v
Bound ChatGPT worker conversations
        |
        v
Git-backed control state
        |
        v
Deterministic Local Agent executor
```

## Documents

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — target boundaries, state model, protocols and safety invariants.
- [`ROADMAP.md`](ROADMAP.md) — staged delivery plan from documentation and fixtures to automatic rollover and multi-goal supervision.
- [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) — concrete expected code changes, tests and migration order.
- [`RESEARCH_LOG.md`](RESEARCH_LOG.md) — observed facts, unknowns, experiments and decisions that still need evidence.
- [`EVIDENCE.md`](EVIDENCE.md) — concrete browser/DOM artifacts already captured and evidence still needed for automatic rollover.
- [`../CHATGPT_DOM_CONTRACT.md`](../CHATGPT_DOM_CONTRACT.md) — canonical observed ChatGPT DOM contract for conversation exhaustion.
- [`../AUTONOMOUS_CHAT_LOOP.md`](../AUTONOMOUS_CHAT_LOOP.md) — current child planner / deterministic executor contract.

## Current status

The repository already has a deterministic terminal exhaustion detector:

- `chat_bridge/dom_contract.js` recognizes the observed maximum-length DOM;
- `chat_bridge/exhaustion_guard.js` reports exhaustion to the extension service worker;
- `chat_bridge/worker_transport.js` records `conversation_exhausted`, disables that conversation and clears its alarm;
- the old conversation remains immutable and hard-bound to its repository.

What does not exist yet:

- durable goal identity independent from one chat;
- a privileged but bounded Superchat control protocol;
- automatic creation and binding of a replacement ChatGPT conversation;
- durable rollover operation journaling and restart reconciliation;
- periodic goal checkpoints usable when the old chat reaches a hard terminal limit;
- fleet/goal summaries for a supervisor conversation;
- multi-goal scheduling policy above Chat Bridge.

## Design principle

The LLM decides **what** should happen. Deterministic infrastructure decides **how lifecycle transitions happen safely**.

Superchat may request that a child planner continue, pause, rotate or start a new goal. It must never infer repository identity from prose, rewrite an existing chat binding, bypass Local Agent task admission, or treat an LLM summary as execution evidence.
