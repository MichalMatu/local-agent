# Conversation Fabric — current goal and execution plan

Status: **canonical execution plan** for the work that starts from stable production `main` and continues on `develop/conversation-fabric`.

This file exists to prevent the development thread from drifting across chats, branches and implementation phases. Before starting a new Conversation Fabric milestone, re-read this file together with `UNIFIED_DEVELOPMENT_DIRECTION.md`. Update the checkpoint here whenever a milestone is completed or the plan is deliberately changed.

## Goal

Keep the existing Local Agent production runtime stable and usable while Conversation Fabric / Superchat is developed and tested beside it in an isolated development environment.

The target product is a higher-level supervisor in which a parent/Superchat can:

- retain a durable campaign goal and compact work ledger;
- create bounded child ChatGPT conversations when needed;
- assign each child an exact scope and immutable identity;
- observe progress without importing whole child transcripts into the parent;
- detect completion, failure, ambiguity or a stuck child;
- recover safely without duplicating work;
- retire/close child conversations only after terminal state is durably recorded;
- use Local Agent only as the deterministic executor for exact repository tasks.

The user must be able to keep using the normal production Local Agent while development and testing happen separately.

## Permanent lane split

### Production — `main`

- source of truth for the installed runtime;
- installed checkout stays `~/local-agent`;
- production LaunchAgent/state/registry/locks/Chat Bridge/normal Chrome profile are not development fixtures;
- only narrow bug fixes, release hygiene and documentation/contract corrections belong here;
- Conversation Fabric remains disabled until an explicit release gate.

### Integration — `develop/conversation-fabric`

- canonical integration line for completed Conversation Fabric milestones;
- not the installed production runtime;
- periodically synchronized with current `main`;
- experimental functionality remains inert with respect to production entrypoints.

### Work branches — `work/*`

One bounded milestone at a time. Examples:

- `work/main-housekeeping` from `main`;
- `work/conversation-fabric-main-sync` from `develop/conversation-fabric`;
- `work/dev-runtime-isolation`;
- `work/conversation-child-contracts`;
- `work/chromium-spawn-spike`.

