# Host Ops target model

**Status: stable baseline / maintenance mode.** `host-ops` is complete for its current role beneath Local Agent. Runtime scope grows only from demonstrated cross-project integration needs.

## Purpose

`host-ops` is a deterministic layer for bounded machine and remote-host effects. Local Agent owns repository identity, scheduling, resources, watchdogs and task evidence; `host-ops` owns input validation, effect boundaries, bounded execution and structured results.

```text
ChatGPT / planner
    -> Local Agent
        -> host-ops
            -> OS / Git / browser / ADB / serial / storage / SSH / remote host
```

It is not an automation platform, planner, scheduler, credential store or device-protocol layer.

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

The following stay outside the stable baseline unless repeated downstream evidence proves a reusable contract:

- device-specific command protocols, calibration, flashing and motion/tool policy;
- autonomous planning, retries, scheduling or generic plugin systems;
- general attached-page automation such as click/fill/press/drag, arbitrary JavaScript, page-content extraction, screenshots, download orchestration, cookies or storage access;
- arbitrary ADB shell, package/reboot operations or broader Android mutation;
- destructive disk formatting/partitioning.

Persistent browser process/session control is already part of the stable baseline; it must not be confused with general page-automation authority. Interactive browser mode deliberately gives the user a normal no-CDP browser process and does not add automated page actions.

## Extension test

A new runtime capability is justified only when:

1. a concrete project cannot express the required effect safely with current primitives;
2. the missing responsibility is a reusable external integration boundary rather than project policy;
3. validation, authority, timeout/failure semantics and structured evidence are clear;
4. focused success/failure tests and the canonical verifier can prove the change;
5. dependency direction `cli -> workflows -> capabilities -> core` remains intact.

Otherwise keep the behavior in the consuming project.

## Maintenance policy

Default work is correctness, safety, compatibility, dependency maintenance and documentation accuracy. Avoid speculative refactors and capability growth that do not improve a demonstrated boundary or failure mode.

`docs/plans/ROADMAP.md` records possible on-demand extensions, not an implementation backlog.
