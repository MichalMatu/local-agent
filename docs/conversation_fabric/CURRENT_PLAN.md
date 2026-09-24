# Conversation Fabric — current goal and execution plan

Status: **canonical execution plan** for the work that starts from stable production `main` and continues on `develop/conversation-fabric`.

This file exists to prevent the development thread from drifting across chats, branches and implementation phases. Before starting a new Conversation Fabric milestone, re-read this file together with `UNIFIED_DEVELOPMENT_DIRECTION.md`. Update the checkpoint here when a milestone is completed or the plan is deliberately changed.

## Goal

Keep the existing Local Agent production runtime stable and usable while Conversation Fabric / Superchat is developed and tested beside it in an isolated development environment.

The target product is a higher-level supervisor in which a parent/Superchat can:

- retain a durable campaign goal and compact work ledger;
- create bounded child ChatGPT conversations when needed;
- assign each child an exact scope and immutable identity;
- observe child progress without importing whole transcripts into the parent;
- detect terminal completion, failure, ambiguity or a stuck child;
- recover or request bounded manual intervention without duplicating work;
- retire/close child conversations when their work is durably recorded;
- use Local Agent only as the deterministic executor for exact repository tasks.

The user must be able to keep using the normal production Local Agent while this development and testing happens separately.

## Permanent lane split

### Production lane — `main`

Purpose: stable Local Agent used for normal work.

Rules:

- `main` is production source of truth;
- installed production checkout remains `~/local-agent`;
- existing production LaunchAgent, state, registry, locks, Chat Bridge and normal Chrome profile remain untouched by development experiments;
- only narrow bug fixes, release hygiene and documentation/contract corrections belong here;
- no Conversation Fabric feature is enabled on production before its explicit release gate.

### Integration lane — `develop/conversation-fabric`

Purpose: canonical integration line for Conversation Fabric / Superchat.

Rules:

- completed development milestones accumulate here;
- this branch is not the installed production runtime;
- it must periodically incorporate current `main` before new integration work proceeds;
- experimental functionality remains inert with respect to production entrypoints until its release gate passes.

### Work branches — `work/*`

Purpose: one bounded implementation milestone at a time.

Examples:

- `work/main-housekeeping` from `main`;
- `work/conversation-fabric-main-sync` from `develop/conversation-fabric` when reconciliation needs isolated review;
- `work/dev-runtime-isolation` from `develop/conversation-fabric`;
- `work/conversation-child-contracts`;
- `work/chromium-spawn-spike`.

