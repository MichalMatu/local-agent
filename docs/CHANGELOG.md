# Changelog

This changelog records operationally relevant Local Agent releases. The release tag and `local_agent.version.RELEASE_VERSION` are the version source of truth. Historical per-release notes remain available under `docs/`.

## v4.17.0

- Completed the next package-ownership phase by moving execution core/process/storage foundations, repository admin/cleanup/worker, task executor, parallel worker, diagnostics and release version under `local_agent/`.
- Reduced historical root library modules to thin aliases/shims and added `tests/test_package_layout.py` to prevent implementation from growing back into compatibility surfaces.
- Standardized root compatibility modules on one-module-object aliases so monkeypatch/runtime semantics do not create a second wrapper implementation.
- Updated `docs/ARCHITECTURE.md` and `AGENTS.md` to make packaged ownership and the root entrypoint boundary explicit.
- Kept `agentd.py`, `agent_parallel.py` and `agent_multirepo.py` as deliberate location-sensitive root orchestrators rather than performing unsafe cosmetic moves.
- Kept `local_agent/supervisor/scheduling.py` parity-protected but not runtime-wired; production scheduling semantics still live in `agent_parallel.py`.
- Preserved task, hard-binding, control, resource, watchdog, publication and Chat Bridge contracts; no downstream task-contract migration is required.

## v4.16.0

- Refactored implementation ownership into `local_agent/` packages while keeping root compatibility shims/entrypoints where existing runtime callers still require them.
- Added centralized `scripts/verify.py`, explicit Ruff configuration and branch-aware coverage reporting in CI.
- Moved configuration, repository identity/hard binding, local/remote operator control and guarded entrypoint implementation into packaged owners.
- Extracted external-resource flock/FD handling and directly tested pure scheduling policy under `local_agent/supervisor/`.
- Replaced machine-specific tracked macOS plist files with portable generated LaunchAgent configuration and separated non-disruptive install from explicit restart.
- Added targeted regression coverage for parallel worker admission, guarded entrypoint lifecycle, remote fail-closed operator control and diagnostics.
- Added architecture/contributor/review documentation for the new ownership boundaries.
- Preserved the existing planner/task, hard-binding, resource and Chat Bridge control contracts; no downstream task-contract migration is required.

## v4.15.0

- Introduced hard binding between one ChatGPT conversation, one canonical `agent_binding` UUID and one exact repository identity.
- Made unbound or mismatched bridge/runtime state fail closed instead of inferring a repository from chat context.
- Added explicit operator-only **Rebind** semantics; normal chat edits and assistant control markers cannot change repository identity.
- Required matching registry binding, control-branch `.agent/binding.json` and task `agent_binding` before serial or parallel execution may claim work.
- Added terminal pre-claim rejection for missing or wrong task bindings so rejected work executes no task command.
- Updated Chat Bridge to v0.4/state schema v3 with exact identity envelopes on bootstrap and wake messages.
- Hardened control synchronization by materializing the fetched remote control ref before active cancellation/ACK checks.

## v4.14.3

- Made `reset-runtime` remove global ephemeral daemon status as well as repository/legacy runtime state.
- Added status-owner liveness semantics so dead owners are reported as stale rather than presented as a live daemon.
- Aligned `agentctl status` and `agentctl doctor` with guarded-entrypoint ownership.

## v4.14.2

- Added guarded `agent_entrypoint.py` ownership of the supervisor lifecycle.
- Added repository-independent `operator-control` desired-state emergency control.
- Added disabled-only `reset-runtime` for stale local claim/spool/run state after destructive queue recovery.
- Added guarded cleanup of generated control bytecode and provisioning of completely missing control/work checkouts.
- Runs the supervisor with `PYTHONDONTWRITEBYTECODE=1` and expanded Linux/macOS emergency-control coverage.

## v4.14.1

- Added repository-scoped `cancel_task` for pending and active work.
- Added a global persistent Local Agent disable marker that survives supervisor and launchd restarts.
- Added explicit local `agent_operator.py enable|disable|status` control.
- Made malformed disable state fail closed and expanded emergency-control tests/documentation.

