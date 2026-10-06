# ADR 0002: Foundation contracts own process, configuration and diagnostics behavior

Status: Accepted

## Context

Every later capability needs to execute local programs, normalize results, apply time and output
bounds, discover machine-local configuration and report missing prerequisites.

Allowing each SSH, ADB, browser or macOS adapter to solve those concerns independently would create
duplicate timeout handling, inconsistent evidence, divergent subprocess cleanup and multiple places
where secrets could leak.

## Decision

Phase 1 introduces a small dependency-free core with three owners:

1. `host_ops.core.execution`
   - owns local child-process creation;
   - executes argv directly without a shell;
   - owns timeout, process-group termination and cleanup;
   - continuously drains stdout/stderr while retaining only configured bounded prefixes;
   - returns `ProcessResult` with explicit `completed`, `timed_out` or `spawn_failed` state.

2. `host_ops.core.config`
   - owns path resolution and TOML parsing;
   - defaults to `~/.config/host-ops/config.toml`;
   - supports `XDG_CONFIG_HOME` and `HOST_OPS_CONFIG`;
   - accepts endpoint identity but rejects credential-like fields.

3. `host_ops.core.diagnostics`
   - owns generic diagnostic contracts and composition;
   - distinguishes `pass`, `warn` and `fail`;
   - accepts command requirements instead of embedding capability-specific policy in core.

The CLI is a thin composition surface. `python -m local_agent.host_ops doctor` currently supplies optional `ssh` and `adb`
requirements and can render the report as human text or JSON.

## Consequences

- Concrete capabilities must use `ProcessRunner` rather than spawn their own child processes.
- Capability adapters receive normalized process evidence instead of vendor/process objects.
- stdout/stderr retention is bounded in memory without stopping pipe drainage.
- Timeout cleanup terminates the spawned process group, which also handles ordinary descendants.
- Configuration never becomes a password or key store.
- Missing optional tooling can be reported without making the whole doctor command fail.
- Live device/network evidence remains a later capability-level concern.

## Rejected alternatives

### `subprocess.run(..., capture_output=True)` in each adapter

Rejected because it duplicates behavior and buffers complete output in memory.

### Temporary-file-only capture

Rejected as the default because it moves the unbounded-retention problem from memory to disk.

### Paramiko or another SSH library in Foundation

Rejected. SSH semantics belong to the SSH capability, and system OpenSSH remains the intended
backend.

### Generic universal Tool base class

Rejected. Foundation provides process/config/diagnostic contracts only. Capability inheritance will
be introduced only if multiple real implementations prove a shared lifecycle.
