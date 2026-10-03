# Local Agent 4.20.2

Local Agent 4.20.2 adds one narrow Conversation Fabric deployment helper: a fail-closed way to adopt a pre-existing **isolated** Chromium profile into the synthetic DEV/operator lab without copying browser state or touching the production/daily Chrome profile.

## Why

The 4.20.1 runtime and target-repository routing are production-ready, but the available authenticated Conversation Fabric browser profile predates the durable `lab.json` marker. Normal `init` correctly refuses every non-empty unmarked lab root. Repeating the earlier DEV login/Cloudflare loop is explicitly out of scope.

## Change

`python -m local_agent.development.lab adopt-profile` accepts a profile only when all of the following are true:

- the requested lab layout is disjoint from all protected production paths;
- the lab root already exists and has no lab marker;
- the root contains exactly one entry: `browser-profile`;
- `browser-profile` is a real directory, not a symlink;
- Chromium `Local State` is a regular file;
- at least one profile contains a regular `Preferences` file;
- no symbolic link exists anywhere below the browser profile.

If validation succeeds, Local Agent creates only the missing inert lab directories and the exact `lab.json` marker. Existing browser-profile bytes are not copied, rewritten or deleted.

Ordinary `init` is unchanged and continues to reject arbitrary non-empty unmarked roots.

## Boundaries

- Chat Bridge remains 0.7.0.
- Runtime schema, content protocol and assistant guard are unchanged.
- Conversation Fabric operator intake remains default-disabled.
- This release does not bind a Superchat, enable intake, submit a campaign or mutate production Chrome.
- Child chats remain reasoning-only and `.agent/tasks` remains the executable repository-work contract.

## Verification

Focused verification covers successful non-mutating adoption plus rejection of unexpected root entries, missing Chromium identity and symlinks. Full exact-SHA CI is required before release.

## Rollback

Rollback target is Local Agent 4.20.1 at `06f77d0b8f3d8a948f842840ac5901ed2e81d917`. Profile adoption writes only isolated lab metadata/directories; it does not rewrite the adopted browser profile.
