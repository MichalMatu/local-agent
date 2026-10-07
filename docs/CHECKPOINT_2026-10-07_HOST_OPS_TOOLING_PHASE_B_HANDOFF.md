# Checkpoint — Host Ops Tooling Phase B handoff

Date: 2026-10-07

Status: **current Phase B continuation checkpoint**.

This checkpoint intentionally records only information needed to continue current work. Historical implementation detail remains available in Git history, task results and older checkpoints.

## Product direction

Host Ops is absorbed into `local_agent.host_ops`. The standalone `MichalMatu/host-ops` repository is archived/history-only and is not an execution target.

The architecture is frozen:

```text
ChatGPT / future plugin
  -> GitHub control + evidence
    -> Local Agent planning / admission / scheduling / policy
      -> Host Ops Tool Runtime
        -> machine / device / remote / browser effects
```

Local Agent remains the single product-level orchestrator. A future Tool Runtime is an internal deterministic execution contract, not another planner, scheduler, daemon, browser RPC or ChatGPT transport.

The key distinction established during live device work remains:

**tool target identity != scheduler resource identity**

Project-dedicated hardware work normally remains `resources: []`; exact device/endpoint identity is discovered and validated inside the operation. Named resources are for genuine shared external conflicts, and `machine` means whole-host exclusivity.

## Completed Phase B evidence

### ADB

Real Samsung Galaxy S22+ proof covers discovery, exact identity, bounded logcat and verified push/pull.

Important fixes:
- `f92feebd3b2dafe5e5de36f5e40d83ab25fa72ec` — query fixed identity properties rather than parsing an unsafe full multiline `getprop` dump;
- `a2808e0352d36c0d3958e12284712dee468a1a31` — bounded remote SHA-256 fallback compatible with Android shell/tooling;
- final transfer task `local-agent-host-ops-adb-transfer-e2e-20261007-v4` passed round-trip SHA verification and exact cleanup.

Wireless ADB `IP:port` was observed changing on the same phone and is therefore a transport locator, not durable device identity.

### SSH / Termux

Configured target `termux-phone` at the time of live proof used `192.168.0.100:8022`, user `u0_a520`, strict host-key verification, explicit configured key and `-F /dev/null`.

Real hardening:
- `5d6fe44415be47fe3a5225b4adcf2440b937f874` — hardened no-clobber push when Termux denies hardlinks, with fail-closed race handling;
- `3f3aa98c78b0209bdb641450c28e043671142fcc` — kept implementation within design budget;
- `local-agent-host-ops-ssh-transfer-e2e-20261007-v2` passed bounded push/pull with identical SHA and cleanup;
- cleanup task confirmed all exact disposable files absent.

SSH `exec` is arbitrary-code-like authority even when a particular smoke command is harmless.

### Serial and removable-media discovery

USB/serial discovery identified `/dev/cu.usbserial-110`, VID:PID `1a86:7523`, as the ESP32-S3 CH340/CH341 connection.

A passive bounded serial transaction wrote zero bytes and proved the generic transport path only. It is not printer evidence.

No external removable media was present, so physical mount/deploy/eject remains deferred.

### Browser Host Ops

Isolated Host Ops browser work is complete for the current deterministic primitives:

- `5a836b8ea033e71250e50d43d91763efa023bb98` fixed seven absorbed Playwright helper module paths;
- `3479b067166e03a1d1d12e47f778553ee632bc89` restored the optional exact `playwright==1.63.0` dependency without adding it to default runtime requirements;
- `local-agent-host-ops-browser-owned-attach-e2e-20261007-v3` passed isolated session start, CDP target inventory, snapshot, selector counts, worker diagnostics, readiness, guarded reload, bounded recovery, stop and cleanup;
- `87a48c23697f68302ea5c9fd9a5ea5ba2df3254d` records the browser hardening evidence.

This did not alter production browser authority. Normal authenticated Chrome + installed Chat Bridge remains the accepted Conversation Fabric execution surface.

### Whole-operation budgets and local artifacts

- `6d2241da0f6c7709cc6502c2cfa6bd960c847014` gives host-profile and direct macOS inspection/storage multi-subprocess operations one monotonic operation deadline.
- `48b34d36c3bf98e1f3d2ea01867d8198ead153ce` bounds local artifact inspect/deploy by size and time while preserving symlink rejection, staging, fsync, atomic/no-clobber commit and final digest verification.
- focused task `local-agent-host-ops-artifact-bounds-focused-20261007-v5` passed architecture/design gates and real CLI success/failure/cleanup smoke.
- documentation evidence head `05e44c55b2071b0ff7e8384c664fc6436a780505` passed exact-head CI run `37569986670` with all six canonical jobs green.

## Phase B closeout

Non-physical contract hardening is complete: shared removable-media deadline, canonical
effect/authority taxonomy, target/resource identity rules, JSON contract version 2 and structured
ADB/SSH partial-effect evidence.

Remaining non-physical freeze gates are evidence only:
- exact-head full six-job CI must be green;
- the GitHub-controlled parent self-heal must pass normal authenticated-Chrome acceptance after the
  verified code is loaded.

P2 cleanup remains optional after freeze unless fresh correctness evidence requires it.

## Physical-only deferred proof

- Anycubic Kobra 2 Neo: not connected. Fresh USB/serial discovery is mandatory before any printer command.
- Removable media: unavailable during last discovery. Use disposable media when available for inspect/mount/deploy/eject and partial-failure proof.
- Production normal-Chrome acceptance: required only when production Chat Bridge lifecycle/recovery behavior changes; current Host Ops browser hardening does not justify touching the user's authenticated session.

These deferrals do not block the non-physical Phase B contract work above.

## Conversation Fabric boundary

Conversation Fabric owns delegation policy, campaign identity/capacity, child roles, stable-result adoption, retry/retire policy, Result Vault, completion and synthesis.

Deterministic browser/chat-UI primitives may later share a semantic Tool Runtime contract, but their production implementation stays in the extension until an architecture-preserving migration exists.

Children are reasoning-only. A child must not create Local Agent tasks, mutate repositories, run host commands or choose the final architecture.

## Conversation Fabric audit status

The deadline, effect, identity and JSON-contract audits were completed in bounded reasoning-only
campaigns and have been incorporated into the maintained code and documentation. Do not replay the
completed swarm unless fresh evidence creates a new independent question.

## Runtime / execution invariants

- Executable target: `local-agent`.
- Canonical binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`.
- Global supervisor control repository: first enabled machine-registry entry, currently `growclip`.
- Production scheduler: bounded parallel supervisor, max workers 4.
- Resolve fresh runtime catalog before executable work.
- Follow an already active/pending equivalent task instead of queuing a duplicate.
- Direct GitHub edits are appropriate for exact source/documentation changes that CI can validate.
- Local Agent is required for machine-local commands, local host/device state and physical I/O.
- Preserve `cli -> workflows -> capabilities -> core`.
- Do not widen capability authority during this hardening pass.

## Fresh-parent start procedure

1. Read `AGENTS.md`, `docs/CURRENT_HANDOFF.md`, this checkpoint, `docs/DEVELOPMENT_PLAN.md`, `docs/host_ops/TOOL_INVENTORY.md` and `docs/MULTI_REPOSITORY.md`.
2. Resolve fresh `main` and exact-head CI.
3. Inspect Local Agent repository status/pending/running/results and `growclip` supervisor status.
4. If clean, launch the four read-only audit children above.
5. Synthesize one contract direction.
6. Implement the smallest first hardening slice, starting with the composed removable-media shared deadline.
7. Add focused regressions, run full exact-head CI and record only durable evidence needed for the next handoff.
