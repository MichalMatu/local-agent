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

Live evidence:
- read-only discovery on the real Samsung S22+ succeeds over wireless ADB; the observed transport changed from `192.168.0.100:34791` to `192.168.0.100:38871` while the device remained the same, and `adb mdns services` advertised the replacement `_adb-tls-connect._tcp` endpoint;
- therefore an Android wireless `IP:port` is an ephemeral transport locator, not a durable device identity and not, by itself, a scheduler resource identity; current project/hardware task policy remains `resources: []` unless a genuinely shared external resource needs cross-repository locking;
- the first real `adb identity` smoke exposed a Samsung-specific multiline value in the full `getprop` dump (`persist.sys.boot.reason.history`), proving that line-oriented parsing of the whole vendor property set was invalid;
- `f92feebd3b2dafe5e5de36f5e40d83ab25fa72ec` hardened identity inspection to request only the seven fixed identity properties under one shared operation budget;
- the post-fix real-device smoke passed both `adb identity` and bounded `adb logcat --lines 50`; identity reported Samsung SM-S906B, Android 16 and SDK 36;
- the first verified transfer smoke then exposed an Android-shell incompatibility in the remote SHA-256 helper; `a2808e0352d36c0d3958e12284712dee468a1a31` replaced the remote shell script with a fixed bounded command fallback (`sha256sum` -> `toybox sha256sum` -> `openssl dgst -sha256`);
- focused protocol coverage was consolidated into `test_adb_remote_files_io.py` at `cc234ddae3f44de21c1672b243684939531b35ce`, and exact-head CI run `37557974161` passed all canonical jobs;
- real-device verified push and pull then passed against `/data/local/tmp` with identical SHA-256 `621a50e0895562e3d0bd28423d88921023b274332ccf171417af406494409545`; the pulled local file was committed through literal `/private/tmp` because the capability intentionally rejects the symlinked macOS `/tmp` parent;
- the transfer smoke used live device discovery immediately before execution and left repository worktrees unchanged.

Hardening status before expansion:
- current discovery, identity, bounded logcat, verified push and verified pull paths all have real-device evidence;
- keep exact explicit serial targeting inside each operation, but rediscover ephemeral wireless transport immediately before use;
- keep the distinction between tool target identity and scheduler lock/resource identity explicit in the future Local Agent <-> Tool Runtime contract;
- defer wireless pair/connect/disconnect and broader general ADB authority until the existing-tool hardening phase is complete and the common Tool Runtime contract is defined.

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

Current bounds:
- both operations default to `max_bytes=512 MiB` and reject configured limits above the shared 16 GiB hard maximum;
- both CLIs expose explicit `--max-bytes` and `--timeout`; the default whole-operation timeout is 300 s;
- inspection shares one monotonic deadline across open/hash/stability verification and rejects a file that starts above the limit or grows past it while hashing;
- deployment shares one deadline across source validation, staging copy, fsync, commit, directory fsync and final SHA-256/size verification; a pre-commit timeout cleans the exact staging file, while any post-commit timeout is surfaced explicitly because the destination may require operator cleanup.

Tests: `host_ops_tests/unit/local_files/*`, CLI artifact tests.

Live hardening evidence:
- focused host task `local-agent-host-ops-artifact-bounds-focused-20261007-v5` passed compile, architecture/design gates, bounded inspect/deploy success, explicit size-limit failures, invalid-timeout failure and exact temporary-file cleanup;
- commit `48b34d36c3bf98e1f3d2ea01867d8198ead153ce` preserves atomic/no-clobber behavior while adding the bounds; exact-head CI run `37569437598` passed `absorbed-host-ops`, `test`, `coverage`, `bridge-browser`, `python-314` and `macos-smoke`.

Remaining hardening:
- inspection/deployment still need final effect/resource metadata classification as part of the cross-tool review.

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

Transfers use a shared whole-operation budget, 512 MiB default / 16 GiB hard maximum, staging, SHA-256 and size verification, explicit replace and cleanup evidence. No-clobber upload prefers a remote hard-link commit and falls back to a no-clobber rename when the target filesystem denies the hard link; the fallback verifies whether staging was consumed and fails closed if the destination appeared concurrently.

Tests: `host_ops_tests/unit/ssh/*`, `host_ops_tests/integration/ssh/*`, CLI SSH tests.

Live evidence:
- task `local-agent-host-ops-ssh-check-e2e-20261007-v1` passed against configured `termux-phone`;
- TCP `192.168.0.100:8022` connected successfully;
- pinned OpenSSH transport, strict host-key verification and configured public-key authentication succeeded;
- remote user was `u0_a520` and `identity_matches=true`;
- task `local-agent-host-ops-ssh-transfer-e2e-20261007-v1` then proved bounded `ssh exec` against the same target and reported the expected Termux environment: user `u0_a520`, home `/data/data/com.termux/files/home`, prefix `/data/data/com.termux/files/usr` and Bash under the Termux prefix;
- that first live transfer exposed a real Android/Termux filesystem defect in the no-clobber upload commit: `ln` returned `Permission denied` for the verified SCP staging file even though the destination did not exist;
- `5d6fe44415be47fe3a5225b4adcf2440b937f874` added a fail-closed `mv -n` fallback plus regression coverage for hard-link denial and a concurrent destination race; `3f3aa98c78b0209bdb641450c28e043671142fcc` preserved the same behavior while keeping the Host Ops design-budget gate green;
- exact-head CI run `37561609068` for `3f3aa98c78b0209bdb641450c28e043671142fcc` passed `absorbed-host-ops`, `test`, `coverage`, `bridge-browser`, `python-314` and `macos-smoke`;
- task `local-agent-host-ops-ssh-transfer-e2e-20261007-v2` then passed on that live revision: verified push and pull of one disposable 33-byte file both reported SHA-256 `fcfdcbeb2735095eb2049b7f426f38bd85d3adeab2e27a132160dcd6d6bbcfe2`, upload staging was cleaned, the pulled local directory was synced and the task had no timeout, truncation, background-process leak or repository edit;
- task `local-agent-host-ops-ssh-cleanup-verify-20261007-v1` independently confirmed that the exact two local disposable paths and the exact remote disposable path were absent after cleanup.

