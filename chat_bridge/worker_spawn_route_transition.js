(() => {
  "use strict";

  const PROVISIONAL_ROUTE_WAIT_MS = 60_000;
  const PROVISIONAL_ROUTE_POLL_MS = 100;
  const CHILD_IDENTITY_WAIT_MS = 30_000;
  const CHILD_IDENTITY_POLL_MS = 100;
  const DOM_CONTRACT_RETRY_MS = 1000;
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

  async function installConversationSpawnDomContract(tabId) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId, frameIds: [0] },
        files: ["dom_contract.js"]
      });
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: "spawn_dom_contract_unavailable", error: String(error) };
    }
  }

  async function probeConversationSpawnUserIdentity(tabId, expectedText, expectedDigest) {
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId, frameIds: [0] },
        func: (expected, digest) => {
          const contract = globalThis.LocalAgentChatDomContract;
          if (
            !contract ||
            typeof contract.messageElements !== "function" ||
            typeof contract.normalizedText !== "function"
          ) {
            return { ok: false, reason: "spawn_dom_contract_unavailable" };
          }

          const expectedNormalized = contract.normalizedText(expected);
          const messages = contract.messageElements(document, "user");
          const latest = messages[messages.length - 1];
          const actual = latest?.innerText || latest?.textContent || "";
          if (
            latest &&
            contract.normalizedText(actual) === expectedNormalized
          ) {
            return {
              ok: true,
              exactUserMessage: true,
              identitySource: "dom_contract",
              userMessageCount: messages.length,
              exactTextCandidateCount: 0,
              mainPresent: Boolean(document.querySelector("main, [role=\"main\"]"))
            };
          }

          const latestTextContent = contract.normalizedText(latest?.textContent || "");
          const latestTurn = latest?.closest?.('[data-turn-key]') || latest;
          const latestTurnTextContent = contract.normalizedText(latestTurn?.textContent || "");
          if (
            latest &&
            messages.length === 1 &&
            expectedNormalized &&
            (
              latestTextContent.includes(expectedNormalized) ||
              latestTurnTextContent.includes(expectedNormalized)
            )
          ) {
            return {
              ok: true,
              exactUserMessage: true,
              identitySource: "dom_contract_embedded_text",
              userMessageCount: 1,
              exactTextCandidateCount: 0,
              mainPresent: Boolean(document.querySelector("main, [role=\"main\"]"))
            };
          }

          const scope = document.querySelector("main") || document.querySelector('[role="main"]');
          if (!scope || !expectedNormalized || !digest) {
            return {
              ok: true,
              exactUserMessage: false,
              identitySource: null,
              userMessageCount: messages.length,
              exactTextCandidateCount: 0,
              mainPresent: Boolean(scope)
            };
          }

          const candidateContainers = new Set();
          const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
          let node = walker.nextNode();
          while (node) {
            if (String(node.nodeValue || "").includes(digest)) {
              let element = node.parentElement;
              while (element && scope.contains(element)) {
                const text = contract.normalizedText(element.innerText || element.textContent || "");
                if (text === expectedNormalized) {
                  candidateContainers.add(element);
                  break;
                }
                element = element.parentElement;
              }
            }
            node = walker.nextNode();
          }

          const minimalCandidates = Array.from(candidateContainers).filter((candidate) =>
            !Array.from(candidateContainers).some(
              (other) => other !== candidate && candidate.contains(other)
            )
          );
          return {
            ok: true,
            exactUserMessage: minimalCandidates.length === 1,
            identitySource: minimalCandidates.length === 1 ? "dom_exact_text" : null,
            userMessageCount: messages.length,
            exactTextCandidateCount: minimalCandidates.length,
            mainPresent: true
          };
        },
        args: [String(expectedText || ""), String(expectedDigest || "")]
      });
      const result = results?.[0]?.result;
      return result && typeof result === "object"
        ? result
        : { ok: false, reason: "spawn_dom_contract_unavailable" };
    } catch (error) {
      return { ok: false, reason: "spawn_dom_contract_unavailable", error: String(error) };
    }
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
    let domContractReady = false;
    let nextDomContractAttempt = 0;
    let lastIdentityProbe = null;
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

      if (!domContractReady && Date.now() >= nextDomContractAttempt) {
        const installed = await installConversationSpawnDomContract(claimed.tab.id);
        domContractReady = installed.ok === true;
        lastIdentityProbe = installed.ok ? lastIdentityProbe : installed;
        nextDomContractAttempt = Date.now() + DOM_CONTRACT_RETRY_MS;
      }
      if (domContractReady) {
        const identity = await probeConversationSpawnUserIdentity(
          claimed.tab.id,
          intent.bootstrap_text,
          intent.child_request_digest
        );
        lastIdentityProbe = identity;
        if (identity?.ok && identity.exactUserMessage === true) {
          return {
            ok: true,
            reason: "identity_discovered",
            childConversationUrl,
            identitySource: String(identity.identitySource || "dom_contract")
          };
        }
        if (identity?.ok && identity.userMessageCount === 1) {
          const routeEvidence = await inspectConversationSpawnContentState(intent);
          lastIdentityProbe = { ...identity, routeEvidence };
          if (
            routeEvidence?.ok &&
            routeEvidence.claimState === "submitted" &&
            routeEvidence.sawProvisionalRoute === true &&
            routeEvidence.contentRoute === "child" &&
            routeEvidence.composerPresent === true &&
            routeEvidence.composerHasText === false
          ) {
            return {
              ok: true,
              reason: "identity_discovered",
              childConversationUrl,
              identitySource: "owned_provisional_canonical_transition"
            };
          }
        }
        if (identity?.reason === "spawn_dom_contract_unavailable") {
          domContractReady = false;
        }
      }
      await new Promise((resolve) => setTimeout(resolve, CHILD_IDENTITY_POLL_MS));
    }

    const diagnostic = await inspectConversationSpawnContentState(intent);
    return {
      ok: false,
      reason: "spawn_submission_ambiguous",
      route: "child_identity_timeout",
      diagnostic: {
        ...diagnostic,
        identityProbe: lastIdentityProbe
      }
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
