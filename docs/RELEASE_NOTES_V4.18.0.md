# Local Agent v4.18.0

## Package cleanup

Implementation now lives entirely under `local_agent/`. The daemon moved to `daemon/service.py`; parallel and serial coordination live in `supervisor/orchestrator.py` and `supervisor/serial.py`. `paths.py` resolves the checkout consistently. Workers execute as package modules with explicit checkout cwd. Production uses `supervisor/scheduling.py` directly; duplicate scheduling policy and historical runtime reexports are removed.

Four root Python launchers remain, each limited to importing and invoking its packaged owner:

| File | Operational reason |
| --- | --- |
| `agent_entrypoint.py` | Installed guarded LaunchAgent and guard reexec |
| `agent_parallel.py` | Direct parallel installations and mode-preserving restart |
| `agent_multirepo.py` | Serial fallback, registry dispatch and serial restart |
| `agentd.py` | Direct daemon installations and daemon restart |

Removed root files: `agent_binding.py`, `agent_cleanup.py`, `agent_config.py`, `agent_core.py`, `agent_operator.py`, `agent_parallel_worker.py`, `agent_process.py`, `agent_remote_operator.py`, `agent_repo_admin.py`, `agent_repo_worker.py`, `agent_repository.py`, `agent_runtime.py`, `agent_storage.py`, `agent_version.py`, `agentctl.py`.

Operator, diagnostics and repository administration commands now use `python -m local_agent.operator.local`, `python -m local_agent.cli.diagnostics` and `python -m local_agent.repository.admin`. Imports use packaged owners directly. No root module aliases or runtime `__file__` mutation remain.

## Reaudit fixes

- Both workers recheck global disable after processing repository controls and before task selection.
- Nonregular or inaccessible local disable markers fail closed; malformed waiting-status JSON is handled explicitly.
- Control-binding versions require integer schema versions and unreadable bindings become admission errors.
- Remote operator fetches use a dedicated tracking ref and read the exact inspected commit, avoiding concurrent `FETCH_HEAD` races.
- The guard uses registered process spawning and cleans descendants after leader exit, signals and unexpected loop exceptions.
- Routine control synchronization no longer redirects global stdout into an unbounded buffer while task threads emit output.
- Self-update merges the inspected SHA, validates packaged sources, rolls back validation failures/exceptions and coordinates reexec through an installation lock. A durable original/candidate journal blocks startup and local enable after interrupted validation.
- Deferred-control integration coverage runs again with a correctly bound task and actual shared polling policy.

Watchdogs, bounded command capture, inherited leases, repository/task identities, resources, claim/result publication and no-replay semantics retain their contracts. The daemon lock filename remains `agentd.lock`. Version ownership is `local_agent.version.RELEASE_VERSION`.

## Upgrade and recovery

The already-running v4.17 updater names deleted files in its validation command and rejects this layout. Stop the installed service while disabled before moving the production checkout to this release. Restart from `~/local-agent` on `main`, verify disabled startup, then perform live E2E and explicit enable. Do not migrate registry identities or clear claims, results or checkpoints for this package cleanup.

Interrupted subsequent self-updates require the explicit journal recovery described in [operations](OPERATIONS.md#interrupted-self-update-recovery).

## Downstream audit

Audited on 2026-09-05, under `MichalMatu`:

| Repository / branch | File | Audited blob |
| --- | --- | --- |
| esp32s3_LiteGraph / main | AGENTS.md | `547a24096ea81271bd268167357eda9af5e10a56` |
| esp32s3_LiteGraph / main | LOCAL_AGENT_FLOW.md | `9fd430ed8340280d4a7e99b0e4278a67386cc5be` |
| esp32s3_LiteGraph / main | LOCAL_AGENT_AUTOPILOT.md | `601f9798de06bc7c8c96f4e5d403387cccb3eeb9` |
| growbox-ml-controller / main | AGENTS.md | `96e080e4d137afc6d8e3f53a81cbe75aa9ff6e44` |
| growbox-ml-controller / mvp/environment-controller | AGENTS.md | `a9999c7f9ec087c57f6dd2f2525871cb0aa14562` |
| MatrixHub / main | AGENTS.md | `741e6291878c67b328769bbc87b46063cfab7950` |
| MatrixHub / develop | AGENTS.md | `df8184f402af914bad8b9a4ce94ac5cf243000f9` |
| esp32_c6_zigbee / main | AGENTS.md | `62355c1f6191beef9a3415c8a7b3bebc629b1800` |

Growbox's development instructions referenced the removed version alias. Commit `7f8ed8588408fccdfcd2ed8b3531f40f530bb02f` updates both references to `local_agent/version.py`. Other audited instructions describe unchanged planner/task/control contracts and need no migration. Retained launcher references remain valid. Recovery details belong to canonical Local Agent operations rather than duplicated downstream instructions.

## Verification and release evidence

The exact candidate must pass `python scripts/verify.py` and `python scripts/verify.py --profile macos-smoke`. CI additionally checks branch coverage and Python 3.14. Focused coverage includes package identity/path resolution, restart arguments, binding rejection on both workers, real two-repository overlap/exclusion, inherited locks, control contention, signal cleanup, actual Git rollback and interrupted installation.

The matching GitHub release records the exact released SHA, test counts, CI run and live task/control receipts. Live gates include active cancellation, global disable, a probe remaining unclaimed while disabled, and healthy bound repositories after explicit enable.

## Remaining decomposition opportunities

The daemon service and parallel orchestrator remain substantial coordination modules. Further splitting requires focused ownership boundaries and process/recovery evidence; this release does not claim that file size alone is a defect. The four operational launchers are deliberate deployment boundaries, not compatibility import APIs.
