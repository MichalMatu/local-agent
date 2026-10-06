# Host Ops Golden Standard

**Status: canonical stable contract.** `host-ops` is in maintenance mode. This document is the first authority for deciding whether a change belongs in this repository.

## Mission

`host-ops` is the deterministic effect layer beneath Local Agent. It validates and executes bounded machine/remote-host operations and returns structured evidence. It does not plan tasks, own project policy, interpret device protocols or schedule work.

```text
ChatGPT / planner -> Local Agent -> host-ops -> OS / Git / serial / storage / SSH / remote host
```

## Stable baseline

The production baseline is the capability set documented in [TARGET_MODEL.md](TARGET_MODEL.md). Architecture and dependency direction are defined in [ARCHITECTURE.md](ARCHITECTURE.md). Security authority is defined in [SECURITY_MODEL.md](../security/SECURITY_MODEL.md).

The default decision is **do not expand the runtime**. A new capability is accepted only when a real downstream project demonstrates a reusable integration boundary that cannot be expressed safely with existing primitives. Device-specific semantics stay downstream.

## Repository invariants

1. `main` contains production source/docs only. Local Agent runtime state under `.agent/` belongs exclusively to `agent-control`, never to `main`.
2. `agent-control` is control-plane state, not product history.
3. Work branches are temporary and are removed after merge/supersession. Valuable abandoned experiments are archived deliberately (for example by tag), not left as ambiguous active branches.
4. The dependency direction remains `cli -> workflows -> capabilities -> core`; lower layers never depend upward.
5. Project/device protocols, calibration, build policy and autonomous planning remain outside `host-ops`.
6. Destructive effects require explicit contracts and explicit task intent.

## Change acceptance

A runtime change is complete only when ownership/boundary/failure semantics are explicit, focused success and realistic failure evidence exist, the canonical verifier passes, and live evidence exists for claims that depend on real devices/hosts. Speculative frameworks and convenience abstractions are rejected.

## Canonical verification

The single repository gate is:

```bash
.venv/bin/python scripts/quality/verify.py
```

Its detailed contract and any manual live/remote golden gates are documented in [VERIFICATION.md](../quality/VERIFICATION.md). CI, when used, must call the same verifier rather than define a second quality contract.

## Documentation hierarchy

When documentation appears to conflict, resolve it in this order:

1. `docs/architecture/GOLDEN_STANDARD.md` — repository mission, boundaries and maintenance posture;
2. `AGENTS.md` — implementation discipline and completion gate;
3. `docs/architecture/TARGET_MODEL.md` + `ARCHITECTURE.md` — stable capabilities and structural detail;
4. `docs/security/SECURITY_MODEL.md` + `docs/quality/VERIFICATION.md` — authority and evidence contracts;
5. `docs/operations/` — operational usage;
6. `docs/plans/ROADMAP.md` — non-binding candidate directions only.

Historical device/project checkpoints do not belong in `host-ops`; they belong in the downstream repository that owns that system.
