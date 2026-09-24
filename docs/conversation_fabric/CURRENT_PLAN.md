# Conversation Fabric — current goal and execution plan

Status: **canonical execution plan** for the work that starts from stable production `main` and continues on `develop/conversation-fabric`.

This file prevents the development thread from drifting across chats, branches and implementation phases. Read it together with `UNIFIED_DEVELOPMENT_DIRECTION.md` before a new milestone. Update this checkpoint whenever a milestone completes or the user changes the goal.

## Goal

Keep the existing Local Agent production runtime stable and usable while Conversation Fabric / Superchat is developed and tested beside it in an isolated development environment.

The target parent/Superchat can retain a durable campaign goal and compact ledger, create bounded child ChatGPT conversations, assign exact immutable scope/identity, observe compact progress, recover without duplicate work, and retire/close children only after terminal state is durably recorded. Local Agent remains the deterministic executor for exact repository tasks.

## Permanent lane split

### Production — `main`

- installed source of truth at `~/local-agent`;
- production LaunchAgent/state/registry/locks/Chat Bridge/normal Chrome are never development fixtures;
- only narrow fixes/hygiene belong here;
- Conversation Fabric remains disabled until an explicit release gate.

### Integration — `develop/conversation-fabric`

- canonical integration line for completed Conversation Fabric milestones;
- not the installed production runtime;
- periodically synchronized with `main`;
- experimental functionality stays inert from production runtime entrypoints until an explicit integration/release phase.

### Work branches — `work/*`

One bounded milestone at a time. `main` and `develop/conversation-fabric` are not scratch branches.

## Intended local topology

```text
PRODUCTION
~/local-agent
branch: main
normal LaunchAgent
production state / registry / locks
normal Chrome profile + production Chat Bridge

DEVELOPMENT
~/local-agent-dev
branch: develop/conversation-fabric or one current work/* branch
~/Library/Application Support/local-agent-dev
separate state / repositories / browser profile / logs / fixtures
synthetic/disposable repositories until an explicit later gate
```

Development must never consume or mutate production `chat-bridge-state`, `operator-control`, task queues, repository control worktrees or runtime state merely because those resources exist.

A second execution supervisor is not required for the current phases. Stage 3 intentionally keeps executor, remote control, real Chrome profile access and Native Messaging registration disabled in the DEV lab.

## Execution order

### Stage 1 — small `main` housekeeping — COMPLETE

- PR #86 merged;
- production baseline `main@3e3ce9c3e5e8b12b7945a3e07030050b9b1febc6`;
- documentation/release drift corrected without runtime behavior change;
- exact-main test, coverage, Python 3.14, macOS smoke and Bridge browser smoke green.

### Stage 2 — synchronize Conversation Fabric with current `main` — COMPLETE

- isolated sync candidate `93ae995ab32a643c87d6efc65cbadcde3f936574` passed all five CI jobs;
- PR #88 merged with history preserved;
- post-merge `develop/conversation-fabric@fd16bb090451076e2b181b93ac3e216e7e896bb2` again passed all five jobs;
- operational branches `chat-bridge-state` and `operator-control` were untouched.

### Stage 3 — isolated DEV lab/runtime boundary — COMPLETE

- fail-closed synthetic lab with separate checkout/state/repositories/browser/logs/fixtures;
- canonical collision checks including symlink aliases to production paths;
- production Chrome, Native Messaging registration, remote control and executor disabled;
- candidate `35057a1d3366e779295895f22dd28d4cb59be5b3` passed all five CI jobs;
- PR #89 merged;
- post-merge `develop/conversation-fabric@0f7fd7c9cc9deaa1b03639123db7b557e62e8089` passed all five jobs.

### Stage 4 — pure Conversation Fabric contracts — COMPLETE

Implemented inert deterministic contracts for:

- bounded immutable `ChildRequest` and exact workflow/node introduction provenance;
- repository id, canonical `agent_binding`, ref and exact source commit SHA;
- canonical bounded scope/context references;
- immutable/idempotent `ChildRegistration` mapping one request digest to one child URL;
- deterministic bounded bootstrap identity;
- logical child lifecycle with cancellation/abandonment;
- bounded `child_checkpoint` / `child_terminal` records and typed evidence references;
- pure `SpawnTransaction` lifecycle with attempt identity and fail-closed post-submit ambiguity;
- static guard keeping Conversation Fabric out of production runtime entrypoints.

Evidence:

- exact candidate `caee3bf57891a9398416791d37adba66f2dbb579` passed test, coverage, Python 3.14, macOS smoke and Bridge browser smoke;
- PR #90 merged;
- post-merge `develop/conversation-fabric@26f907e82fc8473070dd2bc9f932e0e98dfe30e6` again passed all five jobs.

