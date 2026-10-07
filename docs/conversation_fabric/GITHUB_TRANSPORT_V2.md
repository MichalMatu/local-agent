# Conversation Fabric GitHub transport v2

## Status

This is an incremental design for moving Conversation Fabric machine communication out of the ChatGPT parent DOM. It is intentionally inactive in the first slice. The current browser-native Fabric remains the production path until the GitHub-first path has passed its own compatibility and live acceptance gates.

The architecture remains:

- Superchat owns intent and final synthesis.
- Local Agent owns workflow/campaign truth and is the trusted GitHub writeback actor.
- GitHub is the durable control/evidence plane.
- Chat Bridge is the browser driver and owns only browser-local effect/recovery state.
- Child chats are reasoning-only.
- Repository execution authority remains outside Conversation Fabric and must still be resolved through the canonical runtime catalog for executable Local Agent work.

No second scheduler is introduced. GitHub-first Fabric intake will later reuse the existing GitHub-control alarm.

## Why a separate browser dispatch envelope exists

The existing `.agent/conversation/requests/<id>.json` operator request is semantic planner input. It contains bounded child reasoning scope and repository context, but it is not the exact browser effect.

The Bridge should not turn semantic planner input into a child prompt. Local Agent must first admit the operator request and derive immutable ChildRequest/bootstrap material. Only then is a browser dispatch published.

This keeps semantic authority out of the browser extension.

The v1 browser dispatch envelope therefore contains only:

- one immutable dispatch id;
- the admitted operator request id and digest;
- the deterministic campaign id;
- the canonical parent conversation URL;
- 1..4 reasoning children;
- for each child: child id, ChildRequest id, role, exact spawn transaction id, ChildRequest digest, exact bootstrap digest, and exact bootstrap text.

It deliberately does **not** expose the following as dispatch routing/authority fields:

- `agent_binding` or repository identity;
- repository execution authority;
- mutable repository refs;
- scheduler resources;
- Chrome `tab_id`;
- arbitrary browser selectors;
- shell/device commands.

The exact opaque child bootstrap can still contain the already-admitted repository/binding provenance required by the existing ChildRequest contract; Bridge must not reinterpret that provenance as execution authority. The Bridge assigns runtime tab identity locally.

## Idempotency

A dispatch id is immutable.

- unseen id + valid payload: admissible;
- same id + byte-equivalent canonical payload: replay/no-op or recovery;
- same id + different canonical payload: permanent conflict;
- intentional retry after a terminal/ambiguous browser transaction uses a new dispatch/ChildRequest identity according to the owning Local Agent workflow.

The browser spawn transaction keeps the existing exact request/bootstrap digest checks underneath this envelope.

## Ownership split

GitHub durable state should record coarse machine intent/evidence. Browser-local transaction phases must stay with Bridge because they surround the actual DOM effect.

The intended browser-local sequence is:

`prepared -> draft_verified -> submit_armed -> submitted -> response_started`

A future spawn-protocol hardening slice will journal this page-local claim before the first composer mutation. GitHub should not command the transition between `submit_armed` and `submitted`.

## Planned transport sequence

1. Superchat/Local Agent publishes or admits `.agent/conversation/requests/<request-id>.json`.
2. Local Agent validates it and derives exact ChildRequest + bootstrap records.
3. Local Agent publishes one immutable browser-dispatch record/index for the managed parent.
4. The existing GitHub-control poll reads the dispatch surface; no new timer is created.
5. Bridge validates the dispatch and projects each child into the existing conversation-spawn browser intent with `tab_id=null`.
6. Bridge performs the Chrome effects and preserves browser-local recovery evidence.
7. Bridge exposes bounded receipt/result evidence locally.
8. Local Agent, not the extension, publishes durable progress/result evidence back to GitHub.
9. Parent wake/synthesis reads GitHub-authoritative result state.

## Migration / rollback

The path is additive at first.

- Current `LOCAL_AGENT_CF` DOM delegation remains a compatibility fallback.
- The dispatch model is initially pure and not loaded by the extension manifest/service worker.
- The first live intake must be opt-in.
- Disabling GitHub-first intake restores the current Fabric without state conversion.
- Do not dual-authoritatively write campaign lifecycle into both GitHub and `chrome.storage.local`; keep one owner for each state domain during migration.
- Only after production acceptance should parent DOM control parsing be demoted or removed.

## First implementation slice

`chat_bridge/github_fabric_dispatch_model.js` defines the inactive validation/projection contract.

It validates that GitHub can specify an immutable browser effect without gaining runtime Chrome identity or repository execution authority. `toConversationSpawnIntent()` adds only `tab_id=null`, leaving actual tab ownership to the Bridge.

The next slice should add read-only GitHub intake using the existing control poll and feed the validated dispatch into the existing Fabric lifecycle. It must remain feature-gated until restart/idempotency/browser acceptance is proven.
