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

## Prerequisites

External recovery requires all of the following:

- the target ChatGPT conversation is already open in Chromium;
- that Chromium instance exposes an explicitly authorized loopback CDP endpoint such as `http://127.0.0.1:9222`;
- the exact sanitized conversation URL is known, with no query or fragment;
- the current `local-agent` checkout contains the Bridge version expected to be active;
- the installed `hostops` command provides `browser attach readiness` and `browser attach recover-content-script`.

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

The helper returns machine-readable JSON containing:

- mode (`inspect` or `recover`);
- exact sanitized conversation URL;
- exact selected target id;
- the Bridge script basenames that were fingerprinted;
- the bounded Host Ops readiness/recovery result.

Expected SHA-256 values are generated locally and passed to Host Ops but are not copied into the helper's structured result. Host Ops keeps extension ids, raw extension URLs, observed script hashes, script source and private page content outside public readiness/recovery evidence.

## Failure boundary

This helper is deliberately not a daemon watchdog and not an automatic restart loop. Local Agent remains a deterministic executor and ChatGPT remains the planner. External Bridge recovery is one explicit operator/planner action backed by exact target evidence; it does not add heuristic browser monitoring to the daemon.
