# ADR 0004: Isolate routine OpenSSH configuration

- Status: accepted
- Date: 2026-09-20
- Amends: ADR 0003

## Context

ADR 0003 chose the system OpenSSH client so `host-ops` would not implement another SSH protocol
stack or credential store. It also accepted influence from the user's general `~/.ssh/config`,
including routing and multiplexing behavior.

The pre-activation lifecycle audit found that this influence is too broad for deterministic Local
Agent execution. OpenSSH configuration can contain behavior such as `ProxyCommand`, `ProxyJump`,
`Match exec`, forwarding, local commands, multiplex masters and post-authentication forking. Even
when many individual options are overridden, treating a general-purpose user configuration file as
an implicit input makes the authority and process lifecycle of one task harder to prove.

The audit also found that resolving `ssh` through `PATH` creates an unnecessary executable-selection
input. The initial supported hosts are macOS and the Linux CI environment, where the system OpenSSH
client is available at `/usr/bin/ssh`.

The initial Termux use case requires a host, port, remote user, trusted host key and a dedicated local
identity file. None of those need implicit SSH configuration inheritance.

## Decision

Routine `python -m local_agent.host_ops ssh` invocations use the pinned executable:

```text
/usr/bin/ssh
```

and invoke it with:

```text
-F /dev/null
```

so neither `PATH` executable resolution nor general user/system SSH configuration becomes an
implicit behavior surface.

Every SSH target must declare both an explicit remote `user` and a literal machine-local identity
path, for example:

```toml
user = "u0_a520"
identity_file = "~/.ssh/host_ops_termux_ed25519"
```

The identity value is a path reference, not private-key contents. The path must be absolute or
home-relative (`~/...`) and must not contain OpenSSH `%...` tokens or `${...}` environment expansion.
The adapter expands the home-relative path and passes it explicitly with `-i` together with
`IdentitiesOnly=yes`.

Routine authentication is public-key-only. Calls explicitly disable password authentication,
forwarding, agent forwarding, local commands, connection multiplex persistence, automatic host-key
updates, key-agent mutation and post-authentication daemonization. Strict host-key verification
remains mandatory, and trust remains in OpenSSH `known_hosts`.

If a future target genuinely needs a jump host, proxy command, alternate SSH executable or other
routing/runtime feature, that behavior must be introduced as an explicit host-ops contract with
validation and tests. It must not arrive implicitly through `PATH` or an unrelated SSH configuration
file.

## Consequences

Advantages:

- one task's SSH behavior is reviewable from host-ops source plus its validated machine-local target;
- `ProxyCommand`, `Match exec` and unrelated user SSH policy cannot silently add local side effects;
- PATH shadowing cannot replace the SSH binary used by routine capability calls;
- Local Agent process-group and lease assumptions are easier to preserve;
- dedicated automation keys remain possible without storing key bytes in Git or task payloads;
- CI can inspect the effective OpenSSH configuration deterministically with `/usr/bin/ssh -G`.

Tradeoffs:

- existing `~/.ssh/config` aliases, `ProxyJump`, custom `IdentityFile` entries and multiplexing are not
  inherited by routine host-ops calls;
- every target must declare `user` and `identity_file` explicitly;
- platforms without the supported `/usr/bin/ssh` path require a future explicit backend/runtime
  decision instead of silently selecting another binary from `PATH`;
- advanced SSH routing requires a future explicit capability/config design rather than zero-code
  inheritance from the user's SSH setup.

These tradeoffs are intentional for an execution component operating beneath Local Agent.
