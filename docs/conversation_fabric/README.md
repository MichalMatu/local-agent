# Conversation Fabric

This directory is the canonical entry point for the single development direction on `develop/conversation-fabric`.

Production remains `main`. `chat-bridge-state` and `operator-control` remain operational state/control branches and are not development lines.

## Current state

The consolidation phase is complete.

Already present on this branch:

- the latest Chat Bridge transient-assistant recovery line;
- the verified Execution Fabric core under `local_agent/workflow/`;
- the workflow CLI, shared control-Git lock, fixtures and full workflow regression suite;
- the durable task-result event outbox and notification-only Native Messaging host;
- the pure persisted Event Wake state model and tests;
- CI for `develop/**`.

Execution Fabric is intentionally inert with respect to production runtime entrypoints. Event Wake is also intentionally only partially active: its pure state/outbox/native-host substrate is present, but old donor worker/delivery files are not wired over the newer transient recovery path.

## Canonical documents

1. `UNIFIED_DEVELOPMENT_DIRECTION.md` — current architecture, invariants, technical feasibility and implementation order. This is the source of truth for new work.
2. `BRANCH_CONSOLIDATION.md` — what was transplanted, what was deliberately not transplanted, and where donor history is retained.
3. `history/` — superseded design plans, audits and handoffs retained as evidence/reference only. They may mention deleted branches and must not be treated as current instructions.

## Next implementation gate

The next product work is deliberately narrow:

1. pure bounded `ChildRequest`, `ChildRegistration`, lifecycle, checkpoint and terminal-result contracts;
2. then a synthetic Chromium spawn/attach feasibility spike proving exactly-once child creation/recovery;
3. only after that, connect child conversations to the already-transplanted workflow substrate and attention-event transport.

Do not enable a production `SPAWN_CHILD`, automatic workflow scheduler, or broader Native Messaging authority before those gates pass.

## 44-node acceptance model

A campaign may contain 44 logical child requests, but v1 must use bounded active child concurrency. It must not open 44 tabs or inject 44 transcripts into the parent.

The parent keeps a compact ledger and global finding index. Each child receives only its bounded scope plus declared/relevant dependencies and returns a bounded structured terminal record with exact evidence references.

The transplanted workflow contract currently bounds a workflow to 64 nodes and direct `depends_on` fan-in to 16. A 44-step campaign therefore must not build one naive 44-way dependency edge. Use the parent ledger for campaign-wide synthesis or bounded hierarchical barriers. Keep the verified fan-in bound unless profiling or a concrete workflow requirement justifies changing it.

Same-repository Local Agent execution remains serialized. Different registered repositories may execute concurrently under the existing scheduler invariants.
