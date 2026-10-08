# Current handoff — Tool Runtime Phase C and Bridge 0.8.13 checkpoint

Updated: **2026-10-08**. Source baseline at start of this documentation handoff: `main@a7731b059fdab9b17ac8aa51df370814c101c257`; **always read fresh main before editing**.

## Current status, by independent track

### Conversation Fabric / Chat Bridge

- Installed operator Chrome reported **Chat Bridge 0.8.13**, content protocol **v26** after extension and parent-tab reload.
- **Live acceptance PASS:** one-child campaign `cf-a9f08cda8905ab33` and three-child parallel campaign `cf-df084c77d84a5929`. In both, the worker reported stable result capture, automatic exact-tab cleanup and parent feedback.
- The earlier `cf-0c2fd2d492856bc8` failure was closed without automatic replay; its child tab was closed manually after a missing legacy completion footer.
- **Remaining Fabric live test:** service-worker/extension reload *during* an active new campaign, followed by exact-claim result recovery and no duplicate bootstrap or terminal feedback. Existing Chromium CI already exercises controlled worker recovery, but live Chrome interruption is not yet accepted.
- Canonical details and evidence: [Fabric checkpoint](conversation_fabric/CHECKPOINT_2026-10-08_BRIDGE_0813_LIVE_ACCEPTANCE.md), [current plan](conversation_fabric/CURRENT_PLAN.md), [next live test](conversation_fabric/NEXT_CHAT_PROMPT.md).

### Local Agent — Milestone 7 Tool Runtime Phase C

Active implementation remains **Tool Runtime Phase C**, separate from Bridge acceptance:

- Frozen Host Ops Tooling Phase B: `915ac2e47170a9e4d8c0b3e6d45852de7994d63b`, six-job CI `37588594285`, and operator live Bridge acceptance `PHASE_B_LIVE_BRIDGE_ACCEPTANCE_OK`.
- Phase C **contract v1 is already implemented** in `local_agent/tool_runtime/contract.py` (PR #179); do **not** restart the contract-design task as if no source existed.
- Existing pure Host Ops projections in `local_agent/tool_runtime/host_ops_adapter.py`: artifact inspect/deploy; ADB identity/logcat/push/pull; SSH check/push/pull (PRs #180, #181, #184, #189 and related source). These are descriptive/validation adapters, **not** a second executor or a general registry.
- Next engineering task: inspect the actual current adapter inventory and `docs/host_ops/TOOL_INVENTORY.md`; choose the smallest justified missing projection or contract regression, prove preservation of existing Host Ops behavior/error/partial-effect evidence, then validate with exact-head CI. Do not expand the capability set speculatively.
- Physical tests still deferred: Anycubic Kobra 2 Neo printer not connected; `/dev/cu.usbserial-110` was ESP32-S3 CH340/CH341 evidence, not printer identity; removable-media destructive/live proof requires appropriate disposable hardware.

## Read first

1. `AGENTS.md` — repository rules and authority.
2. `docs/CURRENT_HANDOFF.md` — this document.
3. `docs/DEVELOPMENT_PLAN.md` — active milestones.
4. `docs/host_ops/TOOL_INVENTORY.md` and `docs/host_ops/architecture/TARGET_MODEL.md`.
5. `docs/host_ops/security/SECURITY_MODEL.md` and `docs/host_ops/operations/JSON_CONTRACT.md`.
6. `docs/conversation_fabric/CURRENT_PLAN.md` when changing Bridge/Fabric.
7. `docs/OPERATIONS.md` for executable host/repository procedures.

The dated Phase B handoff and historical Conversation Fabric isolated-profile instructions are **evidence**, not instructions to restart completed milestones.

## Immutable authority rules

- `local-agent` remains the executable target for repository-host development. Resolve the target in the *current runtime catalog*; verify the exact canonical binding and `execution_enabled` at task publication, never rely on chat binding.
- Chat Bridge is transport/scheduling and browser reasoning-child lifecycle only. GitHub `conversation_controls` owns remote chat pacing; no GitHub-backed child-chat spawn migration has replaced the Chrome worker.
- Local Agent alone owns planner/executor boundaries, canonical repository/task admission, locks/resources, budgets/watchdogs, durable run evidence and emergency controls.
- Tool Runtime describes deterministic capabilities, normalized targets/effects/results/deadlines and bounded serialization; descriptors never authorize execution.
- **Tool target identity is not scheduler resource identity**. Dedicated project hardware normally has `resources: []`; claim named resources only for real cross-task conflicts.
- Preserve existing Host Ops Python semantics and **CLI JSON contract v2**. No universal registry, second scheduler, MCP replacement, direct ChatGPT-to-daemon transport, child machine authority or general browser-controller duplication.

## Verification / branch hygiene

- Start every code change from the latest `main`; keep the diff small, add focused regression coverage and review actual ownership/partial-effect behavior.
- Require all six exact-head CI jobs: `test`, `coverage`, `python-314`, `absorbed-host-ops`, `bridge-browser`, `macos-smoke`, plus bounded live acceptance when browser/device runtime semantics change.
- Use connected GitHub source edits when reviewable diff and CI suffice; machine/device/local Chrome execution requires an authorized machine executor.
- Source branches `work/*` are disposable **after exact PR state is verified**. Never touch `main` or control/evidence branches. Branch audit and deletion limitations: [2026-10-08 checkpoint](conversation_fabric/CHECKPOINT_2026-10-08_BRIDGE_0813_LIVE_ACCEPTANCE.md).
