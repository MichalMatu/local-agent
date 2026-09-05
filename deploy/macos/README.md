# macOS LaunchAgent deployment

Local Agent generates its LaunchAgent definition from the current checkout and user home directory. The repository intentionally does **not** track machine-specific `.plist` files with absolute `/Users/<name>/...` paths.

The production service label remains:

```text
com.michal.local-agent
```

## Safe workflow

From the Local Agent checkout:

```bash
cd ~/local-agent
```

Inspect the generated definition without changing the machine:

```bash
.venv/bin/python scripts/macos_launchd.py render
```

Write the LaunchAgent definition without activating or restarting it:

```bash
.venv/bin/python scripts/macos_launchd.py install \
  --mode parallel \
  --max-workers 2
```

Inspect the currently loaded service:

```bash
.venv/bin/python scripts/macos_launchd.py status
```

Restart onto the generated definition only when it is safe to interrupt the running agent:

```bash
.venv/bin/python scripts/macos_launchd.py restart \
  --mode parallel \
  --max-workers 2
```

Remove the user LaunchAgent:

```bash
.venv/bin/python scripts/macos_launchd.py uninstall
```

## Modes

| Mode | Entrypoint | Intended use |
| --- | --- | --- |
| `parallel` | `agent_entrypoint.py` | production bounded-parallel supervisor; recommended |
| `multirepo` | `agent_multirepo.py` | known-safe serial multi-repository fallback |
| `single` | `agentd.py` | direct single-repository daemon |

All modes use the same LaunchAgent label and are replacement configurations. They must never be loaded as concurrent Local Agent services.

## Generated paths

The generator resolves paths at runtime instead of embedding one developer account:

- Python: `<repo>/.venv/bin/python`
- working directory: the selected Local Agent checkout
- registry: `~/Library/Application Support/local-agent/repositories.json`
- LaunchAgent: `~/Library/LaunchAgents/com.michal.local-agent.plist`
- stdout: `~/Library/Logs/local-agent.log`
- stderr: `~/Library/Logs/local-agent-error.log`

The generated environment also sets `PYTHONDONTWRITEBYTECODE=1` and provides the standard macOS/Homebrew/PlatformIO executable search paths used by Local Agent tasks.

## Important safety rule

> [!WARNING]
> `install` only writes the definition and deliberately does **not** restart the running service. `restart` is the explicit disruptive action. Do not run it while an important task is active.

The guarded entrypoint, persistent disable marker, repository leases and process-group controls remain the runtime safety mechanisms; launchd is only the service manager.
