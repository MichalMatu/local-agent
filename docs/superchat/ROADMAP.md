# Superchat roadmap

This roadmap starts from the current implemented baseline. Old pre-implementation phase numbering is historical and is no longer the active plan.

## Stage A — single-Superchat live acceptance — complete

The core user-visible path is accepted:

- one parent Superchat delegates bounded reasoning-only children in the already authenticated normal Chrome session;
- child registration/results are durable and visible to the parent;
- the parent synthesizes child outputs and remains the only final execution decision-maker;
- target-bound Local Agent execution stays behind canonical catalog/binding admission and queue dedupe;
- bounded acceptance ends in an intentional paused/closed state.

Evidence includes the same-browser acceptance record plus the current real-extension browser regression.

## Stage B — lifecycle/recovery acceptance — complete

The accepted architecture now has both historical live pacing evidence and deterministic production-shaped lifecycle coverage:

- GitHub-managed pause/resume/NEXT was proved in normal daily Chrome;
- service-worker interruption during active multi-child work preserves durable state;
- submitted children recover only from exact transaction/request/bootstrap/current-route evidence and are never blindly replayed;
- explicit retire plus deliberate fresh-id re-delegation provides controlled rollover without automatic replacement;
- unresolved post-submit ambiguity reaches a bounded fail-closed terminal state;
- terminal feedback is durably delivered at most once and a second restart/poll does not replay it.

Exit condition is satisfied: bounded interruptions either recover from durable evidence or stop with an explicit blocker/failure.

## Stage C — concise operator observability — complete

Chat Bridge 0.8.4 provides one compact read-only Operator status surface combining:

- Conversation Operator enabled/configured/running;
- active workflow and child count;
- current Fabric campaign/result/cleanup/terminal-feedback state;
- Bridge Master/version state;
- bounded dedupe suppression/rejection/reconciliation evidence;
- exact Local Agent `daemon_version` + deployed `self_revision`.

The Local Agent half is bounded `.agent/status/operator.json` telemetry; it adds no execution or scheduling authority.

## Stage D — dedupe corrective-intent hardening — complete

Corrective intent is explicit and anti-duplication safety remains fail-closed:

- `dedupe_revision` defaults to 1 and requires an explicit `dedupe_key`;
- after a completed attempt, including a failed attempt, a new task id with a higher revision may represent deliberate corrective work without waiting for the recent-completion TTL;
- a changed plan at the same revision is terminal `dedupe_intent_conflict` evidence;
- a higher revision never bypasses an active claim;
- crash-safe completion reconciliation uses durable `result_published` evidence so claim loss cannot reopen equivalent work.

## Stage E — bounded multi-goal supervision — next

Only now that Stages A-D and the production-path test-architecture milestone are complete:

- define a deterministic active-goal limit;
- add explicit priority and pause/resume policy across goals;
- bound aggregate child spawn rate;
- keep repository-aware execution decisions at the parent/canonical target boundary;
- add circuit breakers for repeatedly blocked/failed goals;
- expose a compact multi-goal fleet snapshot without creating a second scheduler or execution authority.

Exit: one parent can coordinate several bounded goals without becoming an unsafe autonomous scheduler.

## Explicit non-goals

- child machine authority;
- a second executor/scheduler;
- uncontrolled child fan-out;
- broad manual Chrome automation loops;
- predictive rotation as a correctness dependency;
- copying entire historical chats into supervisor prompts.
