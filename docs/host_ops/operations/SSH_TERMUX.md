# SSH and Termux operations

`python -m local_agent.host_ops ssh` is the hardened OpenSSH boundary for configured POSIX targets, including Termux. It does not implement SSH itself or store credentials.

## Runtime contract

Routine operations use pinned `/usr/bin/ssh` with explicit behavior rather than inheriting general SSH configuration:

- `-F /dev/null` isolates user/system SSH config;
- explicit remote `user` and `identity_file` are required;
- batch public-key authentication only;
- `StrictHostKeyChecking=yes` stays enabled;
- `IdentitiesOnly=yes`; agent/key mutation is disabled;
- forwarding, local commands, multiplex persistence and post-auth daemonization are disabled;
- connection/process execution and retained stdout/stderr are bounded;
- no pseudo-terminal is allocated.

The target host is literal DNS/IP-style syntax. Identity paths must be absolute or `~/...` and may not contain OpenSSH expansion tokens.

Remote argv is encoded for a POSIX shell boundary. Windows/PowerShell would require a separate contract.

Process-group/Local Agent lease behavior is documented once in the [Security model](../security/SECURITY_MODEL.md).

## Machine-local target configuration

Default file:

```text
~/.config/host-ops/config.toml
```

Example Termux target:

```toml
version = 1

[hosts.termux-phone]
host = "192.168.0.100"
port = 8022
user = "u0_a520"
identity_file = "~/.ssh/host_ops_termux_ed25519"
```

The file stores target identity and a path to external key material, never private-key bytes. Password/token/private-key content is rejected by config parsing.

## One-time Termux SSH bootstrap

Bootstrap is intentionally manual because first trust may require a password and out-of-band host-key verification.

### 1. Start SSH in Termux

```bash
pkg install openssh
passwd
sshd
```

Termux normally listens on port `8022`.

### 2. Verify the server key on the phone

```bash
ssh-keygen -lf "$PREFIX/etc/ssh/ssh_host_ed25519_key.pub"
```

Keep this fingerprint visible while establishing trust from the Mac. `ssh-keyscan` alone is not identity proof.

### 3. Create a dedicated client key

On the Mac:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/host_ops_termux_ed25519 -C "host-ops-termux"
```

Do not commit or copy the private key into task payloads/results.

### 4. Establish host trust manually

```bash
/usr/bin/ssh -p 8022 u0_a520@192.168.0.100
```

Accept the key only after comparing its fingerprint with the phone. Routine `host-ops` calls keep using the normal `known_hosts` trust database even though general SSH config is disabled.

### 5. Install the public key

If available:

```bash
ssh-copy-id -i ~/.ssh/host_ops_termux_ed25519.pub -p 8022 u0_a520@192.168.0.100
```

Portable alternative:

```bash
cat ~/.ssh/host_ops_termux_ed25519.pub | \
  /usr/bin/ssh -p 8022 u0_a520@192.168.0.100 \
  'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys'
```

Then add the target to `config.toml`. A DHCP reservation is useful for a phone that should remain a stable worker.

## Routine verification

```bash
python -m local_agent.host_ops ssh check termux-phone
python -m local_agent.host_ops ssh check termux-phone --json
```

A passing check proves, for that invocation, that OpenSSH started, host-key verification passed, the configured key authenticated, the fixed identity command succeeded and the remote account matched configured `user`.

When the console entry point is not installed globally, use the exact checkout:

```bash
PYTHONPATH=src python3 -m host_ops ssh check termux-phone
```

Useful Termux identity preflight:

```bash
python -m local_agent.host_ops ssh exec termux-phone -- sh -lc \
  'test "$PREFIX" = /data/data/com.termux/files/usr && printf "TERMUX_OK\n"'
```

## Remote commands

```bash
python -m local_agent.host_ops ssh exec termux-phone -- uname -a
python -m local_agent.host_ops ssh exec termux-phone -- pwd
python -m local_agent.host_ops ssh exec termux-phone -- sh -lc 'command -v git && command -v python3'
```

`--` separates host-ops options from remote argv. Remote exit status is preserved when it is a normal process exit; local timeout/spawn/runtime states use host-ops process semantics.

## Verified file transfer

```bash
python -m local_agent.host_ops ssh push termux-phone ./artifact.bin /data/data/com.termux/files/home/artifact.bin --json
python -m local_agent.host_ops ssh pull termux-phone /data/data/com.termux/files/home/result.bin ./result.bin --json
```

Transfers are one-file operations with explicit source/destination, whole-operation timeout, size limit, sibling staging, size/SHA-256 verification and explicit `--replace` for existing destinations. Remote paths are normalized absolute POSIX file paths with conservative characters.

No-clobber push uses a remote hard-link commit. Replacement uses remote `mv`; post-commit verification still runs. If a remote namespace is concurrently mutated by another process with the same account, a failed post-commit verification means the destination/staging area should be inspected before retrying.

## Termux worker prerequisites

Remote Git workflows additionally require Bash, Git and `flock` plus the project-specific toolchain. `host-ops` does not install those dependencies.

If SSH must survive phone reboot, Termux:Boot may start `sshd`. Service autostart and Android battery/background policy belong to the phone, not the SSH capability.

## Failure guide

- `Host key verification failed` — trust is missing or changed; verify the fingerprint out-of-band.
- `Permission denied` — configured key/account authentication failed.
- missing explicit user/key — fix `config.toml`; do not rely on defaults.
- identity file inaccessible — fix the configured path/permissions.
- `Connection refused` — `sshd` is not listening at the configured address/port.
- route/timeout failure — verify LAN address and network isolation.
- identity mismatch — transport succeeded but the remote account is not the configured account.
- transfer digest/size failure — treat the operation as failed and inspect the destination if failure occurred after commit.

Do not weaken batch mode, strict host-key checking, explicit identity requirements or config isolation to turn these failures green.
