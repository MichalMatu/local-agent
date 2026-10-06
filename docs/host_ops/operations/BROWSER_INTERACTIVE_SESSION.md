# Interactive managed browser sessions

`python -m local_agent.host_ops browser session interactive-*` temporarily runs an **existing Host Ops-owned profile** without CDP and without extension flags. It is intended for short user-driven interactions such as authentication flows that reject a managed/debuggable browser.

It never adopts, discovers or attaches to the operator's normal browser profile.

## Commands

```bash
python -m local_agent.host_ops browser session interactive-start \
  --profile-dir /absolute/owned/profile \
  --browser-executable /absolute/path/to/chromium \
  --url https://example.test/ \
  --json

python -m local_agent.host_ops browser session interactive-status \
  --profile-dir /absolute/owned/profile \
  --json

python -m local_agent.host_ops browser session interactive-stop \
  --profile-dir /absolute/owned/profile \
  --clear-session-restore \
  --json
```

The profile must already contain the managed-session ownership marker. Only one root process may use the exact profile, and an interactive process must expose no remote-debugging port, address or pipe. Evidence therefore has `endpoint=null`.

`interactive-stop` sends one `SIGTERM` to the uniquely matched root process. Optional `--clear-session-restore` removes only Chromium tab/session-restore files after exit; cookies, site/account state, extension data and the ownership marker are preserved. Unexpected symlinks or file types fail closed.

## Intended transition

1. stop normal managed mode for the exact profile;
2. start interactive mode;
3. let the user complete the manual interaction;
4. stop interactive mode, optionally clearing stale restored tabs;
5. return to normal managed mode.

Interactive mode exposes no page automation, arbitrary JavaScript, click/fill/press primitives, extension mutation, broad process killing or retry loop. Product-specific URLs and extension choices belong outside Host Ops.
