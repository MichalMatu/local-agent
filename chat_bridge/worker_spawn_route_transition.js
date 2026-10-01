(() => {
  "use strict";

  const PROVISIONAL_ROUTE_WAIT_MS = 10_000;
  const PROVISIONAL_ROUTE_POLL_MS = 100;
  const originalSubmitConversationSpawnBootstrap = submitConversationSpawnBootstrap;
  const originalReconcileConversationSpawn = reconcileConversationSpawn;

  function provisionalConversationSpawnUrl(rawUrl) {
    try {
      const url = new URL(String(rawUrl || ""));
      if (url.protocol !== "https:" || !["chatgpt.com", "chat.openai.com"].includes(url.hostname)) {
        return false;
      }
      const path = url.pathname.replace(/\/+$/, "");
      return /^\/uc\/[^/]+$/.test(path) && !url.hash;
    } catch (_error) {
      return false;
    }
  }

  async function claimedSpawnTab(intent) {
    let tab;
    try {
      tab = await chrome.tabs.get(intent.tab_id);
    } catch (error) {
      return { ok: false, reason: "spawn_tab_unavailable", error: String(error) };
    }
    if (!tab?.id) return { ok: false, reason: "spawn_tab_unavailable" };
    if (!await conversationSpawnTabClaimMatches(intent.transaction_id, tab.id)) {
      return { ok: false, reason: "spawn_tab_claim_mismatch" };
    }
    return { ok: true, tab };
  }

  async function waitForCanonicalConversation(intent) {
    const deadline = Date.now() + PROVISIONAL_ROUTE_WAIT_MS;
    while (Date.now() < deadline) {
      const claimed = await claimedSpawnTab(intent);
      if (!claimed.ok) return claimed;
      const canonical = normalizeConversationUrl(String(claimed.tab.url || ""));
      if (canonical) {
        return { ok: true, reason: "canonical_child_route", childConversationUrl: canonical };
      }
      if (!provisionalConversationSpawnUrl(claimed.tab.url)) {
        return {
          ok: false,
          reason: "spawn_submission_ambiguous",
          route: "unexpected_after_provisional"
        };
      }
      await new Promise((resolve) => setTimeout(resolve, PROVISIONAL_ROUTE_POLL_MS));
    }
    return { ok: false, reason: "spawn_submission_ambiguous", route: "provisional_timeout" };
  }

  async function reconcileAfterProvisionalRoute(intent, fallback) {
    const claimed = await claimedSpawnTab(intent);
    if (!claimed.ok) return claimed;
    if (!provisionalConversationSpawnUrl(claimed.tab.url)) return fallback;

    const settled = await waitForCanonicalConversation(intent);
    if (!settled.ok) return settled;
    return originalReconcileConversationSpawn(intent);
  }

  globalThis.submitConversationSpawnBootstrap = async (intent) => {
    const result = await originalSubmitConversationSpawnBootstrap(intent);
    if (result?.ok || result?.reason !== "spawn_submission_ambiguous") return result;
    return reconcileAfterProvisionalRoute(intent, result);
  };

  globalThis.reconcileConversationSpawn = async (intent) => {
    const claimed = await claimedSpawnTab(intent);
    if (!claimed.ok) return claimed;
    if (!provisionalConversationSpawnUrl(claimed.tab.url)) {
      return originalReconcileConversationSpawn(intent);
    }

    const settled = await waitForCanonicalConversation(intent);
    if (!settled.ok) return settled;
    return originalReconcileConversationSpawn(intent);
  };
})();
