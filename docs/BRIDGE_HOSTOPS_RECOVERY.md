# Chat Bridge browser operations through Host Ops

This is the canonical runbook for the dedicated Chat Bridge browser. Host Ops owns browser lifecycle and bounded CDP effects; Local Agent scripts add only Chat Bridge-specific policy.

## Production boundary

Use only the dedicated Chrome for Testing / Chromium profile:

```text
~/.local/share/local-agent/chat-bridge-cft
```

Preferred macOS CfT alias:

```text
~/.local/share/local-agent/chrome-for-testing/current
```

The operator's daily Chrome profile is out of scope. Never attach to it, copy its cookies, enable remote debugging on it, or kill Chrome processes by name.

The old rollback profile may remain on disk but is never selected implicitly:

```text
~/.local/share/local-agent/chat-bridge-chrome
```

## Normal managed session

From the current Local Agent checkout:

```bash
CFT="$HOME/.local/share/local-agent/chrome-for-testing/current/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
PROFILE="$HOME/.local/share/local-agent/chat-bridge-cft"

python scripts/bridge_hostops_session.py start \
  --profile-dir "$PROFILE" \
  --browser-executable "$CFT" \
  --url https://chatgpt.com/

python scripts/bridge_hostops_session.py status --profile-dir "$PROFILE"
python scripts/bridge_hostops_session.py stop --profile-dir "$PROFILE"
```

Managed mode loads the current unpacked `chat_bridge/` extension and uses a browser-selected loopback CDP port. The wrapper rejects the standard branded macOS Google Chrome executable for this flow.

## Manual authentication bootstrap

If an identity provider rejects managed mode, authenticate in the same owned profile without CDP or extension flags:

```bash
python scripts/bridge_hostops_session.py stop --profile-dir "$PROFILE"

python scripts/bridge_hostops_session.py login-start \
  --profile-dir "$PROFILE" \
  --browser-executable "$CFT" \
  --url https://chatgpt.com/

# Complete authentication manually in the opened browser.

python scripts/bridge_hostops_session.py login-finish --profile-dir "$PROFILE"

python scripts/bridge_hostops_session.py start \
  --profile-dir "$PROFILE" \
  --browser-executable "$CFT" \
  --url https://chatgpt.com/
```

`login-finish` stops only the exact interactive browser and removes only tab/session-restore state. Cookies, site storage, account state, extension data and the Host Ops ownership marker remain intact.

Do not try to bypass identity-provider checks with user-agent spoofing, automation-hiding flags or copied daily-browser state.

## Readiness contract

`scripts/bridge_hostops_recovery.py` derives expected content-script SHA-256 fingerprints from the current Bridge manifest/files. Composer readiness accepts the bounded selector union:

```css
#prompt-textarea,
[data-testid="prompt-textarea"],
div.ProseMirror[contenteditable="true"]
```

A logged-out page may legitimately report `dom_not_ready`. A Manifest V3 worker may legitimately report `worker_inactive`. Neither condition is a self-heal trigger by itself.

## Exact-target diagnosis and recovery

For a known exact conversation URL, diagnose read-only first:

```bash
python scripts/bridge_hostops_recovery.py \
  --profile-dir "$PROFILE" \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID
```

An explicit authorized loopback endpoint may be used instead of `--profile-dir`:

```bash
python scripts/bridge_hostops_recovery.py \
  --endpoint http://127.0.0.1:9222 \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID
```

The helper requires exactly one matching page target. It never chooses among duplicate targets and never falls back to another browser/profile.

Use one explicit recovery attempt only when the read-only diagnosis is `content_script_missing` or `content_script_stale`:

```bash
python scripts/bridge_hostops_recovery.py \
  --profile-dir "$PROFILE" \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID \
  --recover
```

Host Ops may then perform at most one guarded page reload followed by one readiness re-check. Never reload for `ready`, `worker_inactive`, `dom_not_ready` or `extension_ambiguous`, and never loop recovery.

## Operational rules

- Prefer Bridge-native maintenance (`LAB:DEBUG`, `LAB:RELOAD=CONTENT`, `LAB:RELOAD=BRIDGE`) while Bridge still responds.
- External Host Ops recovery is a fallback, not a second Bridge runtime.
- No arbitrary JavaScript, click/fill/press, general navigation, worker mutation, broad process kill or implicit daily-Chrome attachment is authorized by this flow.
- Re-check repository drift, daemon state and concurrent tasks before writes or browser mutation.
- `local-agent` is execution-disabled in the multirepo catalog; schedule machine execution through execution-enabled `host-ops` with its exact binding.
- `chat-bridge-state` is an operational runtime-state branch and must not be removed as development-branch cleanup.

## Expected healthy evidence

A healthy logged-in managed profile normally has one intended ChatGPT page, `CONTENT_SCRIPT_STATE=ready`, `DOM_READY=True`, all current Bridge fingerprints matched and zero worker diagnostic errors. `worker_inactive` is acceptable.

Helpers return bounded lifecycle/readiness evidence only. They do not return cookies, storage values, page text, form values, extension ids, script source or raw extension URLs.
