# Superchat roadmap

This roadmap starts from the current implemented baseline. Old pre-implementation phase numbering is historical and is no longer the active plan.

## Stage A — single-Superchat live acceptance — NEXT

Prove the core user-visible behavior on real code:

- one parent Superchat;
- at least two bounded reasoning-only children;
- real child registration/result evidence;
- parent observes and synthesizes child outputs;
- at most one justified target-bound Local Agent execution;
- queue dedupe prevents overlapping equivalent expensive work;
- clean bounded shutdown/pause after the proof.

Exit: a user can watch one parent delegate, collect, decide and execute without giving children machine authority.

## Stage B — lifecycle/recovery acceptance

Prove that the same architecture survives failure boundaries:

- restart during child creation/wait/result collection;
- durable recovery without duplicate authoritative children;
- pause/resume;
- one controlled child rollover;
- hard exhaustion remains terminal/fail-closed;
- parent resumes from durable checkpoint/evidence rather than copied chat history.

Exit: every bounded interruption either resumes safely or stops with one explicit supervisor blocker.

## Stage C — concise operator observability

Provide one status surface showing:

- operator enabled/configured/running;
- parent goal and active children;
- child lifecycle state/result;
- Bridge scheduling state;
- dedupe suppression evidence;
- exact Local Agent/Chat Bridge revisions.

Exit: live readiness can be assessed without reading scattered runtime files.

## Stage D — dedupe corrective-intent hardening

Separate recent successful completion suppression from failed-terminal corrective intent so a materially changed retry is not accidentally blocked by a failed predecessor while preserving anti-duplication safety.

Exit: explicit corrective work is admissible without reopening duplicate execution races.

## Stage E — bounded multi-goal supervision

Only after Stages A-B pass in production:

- deterministic active-goal limit;
- priority and pause/resume policy;
- bounded spawn rate;
- compact fleet snapshot;
- repository-aware scheduling policy;
- circuit breakers for repeated blocked/failed goals.

Exit: one parent can coordinate several goals without becoming an unsafe autonomous scheduler.

## Explicit non-goals until later

- child machine authority;
- a second executor/scheduler;
- uncontrolled child fan-out;
- broad manual Chrome automation loops;
- predictive rotation as a correctness dependency;
- copying entire historical chats into supervisor prompts.
