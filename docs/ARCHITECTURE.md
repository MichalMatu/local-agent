# Local Agent architecture

> **Design goal:** keep planning outside the executor and make local execution deterministic, bounded, observable and recoverable.

This document describes the current code ownership boundaries. Runtime truth still comes from `main`, `AGENTS.md`, operational documentation and live daemon evidence.

## System boundary

```mermaid
flowchart LR
    Planner["ChatGPT / planner"]
    Bridge["Chat Bridge"]
    Control["Git control plane"]
    Entry["Guarded entrypoint"]
    Supervisor["Supervisor"]
    Worker["Repository worker"]
    Runtime["Task runtime"]
    Repo["Project repository"]
    Results["Durable result / status"]
    Operator["Local + remote operator controls"]

    Bridge --> Planner
    Planner -->|exact immutable task| Control
    Control --> Supervisor
    Operator --> Entry
    Entry --> Supervisor
    Supervisor --> Worker
    Worker --> Runtime
    Runtime --> Repo
    Runtime --> Results
    Results --> Control
```

The planner chooses intent. The executor independently owns repository identity, hard binding, resource admission, process lifecycle, watchdogs, checkpoints, publication and emergency stop.

## Package map

```text
local_agent/
├── __init__.py
├── config.py
├── paths.py
├── entrypoint.py
├── version.py
├── cli/
│   └── diagnostics.py
├── daemon/
│   ├── installation.py
│   └── service.py
├── foundation/
│   ├── core.py
│   ├── process.py
│   └── storage.py
├── operator/
│   ├── local.py
│   └── remote.py
├── platform/
│   └── macos_launchd.py
├── repository/
│   ├── admin.py
│   ├── binding.py
│   ├── cleanup.py
│   ├── context.py
│   └── worker.py
├── runtime/
│   ├── executor.py
│   ├── output.py
│   ├── progress.py
│   ├── task_contract.py
│   └── telemetry.py
└── supervisor/
    ├── control.py
    ├── policy.py
    ├── orchestrator.py
    ├── serial.py
    ├── resources.py
    ├── scheduling.py
    └── worker.py
```

The package is the implementation home for reusable code. New implementation must not be added to a root compatibility module when a packaged owner exists.

## Ownership boundaries

| Area | Owner | Responsibilities |
| --- | --- | --- |
| Installation transaction | `local_agent/daemon/installation.py` | installation lock, durable pending revisions and fail-closed admission after interrupted validation |
| Daemon service | `local_agent/daemon/service.py` | lifecycle, durable claims/results, control and validated self-update |
| Parallel orchestration | `local_agent/supervisor/orchestrator.py` | worker admission/reaping, control draining, status and shutdown |
| Serial fallback | `local_agent/supervisor/serial.py` | serial repository polling and mode-preserving restart |
| Checkout paths | `local_agent/paths.py` | explicit source checkout resolution, independent of cwd |
| Release version | `local_agent/version.py` | one release version constant |
| Runtime configuration | `local_agent/config.py` | startup-loaded timeout policy |
| Execution core | `local_agent/foundation/core.py` | deterministic task execution, workspace preparation/checkpointing and result publication |
| Process foundation | `local_agent/foundation/process.py` | registered spawning, process groups, bounded stdout, durable writes and inherited lease FDs |
| Storage foundation | `local_agent/foundation/storage.py` | bounded control Git sync, resilient network retry and storage diagnostics |
| Repository identity | `local_agent/repository/context.py` | registry parsing, workspace identity, config digests and lease keys |
| Hard binding | `local_agent/repository/binding.py` | canonical UUID identity and control-binding validation |
| Repository administration | `local_agent/repository/admin.py` | explicit provisioning and checkout validation |
| Repository runtime cleanup | `local_agent/repository/cleanup.py` | bounded terminal metadata GC with path-exact publication |
| Repository worker | `local_agent/repository/worker.py` | one isolated repository turn, binding admission and repository-scoped controls |
| Task executor | `local_agent/runtime/executor.py` | staged command lifecycle, time/RSS watchdog orchestration and task-level execution budget |
| Task contract | `local_agent/runtime/task_contract.py` | task limits, digest/binding/resource validation |
| Output | `local_agent/runtime/output.py` | bounded live/summary rendering |
| Progress | `local_agent/runtime/progress.py` | validated progress markers and bounded async publication |
| Telemetry | `local_agent/runtime/telemetry.py` | host/process telemetry parsing and collection |
| Local emergency state | `local_agent/operator/local.py` | persistent disable marker, disabled-only runtime reset and binding migration |
| Remote emergency intent | `local_agent/operator/remote.py` | central operator desired-state polling and fail-closed validation |
| Guarded service lifecycle | `local_agent/entrypoint.py` | operator polling plus safe supervisor start/stop/reexec |
| Diagnostics CLI | `local_agent/cli/diagnostics.py` | status, task inspection, task validation and doctor checks |
| Supervisor policy | `local_agent/supervisor/policy.py` | shared polling/order/control policy |
| Production scheduling | `local_agent/supervisor/scheduling.py` | pure retry/due/backoff/max-worker policy consumed directly by the parallel orchestrator |
| Resource admission | `local_agent/supervisor/resources.py` | machine/named-resource flock arbitration and inherited resource FDs |
| Parallel repository worker | `local_agent/supervisor/worker.py` | resource-aware parallel task admission and dispatch |
| macOS integration | `local_agent/platform/macos_launchd.py` | portable LaunchAgent generation/lifecycle helpers |

## Root boundary

All implementation lives under `local_agent/`. Four root Python files remain as operational launchers, with no module aliases or `__file__` mutation:

