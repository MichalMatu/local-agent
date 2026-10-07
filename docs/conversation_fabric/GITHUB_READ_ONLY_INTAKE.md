# GitHub-first Conversation Fabric: read-only intake

## Scope and activation

This is a staged, **read-only** intake, not a live browser spawning path.
The existing `LOCAL_AGENT_CF` DOM flow remains the sole production dispatch.
No browser tab, child composer, campaign lifecycle, or repository task is created by intake.

The existing one-minute GitHub-control alarm calls intake **after** normal
Conversation Fabric polling. No new alarm or scheduling authority exists.

Activation requires `github_fabric_read_only_intake_enabled: true` in the
remote schema-v3 `chat_bridge/runtime.json`. Omitted or `false` disables it.
A non-boolean value invalidates runtime config. Remote fallback never enables it.
The locally configured runtime URL must be the canonical
`https://raw.githubusercontent.com/MichalMatu/local-agent/chat-bridge-state/chat_bridge/runtime.json`.

## Immutable GitHub source

On the `chat-bridge-state` branch, the index is:

`.agent/conversation/browser_dispatches/index.json`

The exact index schema is:

```json
{"schema_version":1,"dispatch_ids":["fabric-00000000000000000000000000000000"]}
```

The bounded index contains zero to four unique canonical dispatch IDs.
The browser derives each immutable record path itself:

`.agent/conversation/browser_dispatches/<dispatch-id>.json`

No URL, repository binding, Chrome tab ID, or browser selector is accepted from
the index. Each record must pass the existing browser-dispatch contract and
bootstrap SHA-256 check, match its path identity, and target an enabled,
GitHub-controlled, locally managed parent. Fetches are no-store, timeout-bounded,
and size-bounded. The publisher is intentionally not connected in this slice.

## Local recovery and conflicts

Only an immutable SHA-256 fingerprint of the canonical dispatch is stored in
`chrome.storage.local` under `bridgeGithubFabricReadOnlySeen`.

- New ID: store its digest, without starting browser work.
- Same ID, same digest: replay/no-op.
- Same ID, different digest: conflict; preserve the original fingerprint.
- Identity ledger full (128 IDs): fail closed; **never evict an identity to
  permit a possible conflicting reuse**. Explicit operator recovery is required.

GitHub content remains the authority for full admitted child bootstrap records.
The local ledger is browser-side replay/conflict evidence, not an execution queue.
No repository execution authorization is exposed or expanded.

## Next gates

1. Local Agent trusted publication of immutable browser-dispatch records/index,
   preserving the normal workflow/campaign ownership model.
2. Opt-in read-only browser smoke against the GitHub raw surface, including
   restart persistence, malformed/truncated responses, conflict retention and
   existing DOM fallback behavior.
3. Explicit spawn protocol v2 with page-local claims before the first composer
   mutation, and no retry after `submit_armed`.
4. Separate feature gate for actual browser dispatch, full real-Chrome E2E,
   failure injection, and rollback evidence.
