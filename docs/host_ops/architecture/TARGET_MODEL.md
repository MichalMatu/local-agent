# Host Ops target model

**Status: stable absorbed baseline / active consolidation.** The current Host Ops behavior is a green baseline beneath Local Agent. The next phase inventories, tests and hardens that baseline before introducing a shared internal tool contract and then broadening the reusable multi-tool surface.

## Purpose

`host-ops` is a deterministic layer for bounded machine and remote-host effects. Local Agent owns repository identity, scheduling, resources, watchdogs and task evidence; `host-ops` owns input validation, effect boundaries, bounded execution and structured results.

```text
ChatGPT / planner
    -> Local Agent
        -> host-ops
            -> OS / Git / browser / ADB / serial / storage / SSH / remote host
```

It is not an automation platform, planner, scheduler, credential store or device-protocol layer. It may grow into a broad deterministic tool runtime, but authority, planning, admission, scheduling and durable ChatGPT control remain Local Agent/GitHub responsibilities.

## Stable capability set

The current baseline includes:

- shared bounded process execution, configuration, diagnostics and normalized results;
- read-only local Git context plus generic host, network and tool inspection;
- bounded ADB discovery/identity/logcat plus verified one-file push/pull for an explicit serial;
- browser process/loopback DevTools inspection;
- explicit Chromium CDP inventory, bounded page metadata/selector counts, extension readiness and worker diagnostics;
- exactly guarded attached-page reload plus one-shot content-script recovery built from readiness + reload;
- persistent Chromium session start/status/stop for an isolated host-ops-owned profile with loopback dynamic CDP;
- interactive no-CDP start/status/stop for that same owned profile, intended for short user-driven steps such as authentication;
- one disposable Playwright HTTP(S) navigation probe with bounded sanitized evidence;
- read-only macOS host/USB/serial/storage discovery plus guarded external-media mount/unmount/eject;
- verified local artifact inspection/deployment and removable-media deploy composition;
- bounded raw POSIX serial transactions with explicit port, baudrate, byte/time limits and idle completion;
- hardened OpenSSH execution and verified one-file transfer;
- exact-revision remote Git workspace execution plus explicit lock-aware cache inventory/removal.

These are generic primitives. Device protocols, project commands and task policy remain downstream.

## Boundary rules

The frozen boundary is responsibility, not today's feature count:

- Host Ops/tooling may implement broad deterministic machine primitives when their inputs, effects, bounds and results are explicit;
- Local Agent remains the only owner of planning, repository/task admission, scheduling, resource arbitration and durable execution evidence;
- GitHub remains the only durable ChatGPT <-> Local Agent control/evidence plane; a future ChatGPT plugin is an ergonomic GitHub-backed surface, not a direct execution transport;
- Conversation Fabric owns child/campaign semantics and reasoning orchestration; deterministic browser/chat-UI lifecycle effects may be Tool Runtime primitives, but delegation policy and synthesis do not move into Host Ops;
- destructive or arbitrary-code-like primitives require correspondingly explicit Local Agent policy/resource admission rather than being made "safe" by hiding the underlying capability;
- project/device-specific policy such as calibration sequences, firmware choice or motion strategy remains outside generic tooling unless it becomes a demonstrably reusable deterministic workflow.

Existing narrow boundaries (for example current ADB and attached-browser surfaces) remain the production contract until intentionally expanded with focused tests and policy coverage. Consolidation must not silently broaden authority.

## Extension test

A new runtime capability is justified only when:

1. a concrete project cannot express the required effect safely with current primitives;
2. the missing responsibility is a reusable external integration boundary rather than project policy;
3. validation, authority, timeout/failure semantics and structured evidence are clear;
4. focused success/failure tests and the canonical verifier can prove the change;
5. dependency direction `cli -> workflows -> capabilities -> core` remains intact.

Otherwise keep the behavior in the consuming project.

## Consolidation sequence

The active order is:

1. inventory and normalize the existing tool surface without changing behavior;
2. debug, test and harden each existing capability/workflow;
3. define and regression-protect the internal Local Agent <-> Tool Runtime contract;
4. migrate existing tools onto that contract without semantic drift;
5. expand the reusable multi-tool surface only after the contract is proven;
6. prepare future ChatGPT-plugin ergonomics over the unchanged GitHub control/evidence plane.

Do not invert this order by building a generic plugin framework first.

`docs/DEVELOPMENT_PLAN.md` is the canonical implementation sequence. `docs/plans/ROADMAP.md` may still record possible on-demand extensions, but it is not authority to skip inventory/hardening.
