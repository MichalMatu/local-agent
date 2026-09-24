# Conversation Fabric

This directory is the canonical entry point for the single development direction on `develop/conversation-fabric`.

Production remains `main`. `chat-bridge-state` and `operator-control` remain operational state/control branches and are not development lines.

## Current state

Stages 1–4 are complete and fully verified. Stage 5 is the current milestone: durable child-conversation storage plus an **offline synthetic Chromium** proof of duplicate-safe spawn/attach/recovery and terminal-gated tab retirement.

Already present on this development line:

- the latest Chat Bridge transient-assistant recovery line;
- the verified Execution Fabric core under `local_agent/workflow/`;
- workflow CLI, shared control-Git lock, fixtures and workflow regression suite;
- durable task-result event outbox and notification-only Native Messaging host substrate;
- pure persisted Event Wake state model and tests;
- current production baseline merged into Conversation Fabric history;
- fail-closed synthetic DEV lab isolated from production state, Chrome and execution authority;
- pure child request/registration/lifecycle/checkpoint/terminal/spawn contracts;
- workflow-owned ConversationStore and durable spawn-attempt ownership for Stage 5;
- isolated browser actuator and synthetic Chromium test path on the Stage 5 work branch.

Production runtime entrypoints remain isolated from Conversation Fabric development packages. Event Wake remains attention transport, not truth.

## Canonical documents

1. `CURRENT_PLAN.md` — current goal, lane split, ordered stages, checkpoint and exact next action. Read this first when resuming work.
2. `UNIFIED_DEVELOPMENT_DIRECTION.md` — architecture, invariants, feasibility and implementation order.
3. `DEV_LAB.md` — isolated synthetic development topology beside production.
4. `BRANCH_CONSOLIDATION.md` — what was transplanted, deliberately omitted and retained as donor history.
5. `history/` — superseded plans/audits/handoffs retained as evidence only.

`CURRENT_PLAN.md` is the execution-order tie-breaker unless the user explicitly changes the goal.

## Current implementation gate

1. **complete:** production `main` housekeeping with no intentional runtime behavior change;
2. **complete:** synchronize Conversation Fabric with current `main`;
3. **complete:** isolated synthetic DEV lab;
4. **complete:** pure bounded child request/registration/lifecycle/spawn/checkpoint/terminal contracts;
5. **current:** prove durable registration/manual attach, duplicate-safe spawn recovery, MV3 restart recovery and terminal-gated retirement in disposable offline Chromium;
6. next connect the verified child lifecycle to the durable parent campaign/workflow ledger;
7. then add bounded Bridge attention routing;
8. only afterward consider a small live slice and later larger acceptance campaign.

Stage 5 must not contact the operator's real ChatGPT session. The browser smoke uses a temporary Chromium profile, forces offline mode and serves a local synthetic fixture. No production `SPAWN_CHILD`, second executor or broader Native Messaging authority is enabled.

## Child identity and retirement invariants

- `ChildRequest` is stable logical intent; browser attempts are separate.
- one admitted request digest resolves to one canonical child conversation URL or fails closed;
- Chrome tab id is routing cache only;
- post-submit uncertainty is ambiguous and never authorizes a replacement child;
- normal Chat Bridge ownership begins only after durable registration/adoption;
- child tab retirement requires a durable terminal record and exact registered child URL;
- unrelated tabs cannot be closed by retirement authority;
- parent reconstruction uses compact durable records, not whole child transcripts.

## 44-node acceptance model

A campaign may contain 44 logical child requests, but v1 must use bounded active child/tab concurrency. It must not open 44 tabs or inject 44 transcripts into the parent.

The parent keeps a compact ledger and finding index. Each child receives only bounded scope plus declared/relevant dependencies and returns a bounded structured terminal record with exact evidence references.

The workflow contract currently bounds a workflow to 64 nodes and direct `depends_on` fan-in to 16. A 44-step campaign therefore must not build one naive 44-way dependency edge; use compact parent synthesis or bounded hierarchical barriers.

Same-repository Local Agent execution remains serialized. Different registered repositories may execute concurrently under the existing scheduler invariants.
