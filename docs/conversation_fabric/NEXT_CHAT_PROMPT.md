# Next chat prompt — primary Chrome child lifecycle implementation

Use the following in one new parent ChatGPT conversation.

---

Continue `MichalMatu/local-agent`, but do not use prior-chat memory as source of truth.

First read fresh from current `main`:

1. `AGENTS.md`
2. `docs/CURRENT_HANDOFF.md`
3. `docs/GOLDEN_STANDARD.md`
4. `docs/OPERATIONS.md`
5. `docs/conversation_fabric/README.md`
6. `docs/conversation_fabric/CURRENT_PLAN.md`

The current goal is **not** another isolated-profile login repair and not yet the final live Superchat acceptance.

Implement the architecture correction: production Conversation Fabric child chats must be created and managed as normal tabs in the operator's already authenticated primary Chrome session through the installed Chat Bridge. Do not launch a second Chrome/Chromium process, do not create or migrate a separate ChatGPT profile, do not copy cookies and do not add manual Cloudflare/login recovery to the normal flow.

Reuse existing browser-side primitives rather than rebuilding them:

- `chat_bridge/worker_spawn.js` transaction-safe tab creation/recovery/bootstrap primitives;
- Chat Bridge `chrome.tabs` / `chrome.scripting` permissions;
- existing content-script composer interaction;
- canonical child URL and transaction/digest ownership rules.

The current `scripts/conversation_live_slice_browser.cjs` production path still launches a Playwright persistent context. Replace that production dependency with primary-Chrome/Chat-Bridge control while preserving fail-closed tab ownership, duplicate-submit protection, bounded readiness checks and child observe/close behavior.

Keep isolated Chromium/profile automation only for deterministic synthetic tests and CI.

Add focused regression coverage that proves production mode does not launch or require a second browser/profile. Run the exact relevant verification/CI. Do not weaken repository execution authority: children remain reasoning-only and only the parent may request one exact target-bound `.agent/tasks` execution when later live acceptance justifies it.

After the primary-Chrome path is implemented and verified, update the current handoff with the exact candidate SHA/evidence and make the next milestone the bounded real-code Superchat acceptance.

---
