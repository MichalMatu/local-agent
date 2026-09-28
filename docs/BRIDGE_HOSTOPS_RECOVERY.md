# External Chat Bridge recovery through Host Ops

Chat Bridge has a normal worker-owned recovery path and an external fallback. Keep those boundaries separate.

The normal path is always preferred while Bridge can still answer its own protocol:

```text
[LAB:DEBUG]
[LAB:RELOAD=CONTENT]
[LAB:RELOAD=BRIDGE]
```

`worker_transport.js` owns content-script probing and reinjection. Host Ops must not replace that mechanism or become a second Bridge runtime.

Use the external fallback only when the Bridge/content path itself is unavailable and therefore cannot execute its own maintenance controls. The fallback is intentionally limited to one already-open ChatGPT page and the current unpacked Bridge content-script files.

## Dedicated managed browser

The preferred external-fallback setup is a separate persistent Chromium profile dedicated to Chat Bridge. Do not enable remote debugging on the operator's normal Chrome profile.

`scripts/bridge_hostops_session.py` is a thin Chat Bridge-specific wrapper around the generic `hostops browser session` capability. It does not own a browser process manager. On `start` it supplies exactly three Bridge-specific inputs: the current `chat_bridge/` unpacked extension directory, an explicit isolated profile directory and an approved ChatGPT HTTPS start URL.

Start a dedicated browser on macOS:

```bash
python scripts/bridge_hostops_session.py start \
  --profile-dir "$HOME/.local/share/local-agent/chat-bridge-chrome" \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

The default start URL is `https://chatgpt.com/`. `--url` may instead name an exact ChatGPT conversation path, but credentials, explicit ports, query data and fragments are rejected. Host Ops loads only the current unpacked `chat_bridge/` extension through this wrapper and creates CDP on a Chrome-selected dynamic loopback port.

Check the session and retrieve the current endpoint:

```bash
python scripts/bridge_hostops_session.py status \
  --profile-dir "$HOME/.local/share/local-agent/chat-bridge-chrome"
```

The JSON result contains the Host Ops session evidence. When running, `result.endpoint` is the explicit `http://127.0.0.1:<dynamic-port>` value to pass to the recovery helper below.

Stop only that dedicated browser:

```bash
python scripts/bridge_hostops_session.py stop \
  --profile-dir "$HOME/.local/share/local-agent/chat-bridge-chrome"
```

The profile persists across stop/start cycles so the operator can log in to ChatGPT once inside this isolated browser. The wrapper never adopts an existing profile, never scans for a daily Chrome profile and never uses process-name killing; those guards are enforced by Host Ops C5.

## Prerequisites

External recovery requires all of the following:

- the target ChatGPT conversation is already open in Chromium;
- that Chromium instance exposes an explicitly authorized loopback CDP endpoint, preferably from the dedicated managed-browser helper above;
- the exact sanitized conversation URL is known, with no query or fragment;
- the current `local-agent` checkout contains the Bridge version expected to be active;
- the installed `hostops` command provides `browser attach readiness`, `browser attach recover-content-script` and, for the managed-browser helper, `browser session start|status|stop`.

This path does not discover or attach to ordinary Chrome implicitly. The CDP endpoint is always explicit.

## Operator helper

`scripts/bridge_hostops_recovery.py` derives the expected content-script fingerprints directly from the current `chat_bridge/manifest.json` and referenced JavaScript files. It never stores expected hashes in planner prompts or documentation.

Read-only diagnosis is the default:

```bash
python scripts/bridge_hostops_recovery.py \
  --endpoint http://127.0.0.1:9222 \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID
```

The helper first asks Host Ops for bounded target inventory, requires exactly one `page` target whose sanitized URL equals the requested conversation URL, then runs exact-target readiness with the Bridge manifest scripts and `#prompt-textarea` DOM readiness guard.

Allow one bounded recovery attempt only with explicit `--recover`:

```bash
python scripts/bridge_hostops_recovery.py \
  --endpoint http://127.0.0.1:9222 \
  --conversation-url https://chatgpt.com/c/CONVERSATION_ID \
  --recover
```

The helper delegates mutation entirely to Host Ops C4. Only `content_script_missing` or `content_script_stale` can cause the existing guarded page reload. Host Ops performs at most one reload and requires one post-reload readiness check. The helper adds no retry loop, arbitrary JavaScript, navigation, click, fill, worker mutation or extension reload authority.

## Escalation policy

Use this order:

1. If Bridge responds, use Bridge-native diagnostics and maintenance. Do not use external recovery merely because a normal Bridge command is available.
2. If Bridge does not respond, run the helper without `--recover` first.
3. If readiness reports `content_script_missing` or `content_script_stale`, one explicit `--recover` attempt is allowed.
4. If readiness reports `dom_not_ready` or `extension_ambiguous`, do not mutate the page. Fix the underlying target/DOM/identity ambiguity first.
5. `worker_inactive` alone is not proof of failure. Manifest V3 workers are allowed to sleep. External content recovery must not wake, restart or otherwise mutate the worker.
6. If one bounded recovery returns `not_recovered`, `target_changed` or another non-success result, stop. Do not loop reloads. Re-inspect the browser/extension state or require explicit operator intervention.
7. If the extension runtime itself is stale or broken, this page-level fallback is not sufficient. Use the explicit Bridge runtime reload path when it is reachable; otherwise the operator must explicitly reload the unpacked extension through Chrome's extension management UI.

## Planner integration

The `host-ops` multirepo conversation is the canonical planner workspace for this fallback because `host-ops` is execution-enabled and already owns the bounded browser capability. The `local-agent` catalog entry remains execution-disabled.

A planner may therefore:

- inspect or update `MichalMatu/local-agent` through direct GitHub operations;
- when machine execution is required, run the helper from the installed/current `local-agent` checkout inside a task targeting the execution-enabled `host-ops` repository and using the exact `host-ops` agent binding;
- never queue a Local Agent task against the `local-agent` repository merely to run this helper.

The planner must still know the exact conversation URL and explicit CDP endpoint. It must not guess either value from history or choose among duplicate page targets.

## Evidence and privacy

The managed-browser helper returns machine-readable JSON containing the action, explicit profile path and bounded Host Ops session result. `start` additionally reports the exact local Bridge directory and sanitized start URL. It does not return cookies, storage, page content or extension source.

The recovery helper returns machine-readable JSON containing:

- mode (`inspect` or `recover`);
- exact sanitized conversation URL;
- exact selected target id;
- the Bridge script basenames that were fingerprinted;
- the bounded Host Ops readiness/recovery result.

Expected SHA-256 values are generated locally and passed to Host Ops but are not copied into the helper's structured result. Host Ops keeps extension ids, raw extension URLs, observed script hashes, script source and private page content outside public readiness/recovery evidence.

## Failure boundary

These helpers are deliberately not daemon watchdogs and not automatic restart loops. Local Agent remains a deterministic executor and ChatGPT remains the planner. External Bridge recovery is one explicit operator/planner action backed by exact target evidence; it does not add heuristic browser monitoring to the daemon.
