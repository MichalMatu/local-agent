# Conversation Fabric current plan

## Goal

Keep the accepted browser-native Conversation Fabric path reliable for repeated bounded delegation cycles inside one parent/project: finish one task campaign cleanly, then start the next without ownership, result or terminal-delivery leakage.

The separate-profile production approach is retired. Same-browser multi-child reasoning/transport, lifecycle/recovery and production-path E2E coverage are complete; current work is the final sequential-cycle hardening stage.

## Implemented production model

Production Conversation Fabric uses:

- one managed parent Superchat in the operator's normal Chrome;
- source manifest remains Chat Bridge `0.8.4`; after a field submit/retry spam regression the operator disabled the live Bridge. PR #171 fixes the source path at `main@59c5d699bc32283ebb98fc026f76128ec9db6d2a`, but that post-fix source has not yet been reloaded/live-accepted; optional `operator_status_url` activation remains unverified;
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

The deterministic real-extension browser smoke now traverses the production routing for the lifecycle/recovery contract; direct helper calls are limited to harness setup, forced time advancement, bounded test-state inspection/awaiting and harness-only MV3 interruption, and do not replace production delegation/recovery/polling/ownership/terminal-delivery transitions.

## Restart/reload E2E — complete

`scripts/conversation_fabric_browser_smoke.cjs` now proves the complete bounded lifecycle:

1. real parent content discovers/submits a delegate control;
2. four ordinary child tabs are created in one extension-owned browser session;
3. three children pass through real post-submit ambiguous routing while every bootstrap is submitted exactly once;
4. stable sibling evidence is durably captured before the ambiguous children finish;
5. the actual MV3 service worker is stopped and woken while ambiguity is still unresolved;
6. durable campaign state and exact page ownership are reconstructed without bootstrap replay or duplicate child creation;
7. all four children recover onto canonical child URLs and exact ownership is re-proven;
8. all four final results are captured before exact owned-tab cleanup;
9. normal production alarm routing reaches terminal state;
10. terminal feedback is delivered exactly once;
11. the worker is restarted a second time and the same production poll route proves no completed-campaign replay;
12. read-only Result Vault inspection still works after child cleanup without resetting terminal delivery;
13. explicit retire plus deliberate fresh-id re-delegation proves bounded operator-controlled rollover without automatic replay;
14. an unresolved post-submit ambiguity is forced past the bounded deadline and fails closed with no second submit, replacement tab or orphaned owned tab.

The test uses CDP only as a harness mechanism to stop/reattach to Chromium's real MV3 worker target; delegation, recovery, polling, ownership, durable state and terminal delivery remain the installed extension's production paths.

## Final work — sequential delegation-cycle hardening

Keep one parent conversation responsible for exactly one project/main goal. For each bounded task, the parent may delegate 1–4 reasoning-only children, durably collect and synthesize their work, report missing coverage explicitly, and close only exact owned tabs. A later task must use a fresh campaign only after the earlier campaign is terminally settled.

The final proof must exercise at least two consecutive campaigns in one parent and show no zombie tabs, stale terminal feedback, bootstrap replay, duplicate child creation or campaign-state leakage. Restart, timeout and manual/retained-composer submission paths must settle deterministically or fail closed with a bounded diagnostic. Delayed automatic submission is a reliability target: it must eventually submit exactly once or report why it did not. Automatic child replacement, re-delegation and multi-goal parent supervision remain out of scope.

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

The final milestone passes when one managed parent can complete at least two successive bounded delegation campaigns for the same project: each campaign captures stable child work, reports any missing coverage, closes exact owned tabs and terminally settles before the next begins. Recovery from restart, timeout and manual/retained-composer submission must not replay prompts or leak campaign state, and any justified machine execution remains a separate parent decision through canonical target admission.
