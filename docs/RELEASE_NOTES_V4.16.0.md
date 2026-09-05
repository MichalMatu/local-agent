# Local Agent 4.16.0

Local Agent 4.16.0 is an architecture and operational-maintainability release. It preserves the current planner/task contract while moving implementation ownership into explicit packages, strengthening verification and making macOS deployment portable.

## Highlights

- Added `pyproject.toml` and `scripts/verify.py` as the executable verification source of truth used by CI.
- Added branch-aware coverage reporting and targeted tests for guarded entrypoint, parallel worker/resource admission, remote emergency control and diagnostic CLI paths.
- Moved timeout configuration to `local_agent/config.py`.
- Moved repository hard binding and repository identity/registry implementation to `local_agent/repository/`.
- Moved persistent local and remote emergency-control implementation to `local_agent/operator/`.
- Moved guarded service implementation to `local_agent/entrypoint.py`; root `agent_entrypoint.py` is now an executable/import shim.
- Extracted external-resource flock/FD handling to `local_agent/supervisor/resources.py`.
- Added directly tested pure scheduling policy in `local_agent/supervisor/scheduling.py` as the boundary for continued decomposition of the parallel supervisor.
- Replaced tracked machine-specific LaunchAgent plist files with generated portable macOS configuration via `scripts/macos_launchd.py`.
- Separated non-disruptive LaunchAgent `install` from explicit disruptive `restart`.
- Added current architecture, contribution and PR-safety documentation.

## Compatibility and planner contract

This release does not change the existing task schema, hard-binding contract, resource declarations, control branch paths, result/status schema or Chat Bridge conversation binding semantics. Downstream project planner documentation therefore requires no contract migration for 4.16.0.

Root compatibility import surfaces remain where existing runtime/tests still depend on them. New implementation should target the packaged owners documented in `docs/ARCHITECTURE.md` rather than add new logic to compatibility shims.

## Verification

The refactor was validated with:

- Python compile checks;
- Ruff;
- Chat Bridge syntax/tests;
- full Python unit/integration tests;
- Python 3.14 compatibility tests;
- branch-aware coverage measurement;
- macOS process/checkpoint/multi-repository/binding/emergency-control smoke tests.

The pre-release branch reached 328+ tests with total branch-aware coverage around 69%, while critical extracted components reached substantially higher targeted coverage (including remote emergency control and pure scheduling policy above 90%). Coverage remains a risk map rather than a release percentage target.

## macOS deployment

Generate or install the LaunchAgent from the current checkout instead of using tracked per-user plist files:

```bash
.venv/bin/python scripts/macos_launchd.py render
.venv/bin/python scripts/macos_launchd.py install --mode parallel --max-workers 2
```

`install` does not intentionally interrupt the running service. Use an explicit restart only at a safe idle boundary:

```bash
.venv/bin/python scripts/macos_launchd.py restart --mode parallel --max-workers 2
```

## Release validation

After merge to `main`, verify that the live daemon reports:

- `daemon_version: 4.16.0`;
- `self_revision` equal to the released `main` commit;
- idle/healthy status before queueing new work;
- successful execution of one real bound task after restart/self-update.