Hardening status before expansion:
- current `ssh check`, bounded `ssh exec`, verified push and verified pull paths all have live Termux evidence;
- `ssh exec` remains arbitrary-code-like authority for the future effect taxonomy;
- keep SSH target identity distinct from scheduler resource identity; the live tasks correctly used `resources: []`;
- retain integration coverage for host-key/authentication failures, interrupted transfer cleanup and no-clobber races;
- defer broader SSH capability expansion until the existing-tool hardening phase is complete and the common Tool Runtime contract is defined.

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

Live hardening evidence:
- `local-agent-host-ops-browser-owned-lifecycle-e2e-20261007-v1` passed isolated profile start/status/stop/status and exact cleanup against the installed Chrome without touching the operator's normal profile;
- `local-agent-host-ops-browser-owned-attach-e2e-20261007-v1` exposed a real post-absorption defect: all seven Playwright helper launchers still used the retired `host_ops...` module namespace;
- commit `5a836b8ea033e71250e50d43d91763efa023bb98` changed only those helper module paths to `local_agent.host_ops...` and added exact argv-module regressions; exact-head CI run `37565016584` passed every canonical job;
- retry v2 then exposed a second real absorption/provisioning defect: the Local Agent venv had no Playwright adapter and the inherited donor documentation pointed to a nonexistent `.[browser]` extra;
- commit `3479b067166e03a1d1d12e47f778553ee632bc89` restored a standalone optional pin in `requirements-host-ops-browser.txt` as `playwright==1.63.0`, kept it out of default `requirements-runtime.txt`, and corrected the install contract; exact-head CI run `37565697928` passed every canonical job;
- `local-agent-host-ops-browser-adapter-install-20261007-v1` installed and import-verified exactly `playwright==1.63.0` in the deployed Local Agent venv;
- `local-agent-host-ops-browser-owned-attach-e2e-20261007-v3` passed isolated session start, CDP target inventory, exact-page snapshot, `html`/`body` selector counts, worker diagnostics, missing-content-script readiness diagnosis, one guarded reload, one bounded not-recovered recovery cycle, stop and exact temporary-profile cleanup with no timeout, truncation, background-process leak or repository edit.

This live proof covers the existing-CDP and owned-session primitives without changing the production browser authority boundary. It did not install a Playwright-managed browser engine, so the disposable `browser probe` remains explicitly optional and was not host-proven in this slice.

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

The initial inventory baseline `3e5462881695ee54fd4aa6a6b201422b0326ef19` passed all canonical jobs. Phase-B hardening has since also passed exact-head CI at `f92feebd3b2dafe5e5de36f5e40d83ab25fa72ec`:
- `absorbed-host-ops`;
- `test`;
- `coverage`;
- `bridge-browser`;
- `python-314`;
- `macos-smoke`.

A real Mac read-only sweep additionally passed 12/12 maintained inspection operations (doctor, host, tool inspection, DNS/TCP, ADB discovery, macOS inventories, browser inspection and local artifact inspection) without writes, timeout, output truncation or leaked background processes.

This proves the current source and broad read-only host baseline are green; it does not replace missing write-path, removable-media or remote-host smokes.

## Hardening queue before Tool Runtime contract

### P0 — contract correctness

No known current P0 data-loss or authority bypass was found in this inventory. Treat any newly discovered wrong-target execution, lease/resource escape, unbounded replay or destructive no-clobber violation as P0 and stop consolidation until fixed.

### P1 — normalize execution semantics

1. Whole-operation budgets are complete for host-profile composition and direct macOS inspection/storage operations at `6d2241da0f6c7709cc6502c2cfa6bd960c847014`; the composed removable-media workflow still needs one shared deadline across inspect/mount/deploy/eject.
2. Explicit local artifact size/time bounds are complete at `48b34d36c3bf98e1f3d2ea01867d8198ead153ce`.
3. Define current operation effect classes accurately: passive read, active network/device read, local process execution, write/mutation, disruptive device/storage effect, arbitrary-code-like execution.
4. Record canonical resource identity for serial ports, ADB devices, disks, remote SSH targets and remote-Git workspace/lock scopes.
5. Verify JSON success/error shape consistency across CLI groups before freezing a shared tool result contract.

### P1 — physical / integration proof

1. ADB real-device verified push/pull (discovery, identity and bounded logcat are complete).
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
