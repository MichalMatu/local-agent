# Conversation Fabric current plan

## Goal

Keep the accepted browser-native Conversation Fabric path correct under real service-worker/reload recovery and prove terminal no-replay end to end in the operator's already authenticated primary Chrome model.

The separate-profile production approach is retired. Same-browser multi-child reasoning/transport has already passed live acceptance; current work is lifecycle/recovery hardening and production-path E2E coverage.

## Implemented production model

Production Conversation Fabric uses:

- one managed parent Superchat in the operator's normal Chrome;
- accepted deployed Chat Bridge remains `0.8.3` until the verified `0.8.4` observability candidate is explicitly loaded;
- a dedicated trailing `LOCAL_AGENT_CF` control envelope, separate from legacy LAB controls;
- the existing `worker_spawn.js` `chrome.tabs` / `chrome.scripting` ownership primitives;
- ordinary child tabs in the same authenticated Chrome session;
- durable `chrome.storage.local` campaign/result state;
- exact transaction/tab/request/bootstrap/current-child-URL ownership evidence;
- bounded stable child-result capture and exact owned-tab cleanup;
- GitHub `conversation_controls` for managed parent pacing;
- the existing GitHub-control alarm for normal campaign polling;
- durable terminal parent feedback at-most-once semantics.

Production does **not** launch another browser, create/migrate another ChatGPT profile, copy cookies, use CDP as a second production control plane, add Native Messaging, create a Local Agent-to-browser RPC, or use LAB scheduling for normal Conversation Fabric pacing.

## Control mechanics

A parent delegation ends with:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"delegate","children":[
  {"id":"audit","role":"research","prompt":"..."},
  {"id":"verify","role":"verification","prompt":"..."}
]}
LOCAL_AGENT_CF>>>
```

The Bridge admits this only from the exact top-frame managed parent. Each child bootstrap states that it is reasoning-only and may not create Local Agent tasks, run machine commands, mutate repositories or make the final parent decision.

When a campaign is running, the existing minute GitHub-control alarm automatically observes/collects stable results while the parent and Master are enabled. The parent waits for actual feedback. An explicit collect block is available for bounded observation recovery without resubmitting child prompts; it is not the normal polling mechanism.

Collect control:

```text
<<<LOCAL_AGENT_CF
{"schema_version":1,"action":"collect","campaign_id":"cf-..."}
LOCAL_AGENT_CF>>>
```

Results must carry the expected completion marker and be stable across repeated observations before adoption. Each stable result is durably stored before sibling completion or tab cleanup.

## Result durability and operator recovery

- Stable child work is not only part of the campaign record: it is copied into a separate bounded Result Vault before tab cleanup or terminal feedback.
- Result Vault retention is independent of the short completed-campaign history window and preserves enough metadata to identify the original child and conversation.
- A managed parent may use a read-only `inspect` control to recover current child state and previously captured/vaulted result text without replaying terminal feedback.
- A managed parent may explicitly `retire` one problematic child. Retirement never resubmits its bootstrap and closes a tab only through the existing exact ownership proof.
- Any already-captured result survives retirement. A retired/missing child is reported as retryable missing coverage so the parent may intentionally issue a new delegation with a new child id.
- Automatic replacement/replay remains forbidden.
## Restart and terminal-delivery contract

- Submitted children are never blindly replayed after service-worker/session restart.
- A post-submit `spawn_submission_ambiguous` result is recoverable evidence uncertainty, not permission to resend the bootstrap or immediately terminally fail an actually submitted child.
- Reattachment after lost session ownership requires exact page transaction/request/bootstrap/current-child-URL evidence; tab id alone is insufficient.
- An ambiguous/submitting child with a durable exact tab/transaction/request/bootstrap claim remains eligible for bounded identity reconciliation across worker restart; it is promoted only after current child-route ownership is proven.
- Transient observation failures remain pending/recoverable.
- Completed/failed cleanup closes only exact owned child tabs.
- Terminal feedback persists a campaign-specific delivery claim before the parent send boundary.
- Definite no-send clears the claim; confirmation marks delivery; an ambiguous surviving claim suppresses resend after restart.
- A new delegation for the same parent is blocked while an older terminal campaign still has undelivered feedback, preventing stale cross-campaign replay.

## Verification already encoded

Current coverage includes:

- positive/negative protocol tests;
- worker lifecycle tests for multi-child delegation, dedupe, managed-parent admission, stable collection, recovery and terminal delivery guards;
- content protocol `18` / source-candidate manifest `0.8.4` contract tests;
- real headless Chromium DOM/browser smoke for parent control, child result capture and ownership checks;
- full repository CI through `bridge-browser`, test, coverage, Python 3.14 and macOS smoke jobs.

Some browser smoke still calls Fabric helpers directly for parts of restart/recovery, so it is not by itself the complete end-to-end restart acceptance.

## Next work — complete restart/reload E2E

Add/maintain one deterministic browser acceptance that traverses the production routing rather than helper-only shortcuts:

1. real parent content discovers/submits a delegate control;
2. spawn four ordinary child tabs;
3. force at least three children through delayed/provisional post-submit routing that would previously surface `spawn_submission_ambiguous`, while verifying each bootstrap is sent exactly once;
4. keep those children recoverable rather than terminally failed, preserving their exact owned tab and transaction/request/bootstrap claims;
5. interrupt/reload the service-worker/extension lifecycle while at least one ambiguous child is still awaiting identity proof;
6. recover durable state and exact child ownership without bootstrap replay or duplicate child creation;
7. let all four tabs reach canonical child URLs and prove identity using the existing transaction/request/bootstrap/current-route/current-child-URL evidence;
8. have all four children produce final results and durably capture all four before cleanup;
9. exercise one additional transient observation failure and later successful recovery;
10. let normal worker polling reach terminal state;
11. close only exact owned child tabs after durable result capture;
12. deliver terminal feedback exactly once with 4/4 recovered results;
13. reload/restart again and poll again;
14. assert no completed-campaign replay and no orphaned completed child;
15. separately prove a truly ambiguous child that never reaches verifiable identity fails closed after bounded recovery with no second submit and no replacement tab.

Prefer a genuine MV3 service-worker/extension restart if Chromium exposes a deterministic harness primitive. If not, use the strongest reliable production-shaped restart and document the remaining limitation explicitly.

## Execution authority

Conversation Fabric is reasoning transport only. If parent synthesis justifies machine work, resolve the actual target through the canonical runtime catalog, require `execution_enabled=true`, and use the exact canonical target `agent_binding`. The current catalog enables `local-agent`, but self-execution receives no special bypass.

## Stop conditions

Stop rather than weakening safety if:

- the parent is not a managed exact conversation/tab;
- child tab/transaction ownership is ambiguous;
- a child obtains machine execution authority;
- result identity is missing/unstable beyond bounded retry;
- GitHub conversation-control ownership/generation is uncertain;
- target catalog/binding identity is uncertain;
- equivalent expensive tasks execute twice;
- terminal feedback could be replayed after an ambiguous send or newer campaign.

A missing isolated profile, isolated-profile login failure or Cloudflare challenge is not a production blocker because that path is no longer part of the accepted architecture.

## Success criteria

The current milestone passes only when a managed parent can delegate multiple reasoning-only child tabs inside the already-running normal Chrome session, preserve stable results across worker/reload interruption, recover transient observation, clean exact owned tabs, deliver terminal feedback at most once, survive another reload/poll without replay, and—only if justified—cause no more than one deterministic target-bound Local Agent execution.
