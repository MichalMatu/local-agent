# External Chat Bridge recovery through Host Ops

Chat Bridge has a normal worker-owned recovery path and an external Host Ops fallback. Keep those boundaries separate.

The normal Bridge path is preferred whenever Bridge can still answer its own protocol:

```text
[LAB:DEBUG]
[LAB:RELOAD=CONTENT]
[LAB:RELOAD=BRIDGE]
```

`worker_transport.js` owns normal content-script probing and reinjection. Host Ops must not become a second Bridge runtime.

## Dedicated browser profile

The external path uses one persistent Chrome for Testing (CfT) or Chromium profile dedicated to Chat Bridge. Do not enable remote debugging on the operator's normal browser profile.

Production profile:

```text
~/.local/share/local-agent/chat-bridge-cft
```

Preferred CfT alias on macOS:

```text
~/.local/share/local-agent/chrome-for-testing/current
```

`scripts/bridge_hostops_session.py` is a thin Chat Bridge wrapper over generic `hostops browser session` capabilities. Host Ops owns browser lifecycle and exact-profile process guards.

Normal managed mode loads the current unpacked `chat_bridge/` extension and uses a browser-selected loopback CDP port:

```bash
CFT="$HOME/.local/share/local-agent/chrome-for-testing/current/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
PROFILE="$HOME/.local/share/local-agent/chat-bridge-cft"

python scripts/bridge_hostops_session.py start \
  --profile-dir "$PROFILE" \
  --browser-executable "$CFT" \
  --url https://chatgpt.com/
```

Check or stop only that exact profile:

```bash
python scripts/bridge_hostops_session.py status --profile-dir "$PROFILE"
python scripts/bridge_hostops_session.py stop --profile-dir "$PROFILE"
```

The wrapper rejects the normal branded macOS Google Chrome executable for this automatic unpacked-extension flow. Chrome for Testing or Chromium should be used instead.

## Manual login bootstrap

Some identity providers can reject a browser while it exposes automation/debugging signals. For that case, use the **same Host Ops-owned dedicated profile** in temporary interactive mode.

First stop normal managed mode for the exact profile, then start login mode:

```bash
python scripts/bridge_hostops_session.py stop --profile-dir "$PROFILE"

python scripts/bridge_hostops_session.py login-start \
  --profile-dir "$PROFILE" \
  --browser-executable "$CFT" \
  --url https://chatgpt.com/
```

`login-start` delegates to `hostops browser session interactive-start`. It launches the same owned profile without CDP flags and without unpacked-extension flags. The user completes authentication manually in that browser window.

Optional status:

```bash
python scripts/bridge_hostops_session.py login-status --profile-dir "$PROFILE"
```

After successful authentication, finish login mode:

```bash
python scripts/bridge_hostops_session.py login-finish --profile-dir "$PROFILE"
```

`login-finish` stops only the exact interactive root process and requests Host Ops to remove only Chromium tab/session-restore files. Cookies, local storage, account state, extension data and the Host Ops ownership marker are retained. This prevents stale identity-provider tabs from reopening when normal managed mode starts again.

Then return to normal managed mode with `start`. The login state remains in the dedicated profile.

Never copy cookies from the user's normal Chrome profile, never attach to that profile, and never add flags intended to disguise automation to an identity provider.

## Readiness and current composer contract

`scripts/bridge_hostops_recovery.py` derives the current Bridge content-script fingerprints from `chat_bridge/manifest.json` and the referenced JavaScript files.

ChatGPT's composer DOM is not assumed to have one historical selector. Current readiness uses this bounded CSS union:

```css
#prompt-textarea,
[data-testid="prompt-textarea"],
div.ProseMirror[contenteditable="true"]
```

This preserves compatibility with the older `#prompt-textarea` DOM while supporting the current ProseMirror composer observed in production. Host Ops still receives only one bounded CSS selector expression and performs its normal DOM selector-count check; no page JavaScript is evaluated.

A logged-out page can legitimately return `dom_not_ready`. That is not a content-script self-heal condition.

## Exact-target external diagnosis

For a known exact ChatGPT conversation URL:

```bash
python scripts/bridge_hostops_recovery.py \
  --profile-dir "$PROFILE" \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID
```

The helper:

1. resolves the exact managed profile to its current loopback CDP endpoint;
2. requires exactly one `page` target whose sanitized URL equals the requested conversation URL;
3. derives all expected Bridge script SHA-256 fingerprints locally;
4. runs Host Ops readiness using the current composer selector contract;
5. remains read-only unless `--recover` is explicitly supplied.

The explicit endpoint form remains available for an already authorized loopback Chromium instance:

```bash
python scripts/bridge_hostops_recovery.py \
  --endpoint http://127.0.0.1:9222 \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID
```

No process-scanning fallback chooses another browser or another target.

## Bounded recovery

Only add `--recover` after read-only diagnosis reports `content_script_missing` or `content_script_stale`:

```bash
python scripts/bridge_hostops_recovery.py \
  --profile-dir "$PROFILE" \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID \
  --recover
```

Mutation is delegated entirely to Host Ops. At most one guarded page reload is allowed, followed by one readiness re-check.

The following conditions are **not** reasons to reload:

- `ready`;
- `worker_inactive` by itself — MV3 workers are allowed to sleep;
- `dom_not_ready`;
- `extension_ambiguous`.

If one bounded recovery returns `not_recovered`, `target_changed` or another non-success result, stop and re-inspect. Do not loop recovery.

## Safety boundaries

The external flow does not provide arbitrary JavaScript, click/fill/press, general navigation, extension reload, worker mutation, broad process killing or implicit daily-Chrome attachment.

Exact-profile browser lifecycle belongs to Host Ops. Local Agent scripts add only Chat Bridge-specific profile/extension/URL policy.

The old rollback profile may remain on disk, but it is not selected implicitly:

```text
~/.local/share/local-agent/chat-bridge-chrome
```

## Multirepo execution

`local-agent` is intentionally execution-disabled in the multirepo catalog. Machine execution for this browser workflow should be scheduled through execution-enabled `host-ops` using its exact agent binding, while Local Agent source changes may be made through GitHub operations.

Before any write or browser mutation, re-check repository drift, daemon state and concurrent tasks.

## Evidence and privacy

Session helpers return only bounded lifecycle evidence such as action, profile path, state, PID and loopback endpoint where applicable. Recovery returns target identity, sanitized URL, requested script basenames and bounded readiness/recovery evidence.

Cookies, storage, page text, form values, extension ids, raw extension URLs, script source and observed raw hashes are not returned by these helpers.

## Failure boundary

These helpers are operator/planner actions, not daemon watchdogs. They do not add background restart loops. If the exact profile, target or ownership evidence is ambiguous, fail closed and require explicit intervention.