Do not turn `develop/conversation-fabric` into a scratch branch and do not perform substantial Conversation Fabric development directly on `main`.

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
branch: develop/conversation-fabric (or one current work/* branch)
separate development state
separate locks
separate logs
separate Chrome profile / browser fixture
separate Chat Bridge/native-host configuration where needed
synthetic/test control repositories until an explicit later gate
```

Development must never consume or mutate production `chat-bridge-state`, `operator-control`, task queues, repository control worktrees or runtime state merely because those resources already exist.

A full second execution supervisor is **not required initially**. The first isolated development lab should contain only what the current milestone needs: development checkout, tests, disposable workflow/control fixtures and separate browser/Chat Bridge state. Add a namespaced DEV executor only when a later integration phase genuinely requires it.

## Execution order

### Stage 1 — small `main` housekeeping

Goal: freeze a clean production baseline without changing runtime behavior.

Work:

1. correct confirmed current-documentation drift;
2. reconcile stale release/backlog wording with the actually released behavior;
3. correct stale deployment/topology naming where it contradicts current repository ids;
4. strengthen documentation/release drift tests where a cheap deterministic check prevents recurrence;
5. make an explicit decision about missing release tags instead of silently inventing release history;
6. do not mix BUG-001 or another runtime refactor into this housekeeping change.

Exit criteria:

- no intentional runtime behavior change;
- CI green on exact housekeeping SHA;
- `main` documentation describes current production consistently;
- production runtime continues normally.

### Stage 2 — synchronize Conversation Fabric with current `main`

Goal: development starts from current production reality rather than a stale production snapshot.

Work:

1. compare `develop/conversation-fabric` with current `main`;
2. integrate production changes deliberately;
3. resolve naming/binding/documentation conflicts without reintroducing superseded Conversation Fabric donor code;
4. run the branch verification suite;
5. update Conversation Fabric docs that still pin an obsolete production SHA.

Exit criteria:

- development contains current production fixes/contracts;
- Conversation Fabric-specific tests remain green;
- production branch itself is not modified by this synchronization step.

### Stage 3 — isolated DEV lab/runtime boundary

Goal: allow Conversation Fabric and browser experiments to run beside the production Local Agent without disturbing it.

Start with the smallest useful isolation boundary:

- separate checkout/worktree;
- separate temporary state roots and test repositories;
- separate browser profile or synthetic Chromium profile;
- separate Chat Bridge test configuration;
- explicit prohibition on production control/state branches;
- tests proving development paths cannot resolve to production paths.

Only if later phases require a real second executor, extend the design to an explicit instance namespace covering daemon lock, state, registry, logs, LaunchAgent label, Native Messaging host/config and control-plane identities.

Exit criteria:

- DEV tests/browser fixture can be started, stopped and destroyed without changing PROD state;
- paths/locks/control identities cannot accidentally collide with production;
- normal production Local Agent remains available while DEV work proceeds.

### Stage 4 — Phase 1: pure Conversation Fabric contracts

Implement bounded deterministic contracts for:

- `ChildRequest`;
- `ChildRegistration`;
- logical child lifecycle;
- spawn transaction lifecycle;
- `child_checkpoint`;
- `child_terminal`.

Require strong positive and negative tests. No production Chrome side effects.

### Stage 5 — Phase 2: synthetic Chromium spawn/attach proof

Prove exactly-once/recoverable child creation in a disposable synthetic ChatGPT fixture.

Must cover:

- fresh child bootstrap;
- exact request -> exact conversation registration;
- uncertain first-send race;
- MV3/service-worker restart;
- duplicate prevention;
- manual attach fallback;
- bounded tab concurrency;
- safe retirement/close behavior only after durable terminal state.

No production `SPAWN_CHILD` yet.

### Stage 6 — Phase 3: campaign/workflow integration

Connect registered reasoning children to durable campaign/workflow nodes while preserving Local Agent repository leases and execution semantics.

Add compact parent ledger, evidence references and bounded context selection. Parent context must scale with compact records, not complete child transcripts.

### Stage 7 — Phase 4: Bridge attention/event routing

Integrate child/task/workflow attention into current Chat Bridge owners while preserving the current transient/assistant-timeout recovery path.

Events are hints to reconcile durable state, never success authority by themselves.

### Stage 8 — Phase 5: bounded live slice

First run a small real campaign. Only after that succeeds, run the larger acceptance campaign such as the 44-node audit.

Measure:

- context growth;
- duplicate prevention;
- stuck-child recovery;
- browser/tab bounds;
- integration/rework rate;
- Local Agent interaction;
- terminal-result quality.

### Stage 9 — Phase 6: automatic scheduling only if needed

Add automatic workflow scheduling only after the complete child lifecycle is stable. Reuse the existing workflow/executor substrate; do not introduce a second autonomous executor/model loop.

## Non-negotiable safeguards

- ChatGPT plans; Local Agent remains deterministic and model-free.
- Production and development runtime state do not share mutable locks/state/control by accident.
- Browser child creation never grants execution authority.
- Hard binding remains authoritative.
- Ambiguous child creation or execution fails closed; never blind-replay.
- No uncontrolled tab explosion.
- No whole child transcripts copied into the parent by default.
- Production `main` is never used as a scratch development branch.
- BUG-001 and other runtime defects get their own scoped repair/release path rather than being hidden inside Conversation Fabric work.

## Current checkpoint — 2026-09-24

Completed:

- production `main` was reviewed with a small read-only audit;
- current production HEAD observed during the audit: `ca7e66c8f82da2ddf22935945edec03e214ffc93`;
- GitHub CI for that HEAD is green;
- no broad production refactor is justified before Conversation Fabric work;
- confirmed housekeeping debt includes stale release/backlog/deployment wording and missing release-tag consistency;
- `develop/conversation-fabric` already contains the consolidated Execution Fabric/workflow substrate, Event Wake foundations and canonical Conversation Fabric architecture, but the child-conversation implementation phases are not complete.

Not yet done:

- no housekeeping corrections have been committed to `main` as part of this plan;
- `develop/conversation-fabric` has not yet been reconciled with the latest `main` changes;
- isolated DEV runtime/browser lab has not yet been implemented;
- automatic Superchat child creation is not production-ready.

## Next action

**Stage 1: create/review the small `main` housekeeping change with no runtime behavior change.**

After Stage 1 is green and accepted, immediately perform Stage 2: reconcile `develop/conversation-fabric` with the resulting current `main`, then proceed to the isolated DEV lab.

If a future conversation is unsure what to do next, this `Next action` section is the tie-breaker unless the user explicitly changes the goal.
