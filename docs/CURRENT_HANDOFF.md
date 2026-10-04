# Current handoff — Superchat live-acceptance checkpoint

Date: 2026-10-04

Status: Local Agent release line `v4.20.6` / Chat Bridge `0.8.1` is the current production baseline. Queue deduplication is released and live. The final known child-browser readiness repair was merged on `main` as `e4b3da908cfac61bb11cd0e4182b7d9e7c42d5b8` after exact-head CI completed 5/5 green. The next milestone is a bounded live Superchat acceptance on real code, not another design round.

## Source of truth

Do not reconstruct state from old chats. Read fresh repository/runtime evidence in this order:

1. `AGENTS.md`
2. this file
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/conversation_fabric/CHECKPOINT_2026-10-04_SUPERCHAT_READY.md`
6. `docs/conversation_fabric/CURRENT_PLAN.md`
7. `docs/conversation_fabric/NEXT_CHAT_PROMPT.md`

Historical self-diagnostic, DEV-lab and research documents are evidence only; they are not the current execution plan.

## Current baseline

- immutable release tag: `v4.20.6` -> release commit `48eb9d8b6c26a9dfb317906d5099acabce8719c8`;
- final code-readiness patch: `e4b3da908cfac61bb11cd0e4182b7d9e7c42d5b8`;
- current `main`: always read fresh; do not equate a moving branch with the immutable release tag;
- Local Agent version line: `4.20.6`;
- Chat Bridge: `0.8.1`;
- production `daemon_version` and `self_revision`: always verify from fresh daemon status before a live campaign;
- all previously known managed conversation controls were paused at the end of the self-diagnostic;
- `local-agent` itself remains execution-disabled as a task target.

## What the self-diagnostic established

- parent-level scheduler/routing/process ownership is healthy;
- repository execution remains bound to the exact target repository and exact canonical `agent_binding`;
- production parallel workers suppress equivalent queued/recent work before expensive execution;
- children remain reasoning-only and cannot acquire machine authority;
- the child-browser auth probe no longer depends on composer DOM readiness;
- there is no remaining known P0/P1 code blocker for one bounded live Superchat proof.

## Accepted architecture

```text
one Superchat parent
  -> delegates bounded reasoning to child chats
  -> receives child evidence/results
  -> synthesizes one parent decision
  -> if execution is justified, emits one target-repository .agent/tasks request
  -> Local Agent executes deterministically under exact binding/resource controls
```

Chat Bridge is transport/scheduling. Child chats are reasoning workers. Local Agent is the only machine executor. Reasoning repository context is not execution authority.

## Next milestone

Run one live acceptance using a real execution-enabled repository and real source code. The parent must visibly delegate at least two narrow, non-overlapping reasoning jobs, collect their results, make the final decision itself, and—only if justified—queue exactly one bounded executable task in the real target repository. Verify that duplicate execution does not occur.

Conversation Operator intake is an explicit live operational setting. Do not assume it is enabled. Verify it fresh and enable only through the supported bounded path when starting the proof. Keep it disabled at rest unless an active campaign intentionally needs it.

## Deferred, non-blocking hardening

A failed task whose final result is successfully published can currently leave the same bounded recent-completion dedupe receipt as a successful task. That may transiently suppress a corrective task reusing the same explicit `dedupe_key`. Treat this as later hardening; it is not a blocker for the single bounded acceptance, where one intent key must not be reused for a materially changed corrective plan.