| Launcher | Operational requirement |
| --- | --- |
| `agent_entrypoint.py` | installed guarded LaunchAgent and guard self-reexec |
| `agent_parallel.py` | existing direct parallel LaunchAgents and parallel self-update/restart |
| `agent_multirepo.py` | serial LaunchAgent, daemon registry dispatch and serial restart |
| `agentd.py` | single-daemon LaunchAgent and daemon self-update/restart |

Keeping these filenames preserves installed launchd configuration and explicit restart commands. The v4.17 updater still needs an operator-managed transition because its in-memory validator names deleted files; see [v4.18 release notes](RELEASE_NOTES_V4.18.0.md). They are executable boundaries, not supported import APIs. All other root aliases and worker/admin/diagnostic/operator shims are removed.

Workers run as package modules with an explicit checkout cwd. Direct supervisor module invocation is also supported. Restart uses an absolute launcher under `repository_root()` and preserves the exact serial/parallel mode, registry, one-shot flag and worker count. The daemon's `SELF_REPO` uses the same resolver for Git revision and self-update. Installed-update compile discovery delegates to `scripts/verify.py --only compile`; validation still isolates HOME, strips lease metadata, bounds each command and runs the full Python suite before accepting an update.

The guard and updater serialize source acceptance through an installation lock. The updater records both revisions durably before installing the inspected commit. Validation failure rolls back; interrupted validation leaves a journal that blocks supervisor startup and local enable until operator recovery. The guard keeps emergency polling active while validation is running. See [operations](OPERATIONS.md#interrupted-self-update-recovery).

`tests/test_package_layout.py` enforces this boundary and tests launcher/module execution and restart paths. The launchd generator keeps the installed launcher contract and validates packaged runtime files before installation.

## Dependency direction

The intended direction is:

```mermaid
flowchart TD
    Root["operational root launchers"] --> Supervisor["local_agent.supervisor"]
    Root --> Repo["local_agent.repository"]
    Root --> Runtime["local_agent.runtime"]
    Root --> Operator["local_agent.operator"]
    Supervisor --> Repo
    Supervisor --> Runtime
    Supervisor --> Foundation["local_agent.foundation"]
    Repo --> Foundation
    Runtime --> Foundation
    Operator --> Repo
    Operator --> Foundation
```

Packaged modules and tests import packaged owners directly. Imports of root launcher names are unsupported and prohibited.

## Remaining decomposition opportunities

The daemon service and parallel orchestrator are still substantial coordination modules. A future change may extract daemon update operations or supervisor process/status handling when it creates a clean ownership boundary. This refactor deliberately keeps claim/result, update rollback, resource admission, control drain and shutdown behavior together with their existing tests.

The scheduling extraction is complete: production calls `scheduling.py` directly and the duplicate policy is removed. Scheduling tests now exercise that owner; supervisor and temporary-Git integration tests exercise its production consumers.

## Safety invariants that layout work must not weaken

> [!CAUTION]
> Refactoring file layout is never a reason to weaken an executor invariant.

- repository/control/task agent bindings must match before execution;
- global disabled state takes precedence over task admission;
- interrupted claimed work is never silently replayed;
- publication retry may republish evidence but may not rerun commands;
- command output, task time and RSS remain bounded;
- repository and resource lease FDs remain inherited through descendants;
- resource contention occurs before claim and remains durable waiting;
- global maintenance drains active workers and acquires repository identities;
- remote operator `enabled` never clears the persistent local disable marker;
- dirty workspaces are never destructively replaced without recoverable evidence;
- daemon/self-update and supervisor restart paths must still resolve to the installed root checkout.

## Verification architecture

The executable verification source of truth is:

```bash
python scripts/verify.py
```

```mermaid
flowchart LR
    Verify["scripts/verify.py"] --> Compile["Python compile"]
    Verify --> Ruff["Ruff"]
    Verify --> Bridge["Chat Bridge syntax + tests"]
    Verify --> Python["Python unit/integration"]
    CI["GitHub Actions"] --> Verify
    CI --> Coverage["branch-aware coverage"]
    CI --> Py314["Python 3.14"]
    CI --> Mac["macOS smoke"]
```

Package-layout changes additionally require `tests/test_package_layout.py` to stay green so moved implementations cannot silently grow back into root shims.

Coverage remains a risk map, not a vanity gate. Lower-covered orchestration and shutdown paths deserve targeted tests before cosmetic decomposition.

## macOS service boundary

Tracked machine-specific plist files are replaced by generated configuration:

```bash
.venv/bin/python scripts/macos_launchd.py render
.venv/bin/python scripts/macos_launchd.py install --mode parallel --max-workers 2
.venv/bin/python scripts/macos_launchd.py restart --mode parallel --max-workers 2
```

`install` is intentionally non-disruptive. `restart` is the explicit service interruption boundary.

## Browser transport boundary

`chat_bridge/service_worker.js` owns serialized persistent state, runtime catalog admission, durable delivery authorization and per-conversation scheduling. `content.js` owns DOM interaction and observable delivery confirmation. `bridge_state.js` owns state normalization; `control_protocol.js` owns marker/identity parsing; `popup.js` owns explicit operator actions. Content messages cannot invoke popup-only configuration or Rebind operations. A pending delivery survives worker restart and blocks replay until operator resolution.

The planner chooses direct GitHub edits with sufficient diff/CI evidence or bounded local execution. Neither the Bridge nor the daemon chooses implementation work. See [the planner contract](AUTONOMOUS_CHAT_LOOP.md) and [the Bridge audit](RELEASE_NOTES_V4.18.1.md).
