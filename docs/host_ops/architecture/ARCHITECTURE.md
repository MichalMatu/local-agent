# Architecture

## Purpose

`host-ops` is a deterministic capability/workflow layer beneath Local Agent. It contains no LLM loop, autonomous planner, retry agent or second scheduler.

```text
ChatGPT / planner
    |
    v
Local Agent
- repository/binding identity
- task/resource scheduling
- watchdogs and execution evidence
    |
    v
host-ops
- stable CLI
- reusable workflows
- deterministic capabilities
- structured bounded results
```

## Package ownership

```text
local_agent/host_ops/
  core/
    config/
    execution/
    diagnostics/

  capabilities/
    local/
      adb/
      browser/
      git/
      host/
      files/
      macos/
      network/
      serial/
    remote/
      ssh/

  workflows/
    remote_git/
    removable_media/

  cli/
    commands/
```

Directories are created only when a real responsibility lands.

### `core`

Owns dependency-light contracts and shared execution behavior:

- validated configuration;
- process lifecycle and cleanup;
- time/output bounds;
- normalized process results;
- generic diagnostics/redaction.

Core must never import concrete capabilities or workflows.

### `capabilities`

Each concrete capability owns one external integration boundary and translates a narrow intent into effects using core primitives.

Current capabilities:

- `capabilities.local.adb`: bounded Android discovery, fixed identity/logcat inspection and verified file transfer for an explicit serial;
- `capabilities.local.browser`: bounded browser/process inspection, explicit Chromium CDP diagnostics and guarded reload/recovery, isolated persistent/interactive session process control, plus an optional disposable one-navigation Playwright probe;
- `capabilities.local.git`: read-only local repository facts (root, selected remote URL, exact `HEAD`, clean-state requirement);
- `capabilities.local.host`: generic hostname/OS/CPU/memory/root-storage facts without dispatch policy;
- `capabilities.local.files`: local artifact inspection plus one-file deployment with explicit destination identity, SHA-256 verification, staged write, fsync and atomic replacement;
- `capabilities.local.macos`: native macOS host/USB/serial/storage inspection plus guarded mount/unmount/eject for explicitly identified external storage targets;
- `capabilities.local.network`: bounded DNS resolution and one explicit TCP endpoint probe;
- `capabilities.local.serial`: bounded POSIX TTY transactions with explicit device path, baudrate, write/read limits, whole-transaction deadline and response-idle completion;
- `capabilities.remote.ssh`: OpenSSH transport semantics plus bounded verified push/pull.

The local Git capability does not know about remote workspace naming or remote execution. The local host capability reports facts without dispatch policy. The local network capability probes only one explicit endpoint. The browser capability owns browser-process/session identity and the documented bounded inspection/diagnostic/reload boundaries, but not general page automation. The ADB capability is device-scoped and exposes fixed inspection plus verified one-file transfer, not arbitrary shell/package/reboot authority. The local file capability does not know whether a target directory belongs to removable media, a project or another application. The macOS capability owns `diskutil` target validation and storage effects, but it does not own artifact contents or firmware policy. The serial capability owns raw 8N1 byte transport only; it does not know device protocols, command syntax, firmware or flashing policy. The SSH capability does not know about Git repositories, builds or tests.

Concrete sibling capabilities do not import each other's private implementation. Capabilities do not import application workflows.

### `workflows`

Own reusable deterministic composition that is larger than one adapter operation but still contains no planning.

Current workflows: `workflows.remote_git` and `workflows.removable_media`.

It provides:

- remote workspace identity derived from the effective worker-visible repository URL;
- binding of each cached workspace to one exact repository URL;
- dedicated cached Git workspaces;
- mandatory workspace locking plus optional host-wide locking;
- exact full-SHA remote provenance and checkout verification;
- cleanup before and after revision changes;
- selectable worktree/full clean mode;
- caller-supplied foreground command argv executed from the verified checkout;
- lock-aware remote cache inventory and explicit single-workspace removal.

`workflows.removable_media` composes public macOS storage and local-file capabilities for one explicit external volume: inspect, mount only when needed, deploy one verified artifact, and optionally eject the containing whole disk after successful deployment. It does not format media or infer firmware/device policy.

The explicit workflow input is repository URL + exact revision + workspace identity. The CLI may obtain repository URL and revision from `capabilities.local.git` for the `prepare-current` / `run-current` convenience path. The CLI may also replace the local remote URL with an explicit worker-visible URL without changing local Git configuration. The effective URL, not the local directory name, determines the default remote cache identity.

The workflow deliberately contains no project-specific command knowledge. Project repositories own build/test commands.

Workflows may depend on core contracts and public capability APIs. They must not depend on CLI presentation.

### `cli`

Owns parsing, command selection, convenience composition and human/JSON rendering. It may combine local repository context with the remote Git workflow, but effect semantics stay in the owning capability/workflow modules.

## Dependency direction

Allowed:

