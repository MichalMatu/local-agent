# Host Ops absorption plan

Status: **in progress on PR #176**. Runtime, donor regression tests and reusable architecture/operations documentation are being absorbed into Local Agent.

## Architectural decision

Local Agent is the sole brain/orchestrator.

`host-ops` is not a second product, planner, scheduler or control plane. Its production code is a deterministic host-capability layer that Local Agent will absorb while preserving the existing safety boundaries:

```text
ChatGPT / planner
    -> Local Agent
        repository identity
        canonical target admission
        scheduling and resource arbitration
        watchdogs and process lifecycle
        durable task/run/result evidence
        -> absorbed host-ops tooling
            deterministic validation
            bounded machine/remote-host effects
            structured evidence
            -> OS / Git / browser / ADB / serial / storage / SSH / remote host
```

The absorbed layer must never own repository routing, task planning, queueing, retries at the orchestration level, agent bindings, Conversation Fabric policy or a second daemon lifecycle.

## Donor baseline

The donor repository is `MichalMatu/host-ops`. Its current production architecture already matches the target responsibility split: `core -> capabilities -> workflows -> cli`, with process creation centralized in `core.execution` and no planner/scheduler runtime.

The migration must preserve behavior and contracts before attempting cleanup or redesign.

## What moves into Local Agent

Move as one coherent capability subsystem:

- production `src/host_ops` behavior;
- architecture and safety contract tests;
- focused capability/workflow tests;
- the versioned machine-readable JSON contract;
- reusable host-operation documentation;
- the canonical quality rules that protect dependency direction, process ownership, typing, security and bounded effects.

The preferred internal namespace is `local_agent.host_ops`, preserving the donor layer structure initially so the migration does not mix transport/effect code into scheduler or repository packages.

A compatibility `hostops` CLI may remain temporarily, but it must be implemented from the same absorbed code. It is a tooling interface, not a second execution authority.

## What does not move as product runtime

Do not copy the donor repository's repository identity or Local Agent control-plane scaffolding:

- donor `.agent/binding.json` identity;
- donor `agent-control` operational state;
- repository-specific Local Agent onboarding that assumes `host-ops` is an independent execution target;
- any planner, scheduler or queue concept;
- donor-only release/control metadata that has no meaning after absorption.

The isolated CPU/GPU routing experiment on `work/cpu-gpu-routing` is not part of the production migration. Preserve that branch or export its research history before the donor repository is archived or deleted. Pen-plotter and other explicitly isolated prototypes remain separate research material unless a later task promotes them deliberately.

## Migration sequence

1. **Freeze and inventory the donor**
   - record donor `main` and the preserved experimental branch;
   - inventory production modules, tests, docs, console entry points and JSON contract;
   - identify any filesystem/config assumptions tied to the standalone repository.

2. **Import the deterministic subsystem — implemented in PR #176**
   - production code is under `local_agent.host_ops` from donor `host-ops@b12b6f33a5ee667201d4bddcbfa3cb1d1cb2948b`;
   - the existing `core -> capabilities -> workflows -> cli` dependency direction is enforced by migrated architecture/design gates;
   - the complete donor pytest regression suite is retained under `host_ops_tests/`.

3. **Add the Local Agent integration seam — active in PR #176**
   - the compatibility CLI is `python -m local_agent.host_ops` and preserves JSON contract version 1;
   - new `host-maintenance` task preparation targets `local-agent`, not the standalone donor repository;
   - existing Local Agent task admission/scheduling remains the only orchestration authority; no new queue, planner or daemon is introduced.

4. **Migrate verification**
   - move the donor architecture/design/security/unit/integration tests;
   - integrate them into Local Agent's canonical verification flow;
   - keep macOS/live-device claims separate from hermetic CI evidence.

5. **Switch operational ownership**
   - update Local Agent docs and runtime usage to the absorbed tooling;
   - stop authoring new executable tasks whose target is the standalone `host-ops` repository;
   - remove the standalone `host-ops` catalog/binding identity only after no supported workflow depends on it.

6. **Retire the donor repository**
   - preserve required research branches/history;
   - mark the standalone repository archived/deprecated rather than leaving two writable implementations;
   - ensure all maintained host-operation documentation points to Local Agent.

## Non-goals

This migration does not:

- create a new scheduler or child execution authority;
- change Conversation Fabric reasoning-only semantics;
- weaken canonical repository binding/admission;
- broaden destructive host/device authority;
- redesign every host-ops API during the move;
- merge experimental CPU/GPU routing into production by default.

## Exit criteria

Absorption is complete when:

- Local Agent contains the maintained deterministic host-operation implementation and its tests;
- the existing capability safety/architecture invariants are enforced in Local Agent CI;
- supported host operations no longer require a separate `MichalMatu/host-ops` checkout or execution binding;
- there is exactly one maintained orchestration authority: Local Agent;
- compatibility CLI/JSON behavior is either preserved or intentionally versioned with migration evidence;
- the donor repository is read-only/archived or otherwise clearly non-authoritative;
- preserved experimental work remains recoverable and is not silently lost.
