# ADR 0003: Use system OpenSSH for remote execution

- Status: accepted; configuration-inheritance portion amended by ADR 0004
- Date: 2026-09-19

## Context

`host-ops` needs deterministic SSH execution for Termux and ordinary remote POSIX hosts. The local
Mac already has a mature OpenSSH client with existing host-key storage, agent/Keychain integration,
SSH configuration, multiplexing and standard diagnostics.

Embedding another SSH protocol implementation would duplicate authentication, host-key and config
semantics inside this repository and would create a second credential surface.

> Historical note: ADR 0004 retains the system OpenSSH backend but removes general `~/.ssh/config`
> inheritance from routine host-ops calls after the pre-activation lifecycle/security audit.

## Decision

The default SSH backend is the system `ssh` executable invoked only through the shared
`host_ops.core.execution.ProcessRunner`.

The SSH capability owns:

- target resolution from validated host-ops configuration;
- OpenSSH-specific argv construction;
- non-interactive/strict defaults;
- POSIX remote command encoding;
- remote-user identity checks;
- interpretation of the resulting `ProcessResult`.

The shared execution core continues to own:

- local process creation;
- wall-clock timeout;
- process-group cleanup;
- bounded stdout/stderr;
- normalized process state.

Authentication secrets and trust material stay outside `host-ops`, in system/user OpenSSH state such
as `~/.ssh`, `known_hosts`, ssh-agent and macOS Keychain.

## Security defaults

Routine adapter calls force:

- `BatchMode=yes`;
- `StrictHostKeyChecking=yes`;
- no pseudo-terminal;
- finite connection/keepalive settings.

Unknown or changed host keys therefore fail closed. Password prompts cannot hang a Local Agent task.
The first host-key trust decision and initial public-key installation are explicit provisioning
steps, not hidden fallback behavior.

Host and user fields are validated before they can become SSH argv elements. In particular, values
that could be interpreted as OpenSSH options or alternate `user@host` syntax are rejected.

## Remote command model

OpenSSH transports a remote command string, not a native remote argv vector. For POSIX targets,
`host-ops` converts caller-provided argv to one command string using POSIX shell quoting.

This contract is suitable for Termux/Linux/macOS-style remote shells. A future Windows/PowerShell
backend must define a separate encoding strategy instead of reusing this implementation.

## Consequences

Advantages:

- no private-key storage inside the repository;
- native reuse of OpenSSH trust and authentication behavior;
- smaller dependency and attack surface;
- diagnostics match commands an operator can reproduce manually;
- no duplicate SSH protocol lifecycle to maintain.

Tradeoffs recorded at the time of this decision included allowing the user's local OpenSSH
configuration to influence authentication/routing. ADR 0004 supersedes that part of the decision:
routine host-ops calls now isolate OpenSSH configuration and make non-default identity selection
explicit.