### Stage 5 — synthetic Chromium spawn/attach proof — IN PROGRESS

Goal: prove duplicate-safe/recoverable child creation and retirement in disposable offline Chromium before any live promotion.

Current branch: `work/chromium-spawn-spike`.
Current PR: #91 (draft while verification is in progress).

Current implementation includes:

- first-class workflow `reasoning` node admission and `waiting_conversation` state;
- workflow-owned durable `WorkflowConversationStore` and checkpoint/terminal ledger;
- deterministic manual-attach authority and registered-child Bridge adoption with `bootstrapPending=false`;
- durable workflow-owned spawn attempts with globally serialized browser ownership reconstructed after restart;
- narrow `worker_spawn.js` actuator and separate pre-registration `spawn_content.js` protocol;
- deterministic `#la-spawn=<transaction-id>` tab claim with `url`/`pendingUrl` recovery;
- offline disposable Chromium proof using a temporary profile, `context.setOffline(true)` and a local synthetic ChatGPT fixture;
- lost-create-ACK recovery without duplicate tab creation;
- MV3 service-worker termination/restart recovery without duplicate bootstrap submission;
- wrong-tab/wrong-route/bootstrap-digest failures closed;
- operator composer edits preserved before the submit boundary;
- ambiguous post-submit state never authorizes an automatic replacement child;
- durable retirement authority issued only after a durable terminal record and `terminal_recorded` lifecycle state;
- browser retirement that can close only the exact registered child conversation URL, never an arbitrary tab id;
- `retired` written only after a validated `closed` or recovery-safe `already_closed` receipt.

Hard Stage 5 boundaries:

- no real ChatGPT child creation;
- no production `SPAWN_CHILD`;
- no broader Native Messaging authority;
- no second executor;
- no mutation of `main`, `chat-bridge-state` or `operator-control`;
- Chrome tab id remains cache/routing detail, not durable identity;
- a timeout/worker loss after submission never proves the bootstrap was not accepted.

Stage 5 exit criteria:

- focused Python/Node tests green, including retirement negatives;
- synthetic Chromium spawn/recovery smoke green in the standard `bridge-browser` profile;
- exact final PR head passes all five CI jobs;
- final diff confirms no live/prod authority was enabled;
- PR #91 merged to `develop/conversation-fabric`;
- all five post-merge develop CI jobs green.

### Stage 6 — campaign/workflow integration

Connect registered reasoning children to the durable parent campaign/workflow ledger while preserving Local Agent repository leases and execution semantics. Add compact parent synthesis, evidence references and bounded context selection.

### Stage 7 — Bridge attention/event routing

Route child/task/workflow attention through current Chat Bridge owners while preserving current transient/assistant-timeout recovery. Events remain hints to reconcile durable truth, never success authority.

### Stage 8 — bounded live slice

Only after prior gates, run a small real campaign. Then consider the larger 44-node acceptance campaign with bounded active child/tab concurrency and measured context/recovery behavior.

### Stage 9 — automatic scheduling only if needed

Only after the complete child lifecycle is stable. Reuse the existing workflow/executor substrate; do not create a second autonomous executor/model loop.

## Non-negotiable safeguards

- ChatGPT plans; Local Agent remains deterministic and model-free.
- PROD and DEV do not accidentally share mutable locks/state/control.
- Browser child creation never grants execution authority.
- Hard repository binding remains authoritative.
- Ambiguous creation/execution fails closed; never blind-replay.
- No uncontrolled tab explosion.
- No whole child transcripts copied into the parent by default.
- Production `main` is never a scratch branch.
- `chat-bridge-state` and `operator-control` remain operational branches, not development lines.

## Current checkpoint — 2026-09-24

Completed:

- Stages 1–4 are merged and fully green;
- canonical development baseline for Stage 5 is `develop/conversation-fabric@26f907e82fc8473070dd2bc9f932e0e98dfe30e6`;
- the old `work/conversation-fabric-phase1-contracts` branch is used only as a verified donor/reference, never merged wholesale;
- `work/chromium-spawn-spike` / PR #91 contains the controlled Stage 5 port plus the new durable retirement gate.

Pending before Stage 5 can be marked complete:

- verify the exact final PR #91 SHA with all five CI jobs;
- review the complete Stage 5 diff and browser authority surface;
- mark PR #91 ready and merge it to `develop/conversation-fabric`;
- verify all five post-merge develop CI jobs.

Not yet enabled:

- real ChatGPT child spawning;
- a production Superchat scheduler;
- a second Local Agent executor.

## Next action

**Finish exact-SHA verification and review of PR #91 (`work/chromium-spawn-spike`). Do not begin a live slice or production child creation before Stage 5 is merged and post-merge CI is green.**

If a future conversation is unsure what to do next, this `Next action` section is the tie-breaker unless the user explicitly changes the goal.