```text
cli -> workflows -> capabilities -> core
cli -------------> capabilities -> core
cli ---------------------------> core
```

Forbidden:

```text
core -> capabilities/workflows
capabilities -> workflows
workflow -> cli
concrete capability A -> concrete sibling capability B private implementation
```

The architecture checker enforces these high-value boundaries and rejects raw `subprocess` use outside `core.execution`.

## Process execution

`host_ops.core.execution` is the single owner of local child-process lifecycle:

- argv boundary;
- cwd/environment;
- wall-clock timeout;
- bounded stdout/stderr retention;
- exit status;
- process-group termination/cleanup;
- normalized result state.

Local Git inspection, browser process discovery, managed browser/CDP-attach/snapshot helper execution, macOS native commands and remote SSH execution use the same `ProcessRunner`; capabilities do not create another subprocess abstraction. The browser DevTools HTTP metadata probe uses bounded direct Python HTTP APIs because the local HTTP endpoint itself is that read-only integration boundary. Managed Playwright probing runs inside an internal helper launched through `ProcessRunner`, so the helper/browser lifetime remains under the existing process timeout and outer Local Agent lifecycle. The local file capability uses direct Python filesystem APIs rather than spawning copy/hash tools because the filesystem is its integration boundary and it must control staging, fsync and digest verification itself. The local serial capability similarly uses direct POSIX device APIs (`os`, `termios`, `select`) because the TTY itself is the integration boundary; it does not spawn a terminal program or shell.

When `host-ops` runs beneath Local Agent it remains inside the authoritative outer repository lease/process group. Local Agent owns admission and scheduling; `host-ops` only owns its child effect.

## Local Git boundary

The local Git capability is read-only with respect to project source. It runs bounded Git inspection commands to determine:

- repository root;
- selected remote URL (`origin` by default);
- exact `HEAD` commit;
- whether the worktree contains tracked/untracked changes.

`run-current` fails closed on a dirty worktree because uncommitted files cannot be reconstructed by a remote worker from Git. Ignored files do not make the source checkout dirty.

Remote cache/workspace identity deliberately does not belong here. It is workflow policy because the effective worker-visible URL may differ from the local remote URL.

## Local artifact boundary

`capabilities.local.files` owns deployment of one explicitly supplied regular source file into one existing destination directory.

Its contract deliberately rejects source and destination-directory symlinks, rejects path-like destination names, and refuses to replace an existing destination unless replacement is explicit. It writes to a same-directory temporary file and fsyncs it. Replacement uses atomic `os.replace`; no-clobber mode first reserves the absent destination with exclusive creation before replacing only that reservation. The final path is reread and verified for both byte size and SHA-256, and directory fsync is attempted.

The capability does not discover removable media, choose firmware filenames, mount filesystems, eject devices or infer project intent. Reusable mount/deploy/eject composition belongs to `workflows.removable_media`; project-specific naming and firmware policy remain with the caller.

## Generic host profile boundary

`capabilities.local.host` reports local execution-host facts only. It does not rank machines, reserve resources or schedule work. macOS physical memory uses pinned `/usr/sbin/sysctl`; Linux memory uses `sysconf` when available.

## Local network boundary

`capabilities.local.network` accepts one explicit host and either resolves it or attempts one explicit TCP port. DNS/socket work runs in a bounded worker process. Address-range discovery, port-range scanning and service fingerprinting are outside this capability.

## Local browser boundary

`capabilities.local.browser` has several explicit, non-interchangeable browser boundaries.

Process/HTTP inspection discovers recognized browser root processes and probes only loopback Chromium DevTools base endpoints. It returns normalized process and sanitized `/json/version` / `/json/list` evidence; credentials, query strings and fragments are not exposed.

Read-only CDP operations require an already-authorized loopback Chromium endpoint and keep evidence bounded: target inventory, current-page/root metadata, selector match counts, extension readiness and worker/service-worker lifecycle diagnostics. They do not export page content, matched nodes, cookies/storage or arbitrary JavaScript results.

Attached-page mutation is intentionally narrow. `browser attach reload` requires one exact page target plus a previously observed sanitized HTTP(S) URL and sends exactly one reload only if the live target still matches that guard. `recover-content-script` may compose one such reload only for a missing/stale content-script diagnosis and must re-check readiness afterward.

Persistent managed sessions control one Chromium-family root process using an isolated host-ops-owned profile and a dynamic loopback CDP port. Profile ownership, exact process/profile identity and start/status/stop behavior fail closed. Interactive mode reuses only that owned profile but deliberately launches without CDP or extension flags for short user-driven interactions; it is process control, not automated page authority.

The disposable Playwright probe is separate: it creates a fresh context, performs exactly one bounded HTTP(S) navigation, returns sanitized metadata/error counts and closes the context/browser.

No browser boundary exposes general click/fill/press/drag automation, arbitrary JavaScript, page-content extraction, screenshots, download orchestration or cookies/storage access.

