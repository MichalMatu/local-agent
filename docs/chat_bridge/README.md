# Chat Bridge development

This directory contains design, implementation and release-audit notes for Local Agent Chat Bridge work that is not yet merged into production.

Current operational behavior on this working branch is also documented by:

- [`../../chat_bridge/README.md`](../../chat_bridge/README.md) — installed extension behavior and control protocol;
- [`../AUTONOMOUS_CHAT_LOOP.md`](../AUTONOMOUS_CHAT_LOOP.md) — planner/executor continuation rules;
- [`../OPERATIONS.md`](../OPERATIONS.md) — Local Agent operational contract;
- [`../SECURITY_MODEL.md`](../SECURITY_MODEL.md) — trust boundaries and safety assumptions.

## Active development: event-driven wake

The event-driven wake project adds a narrow local notification path so Chat Bridge can wake the exact hard-bound conversation immediately after authoritative task result publication instead of relying on repeated no-change polling.

Working branch: `feature/chat-bridge-event-wake`.
Draft PR: `#77`.

Documents:

- [`EVENT_WAKE_ARCHITECTURE.md`](EVENT_WAKE_ARCHITECTURE.md) — architecture, trust boundaries, event contract, lifecycle and failure handling.
- [`TODO.md`](TODO.md) — implementation/release checklist with automated and real-machine gates.
- [`PREMERGE_AUDIT.md`](PREMERGE_AUDIT.md) — fail-first re-audit of authority, publication order, outbox integrity, Native Messaging, routing, MV3 restart, delivery loss and fallback behavior.

## Current candidate shape

The branch now implements:

- bounded durable Local Agent `task_result_ready` outbox after successful result push;
- notification-only Chrome Native Messaging host;
- exact `[LAB:WAIT_TASK=<task-id>]` conversation watch;
- routing by repository id + repository name + `agent_binding` + task id;
- durable recent-event/pending-wake state across MV3 restart;
- on-demand native transport suspended during PAUSE/operator-disable/Master-off;
- scheduled reconciliation fallback even when native delivery is unavailable;
- planner/runtime guidance that prefers `WAIT_TASK` over periodic healthy-task completion polling;
- bounded `LAB:CAPABILITIES`/`STATUS`/`DEBUG` event-wake diagnostics;
- negative/race/restart/integrity/installer regression coverage.

The implementation remains a candidate until the exact final SHA passes the full CI matrix and the real-Mac Native Messaging/live ChatGPT gates in `TODO.md`/`PREMERGE_AUDIT.md` are recorded.

## Design rule

Event-driven wake is an optimization of continuation latency, not a new authority path.

It must not:

- give ChatGPT arbitrary shell or terminal access;
- infer task completion by parsing terminal text;
- weaken conversation/repository `agent_binding` isolation;
- make a local notification authoritative evidence of task success;
- expose task create/cancel or arbitrary filesystem/log access through Native Messaging;
- remove bounded scheduled reconciliation.

The planner still reads the exact durable terminal task result before deciding what to do next.

## Merge rule

Do not merge this working branch to `main` merely because automated tests are green. `main` may trigger Local Agent autoupdate. Merge requires an explicit release decision after the real-machine validation gates are complete.
