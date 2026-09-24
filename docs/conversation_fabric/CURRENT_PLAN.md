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
separate logs
separate Chrome/synthetic browser profile
disposable/synthetic repositories until an explicit later gate
```

Development must never consume or mutate production `chat-bridge-state`, `operator-control`, task queues, repository control worktrees or runtime state merely because those resources already exist.

A full second execution supervisor is **not required initially**. Stage 3 establishes a synthetic-only lab and keeps executor, remote control, real Chrome profile access and Native Messaging registration disabled. Add an explicitly namespaced DEV executor only if a later integration phase genuinely requires it.

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

### Stage 2 — synchronize Conversation Fabric with current `main` — COMPLETE

Goal: development starts from current production reality rather than a stale production snapshot.

Completed:

1. audited divergence between current production and Conversation Fabric;
2. merged `main` first into isolated `work/conversation-fabric-main-sync`;
3. reconciled integration documentation and naming there;
4. verified the exact sync candidate `93ae995ab32a643c87d6efc65cbadcde3f936574` with all five CI jobs;
5. merged PR #88 into `develop/conversation-fabric` with history preserved;
6. verified `develop/conversation-fabric@fd16bb090451076e2b181b93ac3e216e7e896bb2` is `behind_by=0` from current `main`;
7. verified all five post-merge develop CI jobs again, including macOS smoke and Bridge browser smoke.

Operational branches `chat-bridge-state` and `operator-control` were not touched.

### Stage 3 — isolated DEV lab/runtime boundary — IN PROGRESS

Goal: allow Conversation Fabric and browser experiments to run beside production without disturbing it.

Implementation direction:

- separate checkout target `~/local-agent-dev`;
- separate synthetic lab root `~/Library/Application Support/local-agent-dev`;
- separate state/repository/browser/log/fixture directories;
- explicit collision checks against production checkout/state/workspaces/LaunchAgent/logs/Chrome/native-host paths;
- canonical path resolution so symlink aliases to PROD are rejected;
- explicit protected operational branches: `chat-bridge-state`, `operator-control`;
- executor, remote control, normal Chrome profile and Native Messaging registration disabled in the Stage 3 manifest;
- production runtime entrypoints forbidden from importing the development package;
- existing offline disposable Chromium smoke remains the browser model.

A second Local Agent executor is deliberately out of scope. Current production mutable paths are still owned in several runtime modules, so full instance namespacing would be a broader runtime refactor than the current Conversation Fabric phases require.

Exit criteria:

- DEV layout/collision checks deterministic and fully tested;
- initialization idempotent and refuses ambiguous pre-existing state;
- tests prove DEV cannot resolve to protected PROD paths, including symlink aliases;
- production runtime entrypoints do not import the DEV package;
- synthetic browser path remains independent of normal Chrome;
- exact Stage 3 candidate CI green;
- verified Stage 3 PR merged to `develop/conversation-fabric` without touching `main`, `chat-bridge-state` or `operator-control`.

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
- Stage 2 is merged and fully green on `develop/conversation-fabric@fd16bb090451076e2b181b93ac3e216e7e896bb2`;
- current `main` is fully contained in develop (`behind_by=0`);
- Stage 3 preimplementation audit identified that a second executor would require a broad namespace refactor and is not needed yet;
- `work/dev-runtime-isolation` is the active milestone branch;
- initial Stage 3 code now defines a fail-closed synthetic lab, collision tests, inert-boundary tests and `DEV_LAB.md`.

Pending before Stage 3 can be marked complete:

- review/fix the Stage 3 implementation against its focused tests;
- run full exact-SHA CI;
- inspect the complete `develop...work/dev-runtime-isolation` diff;
- merge the verified Stage 3 PR into develop;
- verify develop CI after merge.

Not yet started:

- pure reasoning-child contracts;
- automatic child creation.

## Next action

**Finish and verify `work/dev-runtime-isolation`. Do not start ChildRequest/ChildRegistration work until Stage 3 is merged and green.**

If a future conversation is unsure what to do next, this `Next action` section is the tie-breaker unless the user explicitly changes the goal.
