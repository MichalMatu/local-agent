(() => {
  const GUARD_VERSION = 2;
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
  let lastReportedExhaustionSignature = "";
  let lastRecoverableSignature = "";
  let assistantErrorInFlight = false;
  let retryTimer = null;
  let retryWatchdog = null;

  function latestMessage(role) {
    const messages = document.querySelectorAll(`[data-message-author-role="${role}"]`);
    if (!messages.length) return null;
    const latest = messages[messages.length - 1];
    const text = latest.innerText || latest.textContent || "";
    const stableId = latest.getAttribute("data-message-id") || latest.getAttribute("data-testid") || latest.id || "";
    return { text, identity: stableId || `${role}:${messages.length}:${fnv1a32(text)}` };
  }

  function assistantIsGenerating() {
    const buttons = document.querySelectorAll(
      'button[data-testid="stop-button"], button[data-testid="composer-stop-button"]'
    );
    return Array.from(buttons).some((button) => {
      if (typeof button.checkVisibility === "function") {
        return button.checkVisibility({ checkVisibilityCSS: true, checkOpacity: true });
      }
      return !button.hidden;
    });
  }

  function buttonIsUsable(button) {
    if (!(button instanceof HTMLButtonElement) || !button.isConnected || button.disabled) return false;
    if (typeof button.checkVisibility === "function") {
      return button.checkVisibility({ checkVisibilityCSS: true, checkOpacity: true });
    }
    return !button.hidden;
  }

  function clearRetryTimers() {
    if (retryTimer !== null) clearTimeout(retryTimer);
    if (retryWatchdog !== null) clearTimeout(retryWatchdog);
    retryTimer = null;
    retryWatchdog = null;
  }

  function recoverableSnapshot(conversationUrl) {
    const found = dom.findRecoverableAssistantError(document);
    if (!found) return null;
    const user = latestMessage("user");
    if (!user) return null;
    const signature = fnv1a32(
      `${conversationUrl}\n${user.identity}\n${found.kind}\n${found.assistantIdentity}`
    );
    return { conversationUrl, found, user, signature };
  }

  function snapshotStillCurrent(snapshot) {
    const currentUrl = normalizeConversationUrl(location.href);
    if (!currentUrl || currentUrl !== snapshot.conversationUrl) return null;
    const current = recoverableSnapshot(currentUrl);
    if (!current || current.signature !== snapshot.signature || current.user.identity !== snapshot.user.identity) return null;
    return current;
  }

  function armRetryWatchdog(snapshot, remainingChecks = 8) {
    if (retryWatchdog !== null) clearTimeout(retryWatchdog);
    retryWatchdog = setTimeout(() => {
      retryWatchdog = null;
      const unchanged = snapshotStillCurrent(snapshot);
      if (!unchanged) return;
      if (assistantIsGenerating()) {
        if (remainingChecks > 1) armRetryWatchdog(snapshot, remainingChecks - 1);
        return;
      }
      // ChatGPT may reuse the same assistant error node after Retry. Once generation has
      // stopped, allow the unchanged error to be reported again so durable attempt
      // accounting can advance to the hard cap instead of stalling on DOM identity reuse.
      lastRecoverableSignature = "";
      scheduleScan();
    }, 8000);
  }

  async function authorizeAndRetry(snapshot) {
    retryTimer = null;
    let current = snapshotStillCurrent(snapshot);
    if (!current || assistantIsGenerating() || !buttonIsUsable(current.found.button)) return;

    let response;
    try {
      response = await chrome.runtime.sendMessage({
        type: "bridge:authorize-assistant-retry",
        conversationUrl: current.conversationUrl,
        kind: current.found.kind,
        assistantIdentity: current.found.assistantIdentity,
        userIdentity: current.user.identity,
        userText: current.user.text.slice(0, 12000),
        signature: current.signature
      });
    } catch (error) {
      console.warn("Local Agent Chat Bridge assistant retry authorization failed:", error);
      return;
    }
    if (!response?.ok) return;

    current = snapshotStillCurrent(snapshot);
    if (!current || assistantIsGenerating() || !buttonIsUsable(current.found.button)) return;
    try {
      current.found.button.click();
    } catch (error) {
      console.warn("Local Agent Chat Bridge assistant retry click failed:", error);
      return;
    }

    armRetryWatchdog(snapshot);
  }

  function scheduleAssistantRetry(snapshot, delayMs) {
    if (retryTimer !== null) return;
    const boundedDelay = Math.max(500, Math.min(30000, Number(delayMs) || 1500));
    retryTimer = setTimeout(() => {
      authorizeAndRetry(snapshot).catch((error) => console.warn(error));
    }, boundedDelay);
  }

  async function scanConversationExhaustion(conversationUrl) {
    const found = dom.findConversationExhaustion(document);
    if (!found) return;
    const signature = fnv1a32(
      `${conversationUrl}\n${found.assistantIdentity}\n${dom.CONVERSATION_LIMIT_TEXT}`
    );
    if (signature === lastReportedExhaustionSignature) return;
    try {
      const response = await chrome.runtime.sendMessage({
        type: "bridge:conversation-exhausted",
        conversationUrl,
        assistantIdentity: found.assistantIdentity,
        signature
      });
      if (response?.ok) lastReportedExhaustionSignature = signature;
    } catch (error) {
      console.warn("Local Agent Chat Bridge exhaustion report failed:", error);
    }
  }

  async function scanRecoverableAssistantError(conversationUrl) {
    const snapshot = recoverableSnapshot(conversationUrl);
    if (!snapshot) {
      lastRecoverableSignature = "";
      clearRetryTimers();
      return;
    }
    if (snapshot.signature === lastRecoverableSignature || assistantErrorInFlight) return;

    assistantErrorInFlight = true;
    try {
      const response = await chrome.runtime.sendMessage({
        type: "bridge:assistant-error",
        conversationUrl,
        kind: snapshot.found.kind,
        assistantIdentity: snapshot.found.assistantIdentity,
        userIdentity: snapshot.user.identity,
        userText: snapshot.user.text.slice(0, 12000),
        signature: snapshot.signature
      });
      if (!response?.ok) return;
      lastRecoverableSignature = snapshot.signature;
      if (response.retryEligible) scheduleAssistantRetry(snapshot, response.retryAfterMs);
    } catch (error) {
      console.warn("Local Agent Chat Bridge assistant error report failed:", error);
    } finally {
      assistantErrorInFlight = false;
    }
  }

  async function scan() {
    const conversationUrl = normalizeConversationUrl(location.href);
    if (!conversationUrl) return;
    await scanConversationExhaustion(conversationUrl);
    await scanRecoverableAssistantError(conversationUrl);
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
      attributeFilter: ["class", "hidden", "style", "data-testid", "data-message-author-role", "data-message-id"]
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
      clearRetryTimers();
    }
  };
})();
