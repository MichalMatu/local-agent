# Changelog

This changelog records operationally relevant Local Agent releases. Historical per-release notes through v4.11.5 remain available as `docs/RELEASE_NOTES_V4.11.x.md`. The release tag and `agent_version.RELEASE_VERSION` are the version source of truth.

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
