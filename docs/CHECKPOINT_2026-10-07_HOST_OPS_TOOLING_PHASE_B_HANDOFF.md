# Checkpoint — Host Ops Tooling Phase B freeze

Date: 2026-10-07

Status: **frozen historical Phase B checkpoint**.

This file records the final Phase B evidence and durable architectural conclusions. It is not an
active work queue. Current work begins in `docs/CURRENT_HANDOFF.md`.

## Freeze evidence

Phase B is frozen at:

- source: `main@915ac2e47170a9e4d8c0b3e6d45852de7994d63b`;
- exact-head CI: run `37588594285`, all six canonical jobs succeeded:
  `absorbed-host-ops`, `test`, `coverage`, `bridge-browser`, `python-314`, `macos-smoke`;
- Local Agent full `scripts/verify.py`: passed on the same source before the verified closeout branch
  was fast-forwarded to `main`;
- production normal-Chrome acceptance:
  `PHASE_B_LIVE_BRIDGE_ACCEPTANCE_OK`;
- supervisor/worker deployment was observed on
  `self_revision=915ac2e47170a9e4d8c0b3e6d45852de7994d63b`.

No non-physical Phase B blocker remains.

## Product direction frozen by Phase B

Host Ops is absorbed into `local_agent.host_ops`. The standalone `MichalMatu/host-ops`
repository is history-only and is not an execution target.

```text
ChatGPT / future plugin
  -> GitHub control + evidence
    -> Local Agent planning / admission / scheduling / policy
      -> Host Ops Tool Runtime
        -> machine / device / remote / browser effects
```

Local Agent remains the single product-level orchestrator. Tool Runtime is a deterministic execution
boundary, not another planner, scheduler, daemon, browser RPC or ChatGPT transport.

The key identity invariant is:

**tool target identity != scheduler resource identity**

Project-dedicated hardware normally remains `resources: []`; exact target identity is validated
inside the operation. Named scheduler resources exist only for real shared external conflicts and
`machine` means whole-host exclusivity.

## Completed semantic hardening

Phase B closed the existing maintained surface without broad capability expansion:

- removable-media composition uses one shared monotonic whole-operation deadline;
- every maintained operation has the canonical semantic-effect / authority-ceiling classification;
- operation target, transport locator, durable identity evidence, tool-runtime lock scope and
  scheduler resource are explicitly separate;
- JSON contract version 2 fixes Remote-Git readiness/`ok` truth and freezes the current
  command-family success/failure matrix;
- ADB and SSH transfer failures preserve conservative
  `action_attempted`, `committed` and `cleanup_failed` evidence;
- Host/macOS inspection and storage paths preserve bounded whole-operation semantics;
- local artifact inspect/deploy preserve bounded size/time, staging, fsync, atomic/no-clobber commit
  and final digest verification;
- production Chat Bridge parent self-heal is generation/signature checked, duplicate-tab fail-closed
  and content-refresh capable without legacy LAB reload markers or a second CDP control plane.

The maintained evidence lives in code, tests, `docs/host_ops/TOOL_INVENTORY.md`,
`TARGET_MODEL.md`, `SECURITY_MODEL.md`, `JSON_CONTRACT.md` and Git history.

## Physical-only deferred proof

These were unavailable and intentionally do not block the freeze:

- Anycubic Kobra 2 Neo: not connected. Fresh USB/serial discovery is mandatory before any
  printer-specific command.
- Removable media: no disposable external medium was available for live inspect/mount/deploy/eject
  and post-side-effect proof.
- `/dev/cu.usbserial-110`, VID:PID `1a86:7523`, is ESP32-S3 CH340/CH341 evidence and must never be
  treated as printer identity.

## Durable authority and runtime invariants

- Executable target for this surface: `local-agent`.
- Canonical binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`.
- Production scheduler: bounded parallel Local Agent supervisor.
- GitHub is the durable ChatGPT <-> Local Agent control/evidence plane.
- Conversation Fabric children are reasoning-only.
- Conversation Fabric owns child/campaign semantics, Result Vault, retry/retire policy and synthesis.
- Tool Runtime effect/authority metadata never creates scheduler resources or grants permission.
- Preserve `cli -> workflows -> capabilities -> core` for the existing Host Ops implementation.
- Do not silently broaden authority while migrating existing tools onto the Phase C contract.

## What Phase B deliberately did not build

Phase B did not create:

- a generic Tool Runtime registry;
- a universal target registry;
- a second scheduler/executor/daemon;
- a common replacement JSON envelope;
- direct ChatGPT execution transport;
- broad new device/browser/ADB/SSH capability expansion.

Those omissions are intentional. Phase C begins by defining the internal Local Agent <-> Tool Runtime
contract over the frozen behavior above.
