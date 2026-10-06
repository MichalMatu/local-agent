# Host Ops Tool Inventory

Status: **canonical current-tool inventory for the consolidation phase**.

Inventory baseline: `local-agent@3e5462881695ee54fd4aa6a6b201422b0326ef19`.

This document describes what exists today. It is not the future Tool Runtime schema and does not broaden any authority. The development order remains:

```text
inventory
  -> debug / test / harden existing tools
  -> define Local Agent <-> Tool Runtime contract
  -> migrate existing tools without semantic drift
  -> expand capabilities
  -> future ChatGPT plugin UX over GitHub-backed control/evidence
```

GitHub remains the only durable ChatGPT <-> Local Agent control/evidence plane. No MCP server or direct ChatGPT-to-Local-Agent execution transport is part of this direction.

## Ownership model

Current Host Ops keeps the dependency direction:

```text
cli -> workflows -> capabilities -> core
cli -------------> capabilities -> core
```

Local Agent owns planning, task/repository admission, scheduling, resource arbitration, watchdogs and durable execution evidence. Host Ops owns deterministic validation, machine/remote effects and bounded structured results.

Conversation Fabric remains orchestration. Browser/chat-UI lifecycle effects may eventually share the same internal tool contract, but delegation policy, campaign ownership, retry/retire semantics, Result Vault and synthesis remain outside Host Ops.

## Shared execution primitives

| Primitive | Canonical owner | Current contract | Main hardening concern |
| --- | --- | --- | --- |
| bounded child process | `core/execution/process.py::ProcessRunner` | argv-only, no shell, bounded stdout/stderr, timeout, process-group cleanup, normalized `ProcessResult` | establish consistent whole-operation budgets above multi-process capabilities |
| detached managed process | `core/execution/process.py::DetachedProcessSpawner` | POSIX detached process, sanitized Local Agent lease environment | keep restricted to explicit lifecycle-owning capabilities |
| execution limits | `core/execution/limits.py::ExecutionLimits` | finite timeout, termination/drain grace, stdout/stderr byte limits | future tool contract should carry these semantics explicitly |
| host configuration | `core/config/*` | validated aliases/endpoints; no credential material | current model is SSH-oriented and should not become a universal target registry by accident |
| diagnostics | `core/diagnostics/*` | prerequisite checks and structured doctor evidence | keep diagnostic checks distinct from tool execution authority |

## Current user-visible operations

### ADB

Canonical capability: `capabilities/local/adb/*`.

| Operation | CLI | Effect class today | Result / identity | Current bounds / evidence |
| --- | --- | --- | --- | --- |
| device discovery | `adb devices` | active read | `AdbDevice`; explicit serial/state | default 10 s, bounded output; unit coverage |
| device identity | `adb identity SERIAL` | active read | `AdbIdentity`; exact serial | shared 10 s operation budget; ready/non-ready/unknown/malformed tests |
| recent logs | `adb logcat SERIAL` | active read | `AdbLogcatResult` | 1..10,000 lines; shared deadline; focused tests |
| verified push | `adb push SERIAL LOCAL REMOTE` | device write | `AdbTransferResult` | 300 s default whole-transfer budget; 512 MiB default, 16 GiB hard max; digest/size/staging verification |
| verified pull | `adb pull SERIAL REMOTE LOCAL` | local filesystem write | `AdbTransferResult` | same transfer budget/size limits; atomic/no-clobber local commit |

Tests: `host_ops_tests/unit/local_adb/*`, CLI tests in `host_ops_tests/unit/cli/test_adb*.py`.

Hardening before expansion:
- add real-device smoke for discovery/identity/logcat and verified push/pull;
- classify device-scoped resource identity explicitly;
- keep exact serial targeting;
- only after the current surface is proven, expand toward wireless pair/connect/disconnect and broader general ADB operations.

### Generic host and executable inspection

Canonical capabilities: `capabilities/local/host/*`, `capabilities/local/tools/*`.