## v4.14.0

- Added bounded garbage collection for Git-backed runtime metadata after control synchronization.
- Pending tasks are never pruned; terminal task/result files are pruned as pairs and pending-task run records stay protected.
- The ACK matching the current control request is always protected.
- Cleanup failures remain fail-open for task execution while unexpected `.agent/tasks` mutations remain fail closed.
- Default retention is 32 terminal task/result pairs, 32 runs, 16 ACKs and 8 orphan results.

## v4.13.1

- Fixed remote idle-heartbeat freshness so stale daemon status/version cannot persist because of locally rewritten status-file mtimes.
- Made explicit retry deadlines override normal adaptive polling for resource and worker backoff.
- Preserved parallel/serial execution metadata during supervisor-wide status control.
- Separated inherited repository execution leases from external resource-lock descriptors.
- Extracted shared supervisor polling/order policy and control-binding primitives under `local_agent/supervisor/`.

## v4.13.0

- Made task `resources` mandatory and strictly validated instead of silently falling back to whole-machine exclusivity.
- Defined `resources: []` as repository-local work with no exclusive external resource.
- Reserved named resources for concrete shared devices/state and `machine` for genuine whole-host operations.
- Decoupled `memory_limit_mb` from resource admission.
- Added durable resource waiting with bounded retry and published `waiting_resource` status.
- Improved Chat Bridge `NEXT=<duration>` continuation behavior and regression coverage.

## v4.12.2

- Continued behavior-preserving runtime modularization.
- Extracted progress-marker parsing and bounded asynchronous progress publication into `local_agent/runtime/progress.py`.
- `agent_runtime.py` retains the historical progress imports and keeps executor heartbeat timing (`PROGRESS_INTERVAL`) local for compatibility with existing monkeypatch/test seams.

## v4.12.1

- Continued behavior-preserving runtime modularization.
- Extracted immutable task digests, schema validation, task payload limits and bounded timeout/memory parsing into `local_agent/runtime/task_contract.py`.
- `agent_runtime.py` re-exports the historical task-contract names and constants so existing callers and tests keep the same import surface.

## v4.12.0

- Began behavior-preserving runtime modularization while keeping root entrypoints and compatibility imports stable.
- Extracted live output/diff rendering into `local_agent/runtime/output.py`.
- Extracted host/process telemetry parsing/collection and the underlying RSS sampler into `local_agent/runtime/telemetry.py`.
- `agent_runtime.py` remains the staged executor/orchestrator and keeps the historical `_safe_command`/RSS sampling monkeypatch seam through a small compatibility adapter.

## v4.11.11

- Documentation and release-hygiene alignment only; no runtime behavior change.
- Removed stale hard-coded release text from the README and synchronized current control-probe/logging invariants.

## v4.11.10

- Applied concise multiline command descriptors to the production `RuntimeExecutor` path, including timeout and memory-limit diagnostics.
- Full command and bounded output evidence remains in run/result JSON.

## v4.11.9

- Made production operator logging concise by default.
- Successful internal Git housekeeping and ordinary control-repository lease contention no longer spam the daemon log.
- Added `LOCAL_AGENT_VERBOSE_LOGS=1` as a temporary low-level diagnostic override.

## v4.11.8

- Bounded launchd stdout/stderr log history.
- When idle, a log above 2 MiB is compacted in place to approximately the most recent 1 MiB with descriptor/path verification and append semantics preserved.

## v4.11.7

- Prevented global-control starvation under repeated control-repository lease contention.
- Added explicit `LEASE_BUSY` probe classification and a bounded drain after six consecutive lease-busy probes.

## v4.11.6

- Hardened verification/output behavior and retry/logging discipline.
- Added structured `stream`/`summary` output policy while preserving bounded terminal result evidence and watchdog behavior.
- Added bounded exponential retry and repeated-failure log gating for supervisor failure paths.
