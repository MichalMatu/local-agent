(() => {
  "use strict";

  const PROVISIONAL_ROUTE_WAIT_MS = 60_000;
  const PROVISIONAL_ROUTE_POLL_MS = 100;
  const CHILD_IDENTITY_WAIT_MS = 30_000;
  const CHILD_IDENTITY_POLL_MS = 100;
  const originalSubmitConversationSpawnBootstrap = submitConversationSpawnBootstrap;
  const originalReconcileConversationSpawn = reconcileConversationSpawn;

  function provisionalConversationSpawnUrl(rawUrl) {
    try {
      const url = new URL(String(rawUrl || ""));
      if (url.protocol !== "https:" || !["chatgpt.com", "chat.openai.com"].includes(url.hostname)) {
        return false;
      }
      const path = url.pathname.replace(/\/+$/, "");
      return Boolean(
        !url.hash && (
          /^\/uc\/[^/]+$/.test(path) ||
          /^\/c\/local-chatgpt%3a[A-Za-z0-9-]+$/i.test(path)
        )
      );
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
      if (provisionalConversationSpawnUrl(claimed.tab.url)) {
        await new Promise((resolve) => setTimeout(resolve, PROVISIONAL_ROUTE_POLL_MS));
        continue;
      }
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
    }
    const diagnostic = await inspectConversationSpawnContentState(intent);
    return {
      ok: false,
      reason: "spawn_submission_ambiguous",
      route: "provisional_timeout",
      diagnostic
    };
  }

  async function waitForChildIdentity(intent, childConversationUrl, fallback) {
    const deadline = Date.now() + CHILD_IDENTITY_WAIT_MS;
    while (Date.now() < deadline) {
      const claimed = await claimedSpawnTab(intent);
      if (!claimed.ok) return claimed;
      const canonical = normalizeConversationUrl(String(claimed.tab.url || ""));
      if (!canonical || canonical !== childConversationUrl) {
        return {
          ok: false,
          reason: "spawn_submission_ambiguous",
          route: "child_route_changed_before_identity"
        };
      }

      const reconciled = await originalReconcileConversationSpawn(intent);
      if (reconciled?.ok) {
        if (reconciled.childConversationUrl !== childConversationUrl) {
          return { ok: false, reason: "spawn_child_identity_invalid" };
        }
        return reconciled;
      }
      const reason = String(reconciled?.reason || "");
      if (![
        "spawn_submission_ambiguous",
        "spawn_content_unavailable",
        "spawn_page_not_ready"
      ].includes(reason)) {
        return reconciled || fallback;
      }
      await new Promise((resolve) => setTimeout(resolve, CHILD_IDENTITY_POLL_MS));
    }

    const diagnostic = await inspectConversationSpawnContentState(intent);
    return {
      ok: false,
      reason: "spawn_submission_ambiguous",
      route: "child_identity_timeout",
      diagnostic
    };
  }

  async function reconcileAfterAmbiguousRoute(intent, fallback) {
    const claimed = await claimedSpawnTab(intent);
    if (!claimed.ok) return claimed;

    if (provisionalConversationSpawnUrl(claimed.tab.url)) {
      const settled = await waitForCanonicalConversation(intent);
      if (!settled.ok) return settled;
      return waitForChildIdentity(intent, settled.childConversationUrl, fallback);
    }

    const canonical = normalizeConversationUrl(String(claimed.tab.url || ""));
    if (!canonical) return fallback;
    return waitForChildIdentity(intent, canonical, fallback);
  }

  globalThis.submitConversationSpawnBootstrap = async (intent) => {
    const result = await originalSubmitConversationSpawnBootstrap(intent);
    if (result?.ok || result?.reason !== "spawn_submission_ambiguous") return result;
    return reconcileAfterAmbiguousRoute(intent, result);
  };

  globalThis.reconcileConversationSpawn = async (intent) => {
    const initial = await originalReconcileConversationSpawn(intent);
    if (initial?.ok || initial?.reason !== "spawn_submission_ambiguous") return initial;
    return reconcileAfterAmbiguousRoute(intent, initial);
  };
})();
