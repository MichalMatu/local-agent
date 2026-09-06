(() => {
  const GUARD_VERSION = 1;
  const existingGuard = globalThis.__localAgentChatExhaustionGuard;
  if (existingGuard?.version === GUARD_VERSION) return;
  try {
    existingGuard?.dispose?.();
  } catch (_error) {
    // Ignore stale extension contexts and replace them with the current guard.
  }

  const protocol = globalThis.LocalAgentBridgeProtocol;
  const dom = globalThis.LocalAgentChatDomContract;
  if (!protocol || !dom) return;
  const { normalizeConversationUrl, fnv1a32 } = protocol;

  let scanTimer = null;
  let lastReportedSignature = "";

  async function scan() {
    const conversationUrl = normalizeConversationUrl(location.href);
    if (!conversationUrl) return;
    const found = dom.findConversationExhaustion(document);
    if (!found) return;
    const signature = fnv1a32(
      `${conversationUrl}\n${found.assistantIdentity}\n${dom.CONVERSATION_LIMIT_TEXT}`
    );
    if (signature === lastReportedSignature) return;
    try {
      const response = await chrome.runtime.sendMessage({
        type: "bridge:conversation-exhausted",
        conversationUrl,
        assistantIdentity: found.assistantIdentity,
        signature
      });
      if (response?.ok) lastReportedSignature = signature;
    } catch (error) {
      console.warn("Local Agent Chat Bridge exhaustion report failed:", error);
    }
  }

  function scheduleScan() {
    if (scanTimer !== null) clearTimeout(scanTimer);
    scanTimer = setTimeout(() => {
      scanTimer = null;
      scan().catch((error) => console.warn(error));
    }, 250);
  }

  const observerTarget = document.body || document.documentElement;
  const observer = observerTarget ? new MutationObserver(scheduleScan) : null;
  if (observer && observerTarget) {
    observer.observe(observerTarget, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class", "data-message-author-role", "data-message-id"]
    });
  }
  scheduleScan();
  const retryInterval = setInterval(() => {
    scan().catch((error) => console.warn(error));
  }, 5000);

  const messageListener = (message, _sender, sendResponse) => {
    if (message?.type !== "bridge:exhaustion-capabilities") return false;
    const expectedUrl = normalizeConversationUrl(String(message.expectedUrl || ""));
    const currentUrl = normalizeConversationUrl(location.href);
    sendResponse({
      ok: Boolean(expectedUrl && expectedUrl === currentUrl),
      reason: expectedUrl && expectedUrl === currentUrl ? "ready" : "wrong_conversation",
      guardVersion: GUARD_VERSION
    });
    return false;
  };
  chrome.runtime.onMessage.addListener(messageListener);

  globalThis.__localAgentChatExhaustionGuard = {
    version: GUARD_VERSION,
    dispose() {
      try { chrome.runtime.onMessage.removeListener(messageListener); } catch (_error) {}
      try { observer?.disconnect(); } catch (_error) {}
      if (scanTimer !== null) clearTimeout(scanTimer);
      clearInterval(retryInterval);
    }
  };
})();