Do not use `main` or `develop/conversation-fabric` as scratch branches.

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
separate development state
separate locks where runtime components need them
separate logs
separate Chrome/synthetic browser profile
separate Chat Bridge/native-host configuration where needed
disposable/synthetic control repositories until an explicit later gate
```

Development must never consume or mutate production `chat-bridge-state`, `operator-control`, task queues, repository control worktrees or runtime state merely because those resources already exist.

A full second execution supervisor is **not required initially**. The first isolated development lab should contain only what the current milestone needs: development checkout, tests, disposable workflow/control fixtures and separate browser/Chat Bridge state. Add an explicitly namespaced DEV executor only if a later integration phase genuinely requires it.

## Execution order

### Stage 1 — small `main` housekeeping — COMPLETE

Goal: freeze a clean production baseline without changing runtime behavior.

Completed:

- corrected current operational documentation drift;
- reconciled stale BUG-002 candidate wording with established production behavior;
- clarified renamed repository identities versus preserved physical workspace paths;
- strengthened deterministic documentation-drift tests;
- recorded missing historical release-tag metadata without fabricating/back-dating a tag;
- kept BUG-001 and all runtime behavior out of the change.

Evidence:

- PR #86 was reviewed and squash-merged;
- production baseline is `main@3e3ce9c3e5e8b12b7945a3e07030050b9b1febc6`;
- exact-main CI passed test, coverage, Python 3.14, macOS smoke and Bridge browser smoke;
- no runtime source file changed in the housekeeping PR.

### Stage 2 — synchronize Conversation Fabric with current `main` — IN PROGRESS

Goal: development starts from current production reality rather than a stale production snapshot.

Method:

1. compare `develop/conversation-fabric` with current `main`;
2. merge `main` first into isolated `work/conversation-fabric-main-sync`;
3. reconcile integration documentation and naming there;
4. run the complete combined verification suite;
5. only then merge the sync branch into `develop/conversation-fabric`.

Current evidence:

- before synchronization, develop was 55 commits ahead and 9 commits behind `main`, with merge base `474000b5d4b015958fe92be491968dc4625b4a84`;
- the 9 production commits consist of repository-identity renames plus Stage 1 housekeeping;
- PR #87 cleanly merged `main@3e3ce9c3e5e8b12b7945a3e07030050b9b1febc6` into the isolated sync branch;
- operational branches `chat-bridge-state` and `operator-control` remain untouched;
- canonical Conversation Fabric architecture now names the synchronized production baseline explicitly.

Stage 2 exit criteria:

- combined sync branch CI green on its exact final SHA;
- Conversation Fabric/workflow/Bridge tests remain green;
- `develop/conversation-fabric` contains current production fixes/contracts;
- no production branch or operational-state branch is changed by the develop synchronization itself.

### Stage 3 — isolated DEV lab/runtime boundary

Goal: allow Conversation Fabric and browser experiments to run beside production without disturbing it.

Start with the smallest useful isolation boundary:

- separate checkout/worktree (`~/local-agent-dev` target topology);
- separate temporary state roots and test repositories;
- separate browser/synthetic Chromium profile;
- separate Chat Bridge test configuration;
- explicit prohibition on production control/state branches;
- tests proving DEV paths cannot resolve to production paths.

Only if later phases need a real second executor, extend the design to an explicit instance namespace covering daemon lock, state, registry, logs, LaunchAgent label, Native Messaging host/config and control-plane identities.

Exit criteria:

- DEV tests/browser fixture can be started, stopped and destroyed without changing PROD state;
- paths/locks/control identities cannot accidentally collide with production;
- normal production Local Agent remains available while DEV work proceeds.

### Stage 4 — pure Conversation Fabric contracts

Implement bounded deterministic contracts for:

- `ChildRequest`;
- `ChildRegistration`;
- logical child lifecycle;
- spawn transaction lifecycle;
- `child_checkpoint`;
- `child_terminal`.

Require strong positive and negative tests. No production Chrome side effects.

### Stage 5 — synthetic Chromium spawn/attach proof

Prove exactly-once/recoverable child creation in a disposable synthetic ChatGPT fixture, including:

- fresh child bootstrap;
- exact request -> exact conversation registration;
- uncertain first-send recovery;
- MV3/service-worker restart;
- duplicate prevention;
- manual attach fallback;
- bounded tab concurrency;
- safe retirement/close only after durable terminal state.

No production `SPAWN_CHILD` yet.

### Stage 6 — campaign/workflow integration

Connect registered reasoning children to durable campaign/workflow nodes while preserving Local Agent repository leases and execution semantics. Add compact parent ledger, evidence references and bounded context selection.

### Stage 7 — Bridge attention/event routing

Integrate child/task/workflow attention into current Chat Bridge owners while preserving current transient/assistant-timeout recovery. Events remain hints to reconcile durable state, never success authority.

### Stage 8 — bounded live slice

Run a small real campaign first. Only then run a larger acceptance campaign such as the 44-node audit. Measure context growth, duplicate prevention, stuck-child recovery, tab bounds, integration/rework rate, Local Agent interaction and terminal-result quality.

### Stage 9 — automatic scheduling only if needed

Only after the complete child lifecycle is stable. Reuse the existing workflow/executor substrate; do not create a second autonomous executor/model loop.

## Non-negotiable safeguards

- ChatGPT plans; Local Agent remains deterministic and model-free.
- PROD and DEV do not share mutable locks/state/control by accident.
- Browser child creation never grants execution authority.
- Hard binding remains authoritative.
- Ambiguous creation or execution fails closed; never blind-replay.
- No uncontrolled tab explosion.
- No whole child transcripts copied into the parent by default.
- Production `main` is never a scratch development branch.
- BUG-001 and other runtime defects get their own scoped repair/release path.
- `chat-bridge-state` and `operator-control` are operational branches, not development integration branches.

## Current checkpoint — 2026-09-24

Completed:

- Stage 1 production housekeeping is merged and fully green on `main@3e3ce9c3e5e8b12b7945a3e07030050b9b1febc6`;
- Stage 2 divergence was audited;
- current `main` was cleanly merged into `work/conversation-fabric-main-sync`;
- stale production-baseline wording in the canonical architecture was updated.

Pending before Stage 2 can be marked complete:

- verify the exact final sync-branch SHA with the full branch CI;
- review the final integration diff;
- merge the verified sync branch into `develop/conversation-fabric`;
- verify develop head/CI after merge.

Not yet started:

- isolated DEV lab/runtime boundary;
- pure reasoning-child contracts;
- automatic child creation.

## Next action

**Finish Stage 2 verification and merge the synchronized branch into `develop/conversation-fabric`. Then start Stage 3 on a fresh `work/dev-runtime-isolation` branch.**

If a future conversation is unsure what to do next, this `Next action` section is the tie-breaker unless the user explicitly changes the goal.
