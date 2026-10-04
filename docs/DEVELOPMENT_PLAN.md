# Local Agent development roadmap

This roadmap contains only active forward work. Historical rollout detail belongs in release notes, self-diagnostic reports and archived evidence.

## Baseline — complete

- deterministic target-bound `.agent/tasks` execution;
- bounded parallel multi-repository scheduler and resource admission;
- durable task/result/recovery contracts;
- GitHub-backed Chat Bridge control;
- transport-only Superchat conversation identity;
- reasoning-only Conversation Fabric children;
- isolated child-browser lifecycle path;
- production queue deduplication (`v4.20.6`);
- child auth readiness decoupled from composer DOM readiness (`main@e4b3da908cfac61bb11cd0e4182b7d9e7c42d5b8` code checkpoint).

## Milestone 1 — live single-Superchat acceptance — NEXT

Prove the product shape on real code:

- one parent Superchat owns one bounded real goal;
- parent delegates at least two narrow, non-overlapping reasoning jobs to child chats;
- children return bounded evidence/recommendations and have no machine authority;
- parent synthesizes the final decision;
- if code execution is justified, exactly one target repository task is queued with the exact binding and stable intent identity;
- Local Agent executes once and publishes durable evidence;
- no duplicate expensive build/test task runs;
- child/operator state is cleanly retired or paused after the proof.

Do not expand scope until this passes end to end.

## Milestone 2 — live recovery and lifecycle proof

After Milestone 1 passes:

- restart/reconnect during an active child lifecycle;
- recover bounded durable child state without duplicate authoritative workers;
- exercise pause/resume and one controlled rollover;
- prove hard conversation exhaustion remains fail-closed;
- preserve goal continuity from durable checkpoint/evidence rather than old-chat prose.

## Milestone 3 — operator observability

Expose one concise normal status surface for:

- Conversation Operator enabled/configured/running state;
- active parent goal and child count;
- latest child lifecycle result;
- queue dedupe suppression counts/reasons;
- exact deployed Local Agent and Chat Bridge revisions.

This should remove the need to infer operator readiness from scattered files.

## Milestone 4 — dedupe hardening

Review completion receipt semantics for failed terminal results. A materially changed corrective task must not be accidentally suppressed solely because a failed predecessor published successfully. Preserve the bounded anti-duplication guarantee while allowing explicit corrective intent.

## Milestone 5 — bounded multi-goal supervision

Only after single-goal lifecycle/recovery is proven:

- deterministic active-goal limit;
- explicit priorities and pause/resume;
- bounded spawn rate;
- repository-aware policy;
- circuit breakers for repeated blocked/failed goals;
- compact fleet snapshot for the parent.

## Not current work

Do not reopen legacy repository-bound chat routing, broad manual browser debugging, a second executor/scheduler, child machine authority, or predictive autonomous fan-out. Those directions conflict with the accepted architecture or are premature before live acceptance.
