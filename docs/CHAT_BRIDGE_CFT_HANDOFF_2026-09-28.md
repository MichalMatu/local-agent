# Chat Bridge + Host Ops handoff — 2026-09-28

This is the current continuation point for Chat Bridge / Host Ops browser integration. Verify repository heads and daemon state before acting; do not reconstruct runtime state from chat memory alone.

## Current architecture

- The user's daily Google Chrome profile is out of scope and must remain untouched.
- Chat Bridge uses a dedicated Chrome for Testing / Chromium profile:
  `~/.local/share/local-agent/chat-bridge-cft`.
- Preferred CfT alias:
  `~/.local/share/local-agent/chrome-for-testing/current`.
- Old rollback profile remains on disk and must not be selected implicitly:
  `~/.local/share/local-agent/chat-bridge-chrome`.
- Host Ops owns browser process lifecycle, exact-profile guards, CDP attachment and bounded recovery.
- Local Agent helpers are thin Chat Bridge-specific wrappers only.
- External recovery is read-only by default and may reload once only for `content_script_missing` or `content_script_stale`.
- `worker_inactive` alone is normal for MV3 and is not a recovery trigger.
- `dom_not_ready` alone is not a recovery trigger.

## Repository state at this handoff work

The work started from:

- `MichalMatu/local-agent/main`: `fdb7d3cf4419a4a31b65e126846895db52325635`;
- `MichalMatu/host-ops/main`: `392b2caefdee08e54d3c972898735d842c594f37`.

Feature branches created for the final login/bootstrap fixes:

- `local-agent`: `feat/chat-bridge-login-bootstrap`;
- `host-ops`: `feat/browser-interactive-login-bootstrap`.

Always re-read `main` and branch heads before merging or continuing.

## What was proven in production

The dedicated CfT profile was first verified with one ChatGPT page and all five current content scripts matched.

Google login then rejected the managed browser while it exposed CDP/extension automation signals. The same exact dedicated profile was restarted manually **without CDP and without unpacked-extension flags**. Google login succeeded. The profile was then returned to normal managed mode.

The login state persisted correctly. A second issue was discovered: Chromium restored stale tabs from the authentication flow. Cleaning only session/tab restore files under the dedicated profile fixed that without deleting cookies or login state.

The final production managed-mode smoke after cleanup showed:

- exactly one `https://chatgpt.com/` page target;
- `READINESS_DIAGNOSIS=ready`;
- `CONTENT_SCRIPT_STATE=ready`;
- `DOM_READY=True`;
- all 5 Bridge content-script fingerprints `matched`;
- worker running at that moment;
- worker diagnostics `error_count=0`.

A later read-only branch smoke again showed one page, `DOM_READY=True`, 5/5 matched and `WORKER_ERROR_COUNT=0`; the MV3 worker happened to be inactive during that read, which is acceptable.

## DOM contract correction

The historical readiness selector `#prompt-textarea` is no longer sufficient for the current ChatGPT UI.

Production probing showed the logged-in composer as:

```css
div.ProseMirror[contenteditable="true"]
```

The Local Agent recovery helper now uses a bounded compatibility selector union:

```css
#prompt-textarea,
[data-testid="prompt-textarea"],
div.ProseMirror[contenteditable="true"]
```

This keeps old UI compatibility while recognizing the current composer without `Runtime.evaluate` or arbitrary page JavaScript.

## New login bootstrap flow

Host Ops feature work adds generic exact-profile interactive session commands:

```text
hostops browser session interactive-start
hostops browser session interactive-status
hostops browser session interactive-stop
```

Interactive mode:

- requires an existing Host Ops-owned managed profile;
- launches the exact profile without CDP and without extension flags;
- refuses ambiguous/multiple root processes;
- never adopts the daily Chrome profile;
- returns no CDP endpoint;
- stops only the exact matching root PID;
- can optionally clear only Chromium session/tab restore files after exit.

Local Agent exposes the Chat Bridge-specific thin wrapper:

```text
bridge_hostops_session.py login-start
bridge_hostops_session.py login-status
bridge_hostops_session.py login-finish
```

`login-finish` delegates the bounded session-restore cleanup. It does not clear cookies, local storage or account state.

Normal operator sequence:

```bash
CFT="$HOME/.local/share/local-agent/chrome-for-testing/current/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
PROFILE="$HOME/.local/share/local-agent/chat-bridge-cft"

python scripts/bridge_hostops_session.py stop --profile-dir "$PROFILE"

python scripts/bridge_hostops_session.py login-start \
  --profile-dir "$PROFILE" \
  --browser-executable "$CFT" \
  --url https://chatgpt.com/

# user completes login manually

python scripts/bridge_hostops_session.py login-finish --profile-dir "$PROFILE"

python scripts/bridge_hostops_session.py start \
  --profile-dir "$PROFILE" \
  --browser-executable "$CFT" \
  --url https://chatgpt.com/
```

Do not attempt to bypass identity-provider security using user-agent spoofing, automation-hiding flags or copied daily-browser cookies.

## Verification completed for the feature branches

Host Ops focused tests for the new interactive session lifecycle:

```text
15 passed
```

Local Agent focused tests for the session wrapper + recovery selector contract:

```text
Ran 20 tests
OK
```

A read-only live smoke using the Local Agent feature-branch selector contract against the real logged-in dedicated CfT profile passed:

```text
PAGE_COUNT=1
CONTENT_SCRIPT_STATE=ready
DOM_READY=True
FINGERPRINT_COUNT=5
WORKER_ERROR_COUNT=0
BRANCH_LIVE_SMOKE=pass
```

No reload, restart or page mutation was performed by that branch smoke.

## Recovery contract

For a known exact conversation URL, diagnosis remains:

```bash
python scripts/bridge_hostops_recovery.py \
  --profile-dir "$PROFILE" \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID
```

Only if the read-only diagnosis reports `content_script_missing` or `content_script_stale` may one explicit `--recover` attempt be used.

Never reload for:

- `ready`;
- `worker_inactive` alone;
- `dom_not_ready`;
- `extension_ambiguous`.

Never loop recovery.

## Multirepo operational rules

- `local-agent` is intentionally execution-disabled in the multirepo catalog.
- Machine execution for this browser workflow is scheduled through execution-enabled `host-ops` using its exact binding.
- Before writes, branch changes or browser mutation, check repo drift and concurrent tasks.
- The global supervisor can have unrelated repositories running in parallel; do not assume an idle Host Ops worker means the whole system is idle.
- Avoid broad process kills and giant inline task payloads.

## Next continuation action

If these feature branches are not yet merged:

1. re-read `local-agent/main`, `host-ops/main` and both feature heads;
2. confirm no active conflicting task;
3. run/inspect the focused test evidence and live smoke above;
4. merge only if each feature branch still descends cleanly from the current corresponding `main`;
5. after Local Agent `main` moves, allow the daemon to self-update and verify its reported `self_revision`;
6. run one final read-only managed-profile health check; do not reload a healthy page.

If the branches are already merged, treat the current `main` refs as authoritative and use `docs/BRIDGE_HOSTOPS_RECOVERY.md` as the runbook.
