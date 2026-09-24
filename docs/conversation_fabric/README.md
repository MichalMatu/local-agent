# Conversation Fabric

This directory is the canonical entry point for the single development direction on `develop/conversation-fabric`.

Production remains `main`. `chat-bridge-state` and `operator-control` remain operational state/control branches and are not development lines.

## Current state

The consolidation phase is complete. Stage 1 production housekeeping and Stage 2 synchronization with current `main` are complete. Stage 3 establishes the isolated synthetic DEV lab before any child-conversation implementation begins.

Already present on this development line:

- the latest Chat Bridge transient-assistant recovery line;
- the verified Execution Fabric core under `local_agent/workflow/`;
- the workflow CLI, shared control-Git lock, fixtures and full workflow regression suite;
- the durable task-result event outbox and notification-only Native Messaging host substrate;
- the pure persisted Event Wake state model and tests;
- CI for `develop/**`;
- the current production baseline merged into Conversation Fabric history.

Execution Fabric is intentionally inert with respect to production runtime entrypoints. Event Wake is also intentionally only partially active: its pure state/outbox/native-host substrate is present, but old donor worker/delivery files are not wired over the newer transient recovery path.

## Canonical documents

1. `CURRENT_PLAN.md` — current goal, production/development lane split, ordered execution plan, checkpoint and exact next action. Read this first when resuming work.
2. `UNIFIED_DEVELOPMENT_DIRECTION.md` — current architecture, invariants, technical feasibility and implementation order for Conversation Fabric itself.
3. `DEV_LAB.md` — Stage 3 isolation boundary and safe synthetic development topology beside production.
4. `BRANCH_CONSOLIDATION.md` — what was transplanted, what was deliberately not transplanted, and where donor history is retained.
5. `history/` — superseded design plans, audits and handoffs retained as evidence/reference only. They may mention deleted branches and must not be treated as current instructions.

`CURRENT_PLAN.md` is the tie-breaker for execution order unless the user explicitly changes the goal. Update its `Current checkpoint` and `Next action` when a milestone completes so future chats do not reconstruct the plan from memory.

## Next implementation gate

The prerequisites are intentionally serial at the product boundary even though verification work can overlap:

1. **complete:** small production-`main` housekeeping with no intentional runtime behavior change;
2. **complete:** reconcile `develop/conversation-fabric` with the resulting current `main`;
3. **current:** establish the isolated synthetic DEV checkout/state/browser lab described in `DEV_LAB.md`;
4. then implement the pure bounded `ChildRequest`, `ChildRegistration`, lifecycle, checkpoint and terminal-result contracts;
5. then run the synthetic Chromium spawn/attach feasibility spike proving duplicate-safe child creation/recovery;
6. only after those gates, connect child conversations to the already-transplanted workflow substrate and attention-event transport.

Do not enable a production `SPAWN_CHILD`, automatic workflow scheduler, second executor instance, or broader Native Messaging authority before the relevant gates pass.

## 44-node acceptance model

A campaign may contain 44 logical child requests, but v1 must use bounded active child concurrency. It must not open 44 tabs or inject 44 transcripts into the parent.

The parent keeps a compact ledger and global finding index. Each child receives only its bounded scope plus declared/relevant dependencies and returns a bounded structured terminal record with exact evidence references.

The transplanted workflow contract currently bounds a workflow to 64 nodes and direct `depends_on` fan-in to 16. A 44-step campaign therefore must not build one naive 44-way dependency edge. Use the parent ledger for campaign-wide synthesis or bounded hierarchical barriers. Keep the verified fan-in bound unless profiling or a concrete workflow requirement justifies changing it.

Same-repository Local Agent execution remains serialized. Different registered repositories may execute concurrently under the existing scheduler invariants.