| Operation | CLI | Effect | Notes |
| --- | --- | --- | --- |
| host profile | `host profile` | read | hostname/OS/CPU/memory/root storage plus GPU discovery |
| executable inspection | `tools inspect TOOL...` | **executes local code** | resolves executable then runs `--version`; must not be classified as passive read merely because it reports metadata |

Tests: `host_ops_tests/unit/local_host/*`, `host_ops_tests/unit/local_tools/*`, corresponding CLI tests.

Hardening:
- standardize one whole-profile deadline rather than independent native-probe deadlines where practical;
- future effect taxonomy must distinguish metadata reads from local process execution.

### Network

Canonical capability: `capabilities/local/network/*`.

| Operation | CLI | Effect | Bounds |
| --- | --- | --- | --- |
| DNS resolution | `network resolve HOST` | externally observable read/network effect | default 5 s, max 60 s; isolated worker |
| TCP probe | `network tcp HOST PORT` | active network connection | one explicit endpoint only; default 5 s, max 60 s |

Tests: `host_ops_tests/unit/local_network/*` including loopback success/refusal behavior.

Hardening:
- future tool contract should identify network effect separately from pure reads;
- preserve no-scan semantics at current boundary until broader discovery is intentionally designed.

### Serial

Canonical capability: `capabilities/local/serial/*`.

Operation: `serial transact PORT --baud ...`.

Effect: read or device write depending on payload. Opening/configuring the port itself may affect/reset hardware.

Current contract:
- explicit absolute device path below `/dev`;
- baudrate and optional text/hex write;
- whole transaction deadline;
- response byte cap and idle completion;
- raw POSIX 8N1 transport only.

Tests: unit validation plus real PTY integration in `host_ops_tests/integration/local_serial/test_posix_serial.py`.

Hardening:
- add physical-device smoke;
- future resource identity should be the resolved serial device;
- classify read-only and write transactions differently.

### macOS host/device/storage

Canonical capability: `capabilities/local/macos/*`.

| Operation | CLI | Effect |
| --- | --- | --- |
| host facts | `macos host` | read |
| USB inventory | `macos usb` | read |
| serial inventory | `macos serial` | read |
| external storage inventory | `macos storage` | read |
| mount | `macos mount IDENT` | storage mutation |
| unmount | `macos unmount IDENT` | disruptive storage mutation |
| eject | `macos eject IDENT` | disruptive whole-disk mutation |
| verified media deployment | `macos deploy-media IDENT SOURCE` | composite mount/write/optional eject workflow |

Guards include explicit `diskN`/`diskNsN` identity and fail-closed confirmation that targets are external; eject requires a whole disk.

Tests: `host_ops_tests/unit/macos/*`, CLI storage/removable-media tests.

Hardening:
- add physical removable-media integration smoke;
- convert multi-command storage workflows from per-process timeout reuse to a true whole-operation budget;
- local artifact copy inside `deploy-media` currently has no independent wall-clock/size budget.

### Local artifacts/files

Canonical capability: `capabilities/local/files/*`.

| Operation | CLI | Effect | Result |
| --- | --- | --- | --- |
| inspect artifact | `artifact inspect SOURCE` | filesystem read | `ArtifactInspectionResult` with real path, size, SHA-256, mtime |
| deploy artifact | `artifact deploy SOURCE DESTDIR` | filesystem write | `ArtifactDeploymentResult` with SHA-256, size, replace flag, directory-fsync evidence |

The implementation rejects symlink sources/target directories, stages in the destination directory, fsyncs data, supports explicit replace/no-clobber commit and verifies the final digest.

Tests: `host_ops_tests/unit/local_files/*`, CLI artifact tests.

Hardening:
- no wall-clock or maximum-size bound exists for local hash/copy operations;
- inspection/deployment should eventually expose explicit effect/resource metadata while preserving current atomicity semantics.

### Local Git context

Canonical capability: `capabilities/local/git/client.py::LocalGitClient`.

This is currently a supporting capability rather than a top-level standalone CLI tool. It is used by remote-Git `prepare-current` / `run-current`.

