# Current handoff — Tool Runtime Phase C

Date: 2026-10-07

Status: **ready for a fresh parent chat**.

## Frozen baseline

Host Ops Tooling Phase B is complete and frozen at:

- source: `main@915ac2e47170a9e4d8c0b3e6d45852de7994d63b`;
- exact-head CI: run `37588594285`, all six canonical jobs green;
- local verifier: `scripts/verify.py` passed on the same source before fast-forward to `main`;
- production browser acceptance: `PHASE_B_LIVE_BRIDGE_ACCEPTANCE_OK`;
- Local Agent supervisor/worker were loaded on the same source revision after closeout.

The historical freeze record is
`docs/CHECKPOINT_2026-10-07_HOST_OPS_TOOLING_PHASE_B_HANDOFF.md`.

Do not reopen Phase B hardening unless fresh evidence shows a regression.

## Active goal

Continue Milestone 7, **Phase C**: define and regression-protect the internal
`Local Agent <-> Tool Runtime` contract.

The first Phase C slice is contract definition only. Do not expand the capability surface and do not
build a generic registry/discovery framework yet.

The contract must cover:

1. stable code-owned tool identity;
2. validated arguments and structured results;
3. the frozen semantic-effect and authority-ceiling classes;
4. operation target, transport locator and durable identity evidence;
5. scheduler-resource requirements without deriving scheduler locks from tool target identity;
6. whole-operation execution bounds/deadlines;
7. artifact metadata and partial-effect/error evidence;
8. bounded deterministic serialization plus explicit schema/version behavior;
9. migration rules that preserve existing Host Ops Python behavior and CLI JSON contract version 2.

## Read first

Use this compact source-of-truth chain:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/CHECKPOINT_2026-10-07_HOST_OPS_TOOLING_PHASE_B_HANDOFF.md`
4. `docs/DEVELOPMENT_PLAN.md`
5. `docs/host_ops/TOOL_INVENTORY.md`
6. `docs/host_ops/architecture/TARGET_MODEL.md`
7. `docs/host_ops/security/SECURITY_MODEL.md`
8. `docs/host_ops/operations/JSON_CONTRACT.md`
9. `docs/MULTI_REPOSITORY.md`

Older checkpoints are historical evidence only unless a current document points to one for a disputed invariant.

## Locked authority model

- `local-agent` remains the executable target for this work.
- Canonical binding: `2180d453-1357-4fbc-be1a-e1e5b8fbb10a`.
- Chat Bridge conversation identity is transport/scheduling identity only and never grants repository execution authority.
- Local Agent remains the only owner of planning, repository/task admission, scheduling, resource arbitration, watchdogs and durable execution evidence.
- Tool Runtime validates and executes deterministic effects; it does not own scheduling or planner policy.
- Effect/authority metadata describes capability; it never grants permission.
- **tool target identity != scheduler resource identity**.
- Project-dedicated hardware normally remains `resources: []`; named resources exist only for genuine shared conflicts.
- Conversation Fabric children are reasoning-only.
- GitHub remains the durable control/evidence plane.

## Reuse before invention

Phase C should start from existing abstractions rather than replace them:

- execution bounds: `local_agent/host_ops/core/execution/limits.py::ExecutionLimits`;
- normalized process evidence: `ProcessResult`;
- scheduler resource authority: `local_agent/runtime/task_contract.py::task_resources_for` and supervisor resource admission;
- effect/authority taxonomy: `docs/host_ops/TOOL_INVENTORY.md` and `docs/host_ops/security/SECURITY_MODEL.md`;
- target semantics: `docs/host_ops/architecture/TARGET_MODEL.md`;
- stable result models and validators in artifact, ADB, SSH, serial and remote-Git capabilities;
- bounded artifact metadata pattern in `local_agent/mcp/artifacts.py`;
- deterministic task serialization/version rejection patterns in existing Local Agent contracts.

MCP policy/config patterns may be inspected for naming/versioning ideas, but Phase C is not an MCP
migration and must not make the MCP registry the Tool Runtime registry.

## Smallest proving sequence

The initial contract should be dependency-light, for example under
`local_agent/tool_runtime/contract.py`, and contain only DTOs/enums, validation and bounded
canonical serialization.

Prove it in this order:

1. `artifact inspect` — passive, bounded, target-light;
2. one target-bearing read such as `ssh check` or `adb identity`;
3. one existing mutation/partial-failure path such as verified ADB or SSH transfer.

Only after those examples preserve existing semantics should migration of the remaining tools be designed.

## Explicit non-goals for the first Phase C slice

Do not build:

- a generic tool registry/catalog/discovery service;
- a universal target registry;
- a second executor, scheduler, daemon or browser control plane;
- direct ChatGPT -> Local Agent execution transport;
- an MCP replacement;
- a common Host Ops CLI JSON envelope;
- a task-schema redesign;
- new ADB/SSH/browser/device capability expansion;
- broad P2 naming/deduplication cleanup.

## Physical-only deferred proof

These remain intentionally outside the Phase C start gate:

- Anycubic Kobra 2 Neo printer-specific serial proof, after fresh discovery when connected;
- disposable removable-media inspect/mount/deploy/eject and post-side-effect live proof.

`/dev/cu.usbserial-110` remains ESP32-S3 CH340/CH341 evidence, not printer identity.

## Verification discipline

For every source change:

1. start from fresh current `main`;
2. preserve existing dependency and authority boundaries;
3. add focused contract regressions;
4. preserve existing Host Ops behavior/CLI JSON v2 unless a separately versioned migration is intentional;
5. run exact-head full CI: `absorbed-host-ops`, `test`, `coverage`, `bridge-browser`, `python-314`, `macos-smoke`;
6. use Local Agent for machine-local tests/state and direct GitHub edits only when exact diff + CI are sufficient;
7. retire temporary work branches once proven merged/equivalent.

Use Conversation Fabric for bounded independent read-only design audits when useful, but do not replay
the completed Phase B deadline/effect/identity/JSON audits.
