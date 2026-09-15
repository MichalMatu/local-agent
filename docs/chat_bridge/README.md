# Chat Bridge development

This directory contains forward-looking design and implementation notes for Local Agent Chat Bridge work that is not yet part of the production contract.

Current production behavior remains defined by:

- [`../../chat_bridge/README.md`](../../chat_bridge/README.md) — installed extension behavior and control protocol;
- [`../AUTONOMOUS_CHAT_LOOP.md`](../AUTONOMOUS_CHAT_LOOP.md) — planner/executor continuation rules;
- [`../OPERATIONS.md`](../OPERATIONS.md) — Local Agent operational contract;
- [`../SECURITY_MODEL.md`](../SECURITY_MODEL.md) — trust boundaries and safety assumptions.

## Active development: event-driven wake

The current autonomous loop uses scheduled wake-ups to discover that Local Agent work has completed. The event-driven wake project adds a narrow local notification path so Chat Bridge can wake the exact hard-bound conversation immediately after authoritative task evidence becomes available.

Design documents:

- [`EVENT_WAKE_ARCHITECTURE.md`](EVENT_WAKE_ARCHITECTURE.md) — target architecture, trust boundaries, event contract, lifecycle and failure handling.
- [`TODO.md`](TODO.md) — phased implementation checklist and acceptance criteria.

Working branch: `feature/chat-bridge-event-wake`.

## Design rule

Event-driven wake is an optimization of continuation latency, not a new authority path.

It must not:

- give ChatGPT arbitrary shell or terminal access;
- infer task completion by parsing terminal text;
- weaken conversation/repository `agent_binding` isolation;
- make a local notification authoritative evidence of task success;
- remove bounded scheduled reconciliation until event delivery has proved reliable in production.

The planner still reads the exact durable task result before deciding what to do next.
