# Conversation Fabric

This directory is the canonical entry point for the active Conversation Fabric development direction.

Production remains `main`. `chat-bridge-state` and `operator-control` remain operational state/control branches and are not development lines.

The single canonical Conversation Fabric development branch is `develop/conversation-fabric`. The former `work/conversation-live-slice` branch was a bounded Stage 8 work branch and is superseded by this canonical line. Historical exact branch/revision references in milestone evidence remain evidence only and do not define current branch authority.

## Current target invariant

The current target architecture is intentionally single-path:

```text
ordinary ChatGPT Superchat
  -> GitHub-backed control/evidence
  -> Local Agent
  -> host-ops / narrow ChatGPT Browser Driver
  -> GitHub-backed result/evidence
  -> Superchat
```

GitHub-backed Local Agent contracts are the only authoritative control/evidence plane between ChatGPT reasoning and Local Agent execution.

The target architecture does **not** include an MCP server, a direct OpenAI API reasoning loop inside Local Agent, or any parallel second control transport. Historical documents may mention those ideas; they are not current options or planned fallback paths unless the user explicitly changes the canonical architecture.

## Current state

Stages 1–7 are complete and verified. Stage 8 is the current milestone: prove one bounded real child-conversation live slice in the isolated DEV browser/runtime environment without granting Local Agent execution authority or touching production browser/runtime state.

Already present on this development line:

- the latest Chat Bridge transient-assistant recovery line;
- the verified Execution Fabric core under `local_agent/workflow/`;
- workflow CLI, shared control-Git lock, fixtures and workflow regression suite;
- durable task-result event outbox and notification-only Native Messaging host substrate;
- persisted Event Wake state and exact task/workflow attention routing;
- current production baselines merged through the Conversation Fabric development history;
- fail-closed synthetic DEV lab isolated from production state, Chrome and execution authority;
- pure child request/registration/lifecycle/checkpoint/terminal/spawn contracts;
- workflow-owned conversation state, durable spawn-attempt ownership and restart-safe campaign reconciliation;
- verified disposable/offline Chromium spawn, attach, restart-recovery and terminal-gated retirement proof;
- bounded parent campaign ledger, exact evidence references and explicit digest-pinned child-context promotion;
- Stage 8 one-child live planning, one-shot arming, isolated browser actuator, durable create/recovery journal and guided operator flow.

Production runtime entrypoints remain isolated from Conversation Fabric development packages. Browser/native events are attention transport, not workflow truth.

## Canonical documents

1. `TARGET_PRODUCT_ARCHITECTURE.md` — canonical end-state architecture and hard invariants. Read this first for ownership and control-plane decisions.
2. `CURRENT_PLAN.md` — current goal, ordered stages, checkpoint and exact next action. Read this for implementation state.
3. `UNIFIED_DEVELOPMENT_DIRECTION.md` — stable historical path that now points back to the canonical target and restates its hard invariants.
4. `DEV_LAB.md` — isolated synthetic development topology beside production.
5. `BRANCH_CONSOLIDATION.md` — what was transplanted, deliberately omitted and retained as donor history.
6. `history/` — superseded plans/audits/handoffs retained as evidence only.

`CURRENT_PLAN.md` is the execution-order tie-breaker unless the user explicitly changes the goal. `TARGET_PRODUCT_ARCHITECTURE.md` is the architecture/ownership tie-breaker. Branch identity has one authority: active Conversation Fabric development is on `develop/conversation-fabric` until an explicit integration/release decision moves it elsewhere. Temporary `work/*` branches are disposable milestone/candidate branches and must not become a second long-lived development source of truth.

## Current implementation gate

1. **complete:** production `main` housekeeping with no intentional runtime behavior change;
2. **complete:** synchronize Conversation Fabric with the then-current production baseline;
3. **complete:** isolated synthetic DEV lab;
4. **complete:** pure bounded child request/registration/lifecycle/spawn/checkpoint/terminal contracts;
5. **complete:** durable registration/manual attach, duplicate-safe spawn recovery, MV3 restart recovery and terminal-gated retirement in disposable offline Chromium;
6. **complete:** bind reasoning-child lifecycle to the durable parent campaign/workflow ledger with restart-safe reconciliation, exact evidence refs and bounded explicit context promotion;
7. **complete:** bounded Bridge task/workflow attention and child-terminal event routing while preserving durable-authority boundaries;
8. **current:** bounded one-child live slice in the isolated DEV browser profile, with exact durable plan identity, one-shot arming, fail-closed recovery and no Local Agent execution authority.

Stage 8 does not enable a production Superchat scheduler, a second executor, production `SPAWN_CHILD`, production Chrome-profile mutation or automatic replacement after ambiguous browser state.

## Campaign ledger and context invariants

- one workflow reasoning node may own only one durable child request;
- workflow success/failure may be reconciled from an exact durable child terminal record, never from browser state or a model assertion alone;
- crash windows between terminal persistence, child lifecycle update and workflow-node update are restart-reconciled without replaying reasoning work;
- the parent ledger contains bounded checkpoint/terminal summaries and exact validated evidence references, not child transcripts;
- reusable child context is promoted only through explicit digest-pinned durable record references;
- context selection is bounded by record count and serialized size and rejects self/future/digest-mismatched terminal references;
- existing Local Agent repository leases and task execution paths are not bypassed or duplicated.

## Child identity and retirement invariants

- `ChildRequest` is stable logical intent; browser attempts are separate;
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
