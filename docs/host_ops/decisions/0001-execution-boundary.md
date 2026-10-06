# ADR 0001: Keep planning outside host-ops

- Status: Accepted
- Date: 2026-09-19

## Context

The repository is intended to give ChatGPT broad access to local machine, device, browser and remote-host operations through Local Agent. Several existing projects combine tool execution with their own LLM loop, planner, permission UI and scheduler. Reusing such a stack wholesale would duplicate responsibilities already owned by ChatGPT and Local Agent.

Local Agent already provides repository/binding identity, bounded task execution, cancellation, watchdogs and durable execution evidence. ChatGPT remains the planner.

## Decision

`host-ops` will be a deterministic capability layer only.

It may provide:

- stable CLI commands;
- capability contracts and registry metadata;
- local process execution primitives;
- SSH/Termux adapters;
- Android/ADB adapters;
- Playwright browser adapters;
- macOS application/GUI adapters;
- filesystem/network operations;
- diagnostics and prerequisite checks;
- structured results.

It will not provide:

- an embedded LLM/provider client;
- an autonomous planning loop;
- a second task scheduler/queue;
- automatic replay semantics independent of Local Agent;
- a duplicate execution audit database without a proven need;
- an authority mechanism that bypasses Local Agent binding/control boundaries.

## Consequences

### Positive

- one planner and one execution authority model;
- smaller dependency surface;
- capability modules are independently testable;
- easier replacement of browser/SSH/macOS backends;
- Local Agent remains the source of task execution evidence;
- no provider/API dependency is required inside host-ops.

### Negative

- host-ops is not useful as a standalone autonomous agent without an external caller;
- cross-capability workflows must be composed by the CLI/application layer or external planner;
- permission/approval UX is not solved by this repository alone.

## References considered

The initial design review considered Local Agent's OpenWorker governance audit, OpenWorker's capability/permission patterns and Anthropic's computer-use reference implementation. Patterns are adapted selectively; runtime/agent loops are not copied wholesale.
