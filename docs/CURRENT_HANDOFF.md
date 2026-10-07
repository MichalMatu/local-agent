# Current handoff — Host Ops Tooling Phase B

Date: 2026-10-07

Status: **ready for a fresh parent chat**.

## Active goal

Continue Milestone 7, Phase B: harden the already-absorbed Host Ops surface before defining the shared Local Agent <-> Tool Runtime contract.

Do not reopen completed Host Ops absorption, donor retirement, ADB transfer hardening, SSH transfer hardening, browser helper absorption, direct host/macOS timeout work or local artifact bounds unless fresh evidence shows a regression.

Frozen progression:

```text
inventory existing tools
  -> harden existing tools
  -> define Local Agent <-> Tool Runtime contract
  -> migrate existing tools without semantic drift
  -> expand reusable capabilities
  -> future ChatGPT plugin over the same GitHub control/evidence plane
```

No MCP replacement, direct ChatGPT -> Local Agent transport, second scheduler or second browser-control plane is part of this work.

## Read first

Use only this compact source-of-truth chain for current continuation:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/CHECKPOINT_2026-10-07_HOST_OPS_TOOLING_PHASE_B_HANDOFF.md`
4. `docs/DEVELOPMENT_PLAN.md`
5. `docs/host_ops/TOOL_INVENTORY.md`
6. `docs/MULTI_REPOSITORY.md`

Older checkpoints are historical evidence and rollback material. Do not read them unless a current document explicitly points to one for a disputed invariant.

## Locked authority model

- `local-agent` is the executable target for Host Ops work.
- Canonical binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`.
- Chat Bridge conversation identity is transport/scheduling identity only and never grants repository execution authority.
- Resolve the actual executable target from the runtime catalog before creating a task; `execution_enabled=false` targets are inspection-only.
- The parallel supervisor owns production scheduling; its global restart/self-update/status control repository is the first enabled machine-registry entry, currently `growclip`.
- Project/dedicated-hardware tasks use `resources: []` unless there is a real shared external conflict. Tool target identity is not scheduler resource identity.
- Conversation Fabric children are reasoning-only. They inspect bounded scope and return evidence; they do not create tasks, mutate repositories, run host commands or make the final parent decision.
- Use direct GitHub edits when an exact repository diff plus CI is sufficient. Use Local Agent for machine-local commands, builds/tests that require the host, devices and host state.

## Phase B already completed

| Slice | Current evidence |
| --- | --- |
| ADB | Real Samsung discovery/identity/logcat and verified push/pull complete; transfer hardening is closed. |
| SSH / Termux | Strict configured target check/exec plus verified push/pull and cleanup complete; Termux no-clobber fallback hardened. |
| Serial transport | Bounded passive transaction completed on `/dev/cu.usbserial-110`; that CH340/CH341 device is the ESP32-S3, not the printer. |
| Browser Host Ops | Absorbed Playwright helper paths fixed, optional `playwright==1.63.0` dependency restored, isolated owned-session lifecycle/CDP primitives live-smoked. |
| Host/macOS operation budgets | Host profile and direct macOS inspection/storage multi-subprocess operations share whole-operation deadlines. |
| Local artifacts | Inspect/deploy now have 512 MiB default / 16 GiB hard size bounds and 300 s default whole-operation timeout while preserving atomic/no-clobber semantics. |

Latest behavior-changing artifact commit: `48b34d36c3bf98e1f3d2ea01867d8198ead153ce`.
Documentation evidence commit `05e44c55b2071b0ff7e8384c664fc6436a780505` passed exact-head CI run `37569986670` with all six canonical jobs green.

## Deferred physical-only work

Do not block non-physical Phase B on unavailable hardware.

- Anycubic Kobra 2 Neo is **not connected**. Never probe `/dev/cu.usbserial-110` as the printer. When the printer is connected, rerun fresh USB/serial discovery before printer-specific commands.
- No removable external media was present during discovery. Physical inspect/mount/deploy/eject smoke remains deferred until disposable media exists.
- Normal authenticated Chrome / Chat Bridge must remain untouched by Host Ops isolated-browser tests. Live normal-Chrome acceptance is required only when production lifecycle/recovery behavior changes; do not enable or reload it implicitly.

## Phase B closeout status

The non-physical semantic hardening queue is complete:

1. removable-media composition has one shared whole-operation deadline;
2. every maintained operation has a canonical effect/authority classification;
3. target identity, transport locator, tool-runtime lock and scheduler-resource identity are separate;
4. JSON contract version 2 fixes Remote-Git ok/readiness truth and freezes the command-family matrix;
5. ADB and SSH transfer failures preserve action-attempted, committed and cleanup evidence.

Before Phase B is frozen, require exact-head full six-job CI and normal authenticated-Chrome
acceptance for the GitHub-controlled parent self-heal. Only unavailable printer/removable-media
physical proofs may remain deferred. P2 naming/deduplication cleanup is not a blocker unless it
reveals a correctness defect.

## Preferred use of Conversation Fabric

The next parent should fan out bounded read-only audits early instead of doing all repository reading serially.

Recommended first campaign:

- **deadline-audit** — removable-media end-to-end deadline propagation and failure/cleanup semantics;
- **effects-audit** — effect/risk classes across the complete maintained surface;
- **identity-audit** — canonical target/resource identity model and collision/race implications;
- **json-contract-audit** — CLI success/error schema consistency and exact inconsistencies to fix.

Children must receive the exact current `main` SHA and bounded files/scope. They return findings with file/symbol evidence only. The parent synthesizes one design, prevents parallel competing abstractions, then owns any source changes and Local Agent tasks.

## Verification before handoff or merge

For every source change:

1. start from fresh current `main`;
2. preserve the dependency direction `cli -> workflows -> capabilities -> core`;
3. add focused regression coverage for real behavior changes;
4. run exact-head full CI: `absorbed-host-ops`, `test`, `coverage`, `bridge-browser`, `python-314`, `macos-smoke`;
5. use bounded live proof when physical/host/browser semantics require it;
6. retire only temporary branches proven equivalent/merged.

The parent should inspect current `main`, CI, Local Agent repository status/results and the `growclip` supervisor status before queuing executable work, and follow an already pending equivalent task instead of duplicating it.