Current behavior:
- resolve repository root;
- optionally require a clean tracked/untracked worktree;
- resolve exact `HEAD^{commit}`;
- resolve one named remote URL.

Effect: invokes local Git processes but does not mutate the repository.

Tests: `host_ops_tests/unit/local_git/test_local_git_client.py`.

Hardening:
- classify as process-backed local inspection rather than pure filesystem read;
- preserve exact-revision reproducibility and clean-worktree semantics.

### SSH

Canonical capability: `capabilities/remote/ssh/*`.

| Operation | CLI | Effect |
| --- | --- | --- |
| transport/user check | `ssh check TARGET` | remote command read |
| remote execution | `ssh exec TARGET ARGV...` | **general remote code execution** |
| verified upload | `ssh push TARGET LOCAL REMOTE` | remote filesystem write |
| verified download | `ssh pull TARGET REMOTE LOCAL` | local filesystem write + remote read |

Transport is pinned to system OpenSSH with `-F /dev/null`, strict host-key checking, explicit identity file/user, public-key-only authentication, disabled forwarding/agent mutation/control multiplexing and bounded `ProcessRunner` execution.

Transfers use a shared whole-operation budget, 512 MiB default / 16 GiB hard maximum, staging, SHA-256 and size verification, explicit replace and cleanup evidence.

Tests: `host_ops_tests/unit/ssh/*`, `host_ops_tests/integration/ssh/*`, CLI SSH tests.

Hardening:
- `ssh exec` must be modeled as arbitrary-code-like authority in the future effect taxonomy;
- resource identity should be the resolved remote target;
- add/retain integration coverage for host-key/authentication failures and interrupted transfer cleanup.

### Remote Git workflows

Canonical workflow: `workflows/remote_git/*`.

| Operation | CLI | Effect |
| --- | --- | --- |
| exact revision prepare | `remote git prepare` | remote filesystem/Git mutation |
| prepare + project command | `remote git run` | remote arbitrary command after exact revision preparation |
| derive from local checkout | `remote git prepare-current` | local Git inspection + remote mutation |
| derive + run | `remote git run-current` | local inspection + remote arbitrary execution |
| cache inventory | `remote git cache list` | remote read |
| cache removal | `remote git cache remove` | destructive remote filesystem mutation |

Important current invariants:
- full lowercase 40/64-hex revision only;
- exact repository URL/workspace binding;
- fetched commit reachability proof;
- hard reset/clean before revision transitions;
- workspace and optional host-wide `flock`;
- readiness marker required;
- symlink/type checks for cache/workspace/lock state.

Tests: `host_ops_tests/unit/workflows/test_remote_git*.py`, CLI remote-Git tests.

Hardening:
- make remote workspace and optional heavy-job lock identities explicit future resources;
- keep `run` classified as arbitrary-code-like, not merely a Git workflow;
- review whether the single SSH process timeout is sufficient as a semantic whole workflow deadline for long remote commands.

### Removable-media workflow

Canonical workflow: `workflows/removable_media/deploy.py::MacOSRemovableMediaDeployer`.

Composition:
`external storage inspect -> optional mount -> verified local artifact deploy -> optional eject`.

Result: `RemovableMediaDeploymentResult`; failures retain stage and already-completed side-effect evidence through `RemovableMediaDeploymentError`.

Hardening:
- true end-to-end operation budget;
- explicit target-disk resource identity;
- physical-media smoke including partial failure after mount/deploy.

## Host Ops browser operations

Canonical capability: `capabilities/local/browser/*`.

Current user-visible groups include:
- browser process/loopback DevTools inspection;
- disposable managed one-navigation probe;
- persistent managed-session start/status/stop;
- interactive owned-session start/status/stop;
- CDP attach target inventory;
- exact-page snapshot;
- selector counts;
- extension/DOM readiness;
- worker/service-worker diagnostics;
- exact URL-guarded reload;
- bounded content-script recovery built from readiness + at most one reload.

Focused coverage lives in `host_ops_tests/unit/local_browser/*` plus CLI tests and the repository's browser smoke gates.