## ADB boundary

`capabilities.local.adb` resolves the local `adb` executable, lists attached device identities/states, reads fixed `getprop` identity facts, captures a bounded `logcat -d -t N` tail and performs verified one-file push/pull for one validated explicit serial in `device` state. File transfer accepts only validated literal absolute paths, size/time bounds and explicit replacement intent. Arbitrary shell, package mutation and reboot operations remain outside the ADB boundary.

## macOS boundary

Read-only macOS inspection uses pinned Apple-provided tools through `ProcessRunner` and returns normalized models for host, USB, serial and external storage facts.

Storage mutation is deliberately narrow. `MacOSStorageController` accepts only canonical `diskN`/`diskNsN` identifiers and uses `diskutil info -plist` before every action. If `Internal` is not explicitly `false`, the action is rejected. Eject additionally requires `Whole=true`. Formatting and partitioning are outside this capability.

## Local serial boundary

`capabilities.local.serial` owns one bounded transaction against one explicitly supplied POSIX character device below `/dev`.

The port path is resolved before opening and must still identify a character device. The caller supplies a host-supported baudrate, optional raw bytes to write, maximum response size, whole-transaction deadline and response-idle interval. The capability configures raw 8N1 operation, performs non-blocking bounded writes and reads, and reports whether completion came from the overall deadline, response-idle interval or read-size limit.

If a transaction includes a write, buffered input is flushed before sending so stale response bytes are not silently mixed with the new request. A read-only transaction does not flush existing input. The capability does not interpret line endings, G-code, bootloader protocols or firmware semantics. Higher-level device workflows must supply those policies explicitly.

## SSH boundary

Routine SSH calls use pinned `/usr/bin/ssh` and `-F /dev/null`.

Targets require explicit remote user and literal identity-file path. Authentication is public-key-only and non-interactive. Strict host-key verification is mandatory. General user SSH config, forwarding, local commands, connection multiplex persistence and agent mutation are intentionally not inherited.

Termux/Linux are target profiles, not separate SSH implementations.

## Remote Git workflow boundary

The remote Git bootstrap is a constant host-ops program. Repository URL, revision, workspace/lock names and command argv are supplied as positional data; caller input is not interpolated into bootstrap source.

The revision is a full lower-case Git object id. Symbolic branches/tags are rejected. After fetch/prune, the requested commit must have been fetched and must be reachable from refs fetched from the effective worker-visible origin; merely finding the object in an old workspace cache is insufficient. `git rev-parse HEAD` must match the requested revision before caller code runs.

Each remote workspace is bound to one exact worker-visible repository URL. A caller cannot silently retarget an existing cache to another repository and reuse its objects. Legacy pre-binding workspaces are adopted only if their current `origin` already matches the requested URL. Cache roots, workspace/repository directories, repository markers and lock paths reject unexpected symlink/type state; lock files are opened non-truncating before `flock`.

A previous project command may modify tracked files or leave nested untracked Git repositories. The workflow hard-resets and double-force-cleans the old checkout before switching revision, then resets/cleans again after checkout. This prevents stale build state from blocking or contaminating the next exact source preparation.

Every workspace receives a non-blocking kernel lock. An optional second lock can serialize CPU-heavy jobs across unrelated repositories on a constrained host. Local Agent may additionally own a named scheduler resource for cross-repository queueing.

Default clean mode preserves ignored caches (`git clean -ffd`). Full mode removes ignored state as well (`git clean -ffdx`). This is an explicit reproducibility/performance tradeoff selected by the caller.

Remote project commands are expected to remain foreground processes. Intentional daemonization/background descendants are outside the timeout and lock-lifecycle guarantee.

## Results

Machine-facing operations return explicit success/failure state and structured evidence appropriate to the boundary. Process-backed capabilities additionally retain bounded stdout/stderr, duration, truncation state and normalized execution errors. Artifact deployment returns source/destination identity, byte size, SHA-256, replacement state and whether destination-directory fsync was supported. Serial transactions return requested/resolved port identity, baudrate, bytes written/read, bounded response bytes and the completion condition.

Human rendering stays at the CLI boundary.

## Configuration and secrets

Machine-local target configuration lives outside the repository under `~/.config/host-ops/` by default.

Configuration may identify endpoints and reference an external SSH key path. It must never contain private-key bytes, passwords, bearer tokens, cookies or other secrets.

HTTP(S) repository URLs passed to remote Git workflows must not embed credentials, query strings or fragments. Authentication/trust belongs to external target configuration.

## Evolution rule

Before adding a module, identify its single owner and dependency direction. Before adding an abstraction, identify repeated real use or a concrete alternate implementation/test seam.

Prefer small vertical slices:

```text
contract -> implementation -> CLI/use site -> focused tests -> full gate -> live smoke if physical I/O matters
```

Do not pre-create empty capability trees or generic plugin frameworks.
