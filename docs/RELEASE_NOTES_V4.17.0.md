# Local Agent 4.17.0 release notes

Local Agent 4.17.0 completes the next package-ownership phase started in v4.16.0. The release is intentionally focused on code layout, ownership clarity and regression protection rather than changing the planner/task/control contract.

## What changed

### Reusable implementation moved under `local_agent/`

The following root implementations now have explicit packaged owners:

- execution core → `local_agent/foundation/core.py`;
- registered process/lease/durable-write foundation → `local_agent/foundation/process.py`;
- bounded control Git/storage policy → `local_agent/foundation/storage.py`;
- repository provisioning/validation → `local_agent/repository/admin.py`;
- repository runtime cleanup → `local_agent/repository/cleanup.py`;
- short-lived repository worker → `local_agent/repository/worker.py`;
- staged task executor → `local_agent/runtime/executor.py`;
- parallel repository worker → `local_agent/supervisor/worker.py`;
- diagnostics CLI implementation → `local_agent/cli/diagnostics.py`;
- release version → `local_agent/version.py`.

Large behavior-preserving moves reuse the previous implementation verbatim where possible. Package-specific edits are limited to ownership/import seams.

### Root files are now an explicit boundary

Historical import/executable names remain as thin aliases/shims where current runtime, tests or deployment entrypoints still use them. They are no longer implementation owners.

`tests/test_package_layout.py` now enforces:

1. each migrated root name resolves to exactly the same module object as its packaged owner;
2. compatibility sources remain strictly thin and cannot silently grow implementation again.

New implementation belongs in `local_agent/`, and new code should import packaged owners directly.

### Architecture documentation now matches code

`docs/ARCHITECTURE.md` and `AGENTS.md` now describe the real package map, ownership boundaries and remaining migration seams.

## Deliberately unchanged

Three location-sensitive production orchestrators remain in the repository root:

- `agentd.py` — daemon lifecycle, durable claims/results, control and validated self-update;
- `agent_parallel.py` — released bounded-parallel supervisor;
- `agent_multirepo.py` — serial fallback supervisor.

Their current restart/self-update/worker launch logic derives paths from `__file__`. Moving them without explicit path rewiring would be a runtime behavior change, so v4.17.0 does not perform a cosmetic relocation.

`local_agent/supervisor/scheduling.py` also remains a parity-protected extraction target. Production scheduling semantics still live in `agent_parallel.py`; the scheduler rewire is a future focused change.

## Runtime contract

This release does not intentionally change:

- task schema or immutable task identity;
- canonical repository/agent binding requirements;
- control branch paths or control actions;
- repository/resource admission semantics;
- timeout, idle, memory or stdout bounds;
- durable claim/result behavior;
- interrupted-task no-replay policy;
- publication behavior;
- Chat Bridge repository binding semantics;
- macOS launchd operating model.

No downstream task/control contract migration is required.

## Verification gate

The release candidate must pass the exact-head GitHub Actions matrix:

- Python compile;
- Ruff;
- Chat Bridge syntax/tests;
- full Python unit/integration suite;
- branch-aware coverage;
- Python 3.14 suite;
- macOS smoke suite.

The package-layout regression test is part of the normal Python suite.

## Follow-up architecture work

Future changes should proceed in small tested slices rather than by full-file rewrites:

1. rewire `agent_parallel.py` to the existing pure scheduling owner and remove duplicate scheduling logic;
2. extract parallel process/reaping logic into `local_agent/supervisor/processes.py`;
3. extract supervisor status/log-maintenance logic into `local_agent/supervisor/status.py`;
4. split daemon service/self-update ownership only with explicit root-entrypoint/restart-path coverage;
5. remove compatibility aliases once all current internal/test/deployment callers use packaged owners directly.