Current production boundary remains intentionally narrower than general page automation. Broader browser automation should only be considered after the existing browser and Chat Bridge primitives are normalized and hardened.

## Chat Bridge primitives that are semantic Tool Runtime candidates

These operations are deterministic browser/chat-UI effects, but **their current production implementation stays in the extension** because that is where the authenticated primary-Chrome authority exists today.

| Semantic primitive | Current owner |
| --- | --- |
| create/recover exact child tab | `chat_bridge/worker_spawn.js` |
| write/submit exact prompt | `chat_bridge/spawn_content.js`, parent-feedback equivalents in `content.js` / `conversation_fabric_content.js` |
| observe route/ownership | `worker_spawn_route_transition.js`, `worker_spawn.js` |
| read bounded child result | `spawn_result_content.js`, `worker_spawn_result.js` |
| close exact owned tab | `worker_spawn_result.js` |

These are candidates for a common **semantic** tool contract later. They must not be physically moved into Python Host Ops by inventing a new Local-Agent-to-browser RPC or second control transport.

## Conversation Fabric responsibilities that are not tools

The following stay with Local Agent / Conversation Fabric:
- decide whether/how many children to delegate;
- campaign identity, capacity and ownership;
- child role/prompt policy;
- retry, ambiguity recovery and retirement policy;
- stable-result adoption rules;
- Result Vault retention;
- campaign completion and terminal feedback;
- synthesis and next-step reasoning.

A future Tool Runtime may execute browser/chat primitives for those workflows; it must not own the reasoning workflow itself.

## Current verification baseline

At inventory closeout the exact-head CI for `3e5462881695ee54fd4aa6a6b201422b0326ef19` passed all canonical jobs:
- `absorbed-host-ops`;
- `test`;
- `coverage`;
- `bridge-browser`;
- `python-314`;
- `macos-smoke`.

This proves the current source baseline is green; it does not replace missing real-device/media/remote-host smokes.

## Hardening queue before Tool Runtime contract

### P0 — contract correctness

No known current P0 data-loss or authority bypass was found in this inventory. Treat any newly discovered wrong-target execution, lease/resource escape, unbounded replay or destructive no-clobber violation as P0 and stop consolidation until fixed.

### P1 — normalize execution semantics

1. Introduce true whole-operation budgets where a user operation spans multiple subprocesses or subprocess + local I/O, especially macOS storage/removable-media and host-profile composition.
2. Add explicit size/time bounds for local artifact hashing/copying.
3. Define current operation effect classes accurately: passive read, active network/device read, local process execution, write/mutation, disruptive device/storage effect, arbitrary-code-like execution.
4. Record canonical resource identity for serial ports, ADB devices, disks, remote SSH targets and remote-Git workspace/lock scopes.
5. Verify JSON success/error shape consistency across CLI groups before freezing a shared tool result contract.

### P1 — physical / integration proof

1. ADB real-device discovery/identity/logcat/push/pull.
2. macOS removable-media inspect/mount/deploy/eject.
3. one physical serial-device transaction.
4. bounded real SSH target check/exec/transfer path.
5. browser/Chat Bridge live normal-Chrome acceptance when lifecycle code changes.

### P2 — cleanup and duplication

1. inventory duplicated validation/rendering between CLI and capability layers;
2. normalize repeated operation-budget helpers after semantics are proven;
3. standardize browser/chat-UI primitive result names without changing extension execution locality;
4. remove obsolete narrow-boundary wording only when the capability is actually expanded.

## Exit criteria for the inventory/hardening phase

Do not introduce the shared Tool Runtime registry merely because the inventory exists.

Proceed to the Local Agent <-> Tool Runtime contract only when:
- every maintained operation has a canonical owner and effect/resource classification;
- current success/failure JSON contracts are documented and tested;
- P1 timeout/boundary inconsistencies are either fixed or explicitly accepted;
- hardware/remote operations have at least one realistic smoke path where feasible;
- Chat Bridge primitive ownership is separated from Conversation Fabric orchestration;
- exact-head CI remains green.
