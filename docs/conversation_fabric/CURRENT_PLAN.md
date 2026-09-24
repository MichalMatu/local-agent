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

### Stage 5 — synthetic Chromium spawn/attach proof — COMPLETE

Implemented and proved in disposable/offline Chromium:

- first-class workflow `reasoning` node admission and `waiting_conversation` state without masking independent runnable work;
- workflow-owned durable `WorkflowConversationStore` and checkpoint/terminal ledger;
- deterministic manual-attach authority and registered-child Bridge adoption with `bootstrapPending=false`;
- durable workflow-owned spawn attempts with globally serialized browser ownership reconstructed after restart;
- narrow `worker_spawn.js` actuator and separate pre-registration `spawn_content.js` protocol;
- deterministic `#la-spawn=<transaction-id>` tab claim with `url`/`pendingUrl` recovery;
- lost-create-ACK recovery without duplicate tab creation;
- MV3 service-worker termination/restart recovery without duplicate bootstrap submission;
- wrong-tab/wrong-route/bootstrap-digest failures closed;
- operator composer edits preserved before the submit boundary;
- ambiguous post-submit state never authorizes an automatic replacement child;
- durable retirement authority issued only after a durable terminal record and `terminal_recorded` lifecycle state;
- browser retirement that can close only the exact registered child conversation URL, never an arbitrary tab id;
- `retired` written only after a validated `closed` or recovery-safe `already_closed` receipt;
- offline Chromium retirement smoke proving unrelated tabs remain untouched.

Hard Stage 5 boundaries preserved:

- no real ChatGPT child creation;
- no production `SPAWN_CHILD`;
- no broader Native Messaging authority;
- no second executor;
- no mutation of `main`, `chat-bridge-state` or `operator-control`;
- Chrome tab id remains cache/routing detail, not durable identity;
- a timeout/worker loss after submission never proves the bootstrap was not accepted.

Evidence:

- exact final PR head `fed2f611ff9b6ef44c08540ece9c798cb64927ea` passed test, coverage, Python 3.14, macOS smoke and Bridge browser smoke;
- final diff review confirmed no live/production spawn or retirement authority was enabled;
- PR #91 merged;
- post-merge `develop/conversation-fabric@217286fb1f2430bf62491e766ef83025a19076a9` passed all five jobs; one macOS smoke attempt exposed an existing timing-observation flake whose own captured output showed the expected late task had started, and a same-SHA rerun passed.

### Stage 6 — campaign/workflow integration — COMPLETE

Implemented and verified:

- restart-safe reasoning-child/workflow reconciliation from exact durable `child_terminal` records;
- recovery when a crash lands after terminal persistence but before child lifecycle or workflow-node persistence, without replaying reasoning work;
- fail-closed detection when workflow success/failure exists without a durable child terminal;
- one durable child request per reasoning workflow node, enforced under the workflow execution lock before browser spawning can begin;
- compact read-only parent ledger containing bounded checkpoint/terminal summaries rather than transcripts;
- exact validated evidence references plus digest-pinned durable terminal record references in the parent projection;
- explicit `child_terminal` context promotion only when the later child request names the exact durable terminal digest;
- causal rejection of child-terminal context recorded after the target request was created;
- bounded selected-context count/serialized size and bounded parent-ledger size;
- negative tests for duplicate child ownership, self-reference, excessive promoted context, wrong digest, future terminal context and missing terminal authority;
- restart/idempotency tests across durable workflow/conversation stores.

Hard Stage 6 boundaries preserved:

- no real ChatGPT child spawning;
- no automatic production Superchat scheduler;
- no production Event Wake/attention integration;
- no second executor or worker pool;
- no whole child transcripts in the parent ledger/context;
- no mutation of `main`, `chat-bridge-state` or `operator-control`;
- browser state remains non-authoritative for workflow success;
- daemon, supervisor, executor and Chat Bridge implementation files remained unchanged by PR #92.

Evidence:

- exact final PR head `e9041a879d10b0d1b698688439b5309618654133` passed test, coverage, Python 3.14, macOS smoke and Bridge browser smoke;
- PR #92 merged to `develop/conversation-fabric` as `6d4e721ffb53dc85a8c4fb6f82632f244f184729`;
- post-merge push CI for `develop/conversation-fabric@6d4e721ffb53dc85a8c4fb6f82632f244f184729` completed successfully.

### Stage 7 — Bridge attention/event routing — IN PROGRESS

Current branch: `work/conversation-attention-routing` from verified `develop/conversation-fabric@6d4e721ffb53dc85a8c4fb6f82632f244f184729`.

Current PR: #93 (draft until the final exact-head and post-merge gates complete).

Implemented on the Stage 7 work branch:

- exact `[LAB:WAIT_TASK=<task-id>]` attention watch for one Local Agent task result;
- persistent `[LAB:WAIT_WORKFLOW=<workflow-id>]` subscription for durable Conversation Fabric child-terminal attention in the exact parent chat;
- bounded persisted task/workflow attention state with binding-epoch ownership and restart recovery;
- typed `child_terminal_ready` envelopes addressed by canonical `parent_conversation_url + workflow_id` and carrying only bounded child/terminal identity;
- explicit opt-in Conversation Fabric event emission through `bridge_event_state_dir`, leaving the default conversation ledger inert;
- child-terminal emission only after durable terminal persistence, terminal lifecycle reconciliation and successful workflow outcome reconciliation;
- the existing read-only Native Messaging host reused for `hello` / `event` / `ack` notification transport only;
- matching events accelerate the existing alarm / `runFeedbackCycle()` path rather than bypassing current delivery, transient, assistant-error or timeout guards;
- task and child-terminal wake prompts explicitly label notifications as hints and require authoritative task/ledger re-read before action;
- persistent workflow watches remain active across multiple child completions;
- repeated identical `WAIT_WORKFLOW` subscriptions are idempotent and do not replay already delivered recent hints;
- exact-parent, wrong-workflow, task-ownership conflict, binding change, restart, transient delivery, outbox failure/retry and duplicate-attention negative coverage.

Hard Stage 7 boundaries preserved:

- no Local Agent daemon, supervisor, executor, repository-lease or worker execution semantics change;
- no real ChatGPT child spawning;
- no production Superchat/workflow scheduler;
- no second executor or worker pool;
- no command/execution authority added to Native Messaging;
- browser/native events remain hints and never prove task/child/workflow success;
- no mutation of `main`, `chat-bridge-state` or `operator-control`;
- Conversation Fabric child-terminal emission remains explicit opt-in rather than silently targeting production state.

Current evidence:

- task-attention intermediate head `9a53cd3b7d430815a3a72e7d19ba5040a393c2d4` passed all five CI jobs;
- exact candidate head before this checkpoint update, `90a7cd4c9e8197f1591d6e1f7f14aacfb6ad5d1d`, passed test, coverage, Python 3.14, macOS smoke and Bridge browser smoke;
- final diff review from Stage 6 baseline showed only Chat Bridge attention/transport, bounded event-envelope, opt-in conversation attention and tests; daemon/supervisor/executor entrypoints are untouched;
- PR #93 has no unresolved review threads.

Stage 7 exit criteria:

- this canonical checkpoint update is included in PR #93;
- final exact PR head passes test, coverage, Python 3.14, macOS smoke and Bridge browser smoke;
- final PR diff confirms the hard Stage 7 boundaries above;
- PR #93 is merged to `develop/conversation-fabric`;
- the same five jobs pass on the post-merge develop SHA.

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

- Stages 1–6 are merged and fully green;
- canonical development baseline for Stage 7 is `develop/conversation-fabric@6d4e721ffb53dc85a8c4fb6f82632f244f184729`;
- Stage 6 durable campaign/workflow ledger and exact child-terminal reconciliation are integrated without changing Local Agent execution semantics;
- operational branches remain untouched.

In progress:

- draft PR #93 on `work/conversation-attention-routing` contains the bounded Stage 7 task/workflow attention implementation;
- exact candidate `90a7cd4c9e8197f1591d6e1f7f14aacfb6ad5d1d` is 5/5 green before this checkpoint-only follow-up;
- the remaining Stage 7 work is final exact-head CI after this documentation update, ready-for-review transition, merge, and post-merge 5/5 verification.

Not yet enabled:

- a bounded real ChatGPT campaign using automatic child spawning;
- a production Superchat scheduler;
- a second Local Agent executor.

## Next action

**Require the final PR #93 head (including this checkpoint) to pass all five CI jobs, perform one final scope review, mark the PR ready, merge it to `develop/conversation-fabric`, and require the same five jobs green on the merge commit. Only then begin Stage 8 with a small bounded live campaign; do not jump directly to the 44-node campaign.**

If a future conversation is unsure what to do next, this `Next action` section is the tie-breaker unless the user explicitly changes the goal.
