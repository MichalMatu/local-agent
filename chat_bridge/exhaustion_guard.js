(() => {
  const GUARD_VERSION = 3;
  const RETRY_RECHECK_GRACE_MS = 8000;
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
  let retryRecheckTimer = null;
  let retryAwaiting = null;

  function latestMessage(role) {
    const messages = document.querySelectorAll(`[data-message-author-role="${role}"]`);
    if (!messages.length) return null;
    const latest = messages[messages.length - 1];
    const text = latest.innerText || latest.textContent || "";
    // Use transcript position plus content rather than ChatGPT's DOM message id. The DOM id
    // may be regenerated when the page is rehydrated, while the same transcript turn keeps
    // the same ordinal and text. This keeps the worker's durable retry budget stable across
    // a page/content-script restart without allowing a later turn to inherit that budget.
    const identity = `${role}:${messages.length}:${fnv1a32(text)}`;
    return { text, identity };
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

  function clearRetryRecheck() {
    if (retryRecheckTimer !== null) clearTimeout(retryRecheckTimer);
    retryRecheckTimer = null;
    retryAwaiting = null;
  }

  function clearRetryTimers() {
    if (retryTimer !== null) clearTimeout(retryTimer);
    retryTimer = null;
    clearRetryRecheck();
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

  function armRetryRecheck(snapshot) {
    if (retryRecheckTimer !== null) clearTimeout(retryRecheckTimer);
    retryAwaiting = {
      signature: snapshot.signature,
      notBefore: Date.now() + RETRY_RECHECK_GRACE_MS
    };
    retryRecheckTimer = setTimeout(() => {
      retryRecheckTimer = null;
      scheduleScan();
    }, RETRY_RECHECK_GRACE_MS);
  }

  async function authorizeAndRetry(snapshot, retryContext) {
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
        signature: current.signature,
        bindingRevision: retryContext.bindingRevision,
        generation: retryContext.generation
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

    // ChatGPT sometimes reuses the exact timeout card while Retry is generating. Do not
    // rely on a fixed number of watchdog checks: after an initial grace period the normal
    // mutation/5-second scan loop keeps waiting until generation actually stops. That
    // makes long responses recoverable without permitting a rapid duplicate Retry click.
    armRetryRecheck(snapshot);
  }

  function scheduleAssistantRetry(snapshot, delayMs, retryContext) {
    if (retryTimer !== null) return;
    const boundedDelay = Math.max(500, Math.min(30000, Number(delayMs) || 1500));
    retryTimer = setTimeout(() => {
      authorizeAndRetry(snapshot, retryContext).catch((error) => console.warn(error));
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

    if (retryAwaiting && retryAwaiting.signature !== snapshot.signature) {
      clearRetryRecheck();
    }
    if (retryAwaiting?.signature === snapshot.signature) {
      if (Date.now() < retryAwaiting.notBefore || assistantIsGenerating()) return;
      clearRetryRecheck();
      lastRecoverableSignature = "";
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
      if (!response?.ok) {
        if (response?.reason === "assistant_error_wrong_tab") {
          lastRecoverableSignature = snapshot.signature;
        }
        return;
      }
      lastRecoverableSignature = snapshot.signature;
      if (response.retryEligible) {
        scheduleAssistantRetry(snapshot, response.retryAfterMs, {
          bindingRevision: response.bindingRevision,
          generation: response.generation
        });
      }
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
    if (!message || !["bridge:exhaustion-capabilities", "bridge:assistant-recovery-kick"].includes(message.type)) {
      return false;
    }
    const expectedUrl = normalizeConversationUrl(String(message.expectedUrl || ""));
    const currentUrl = normalizeConversationUrl(location.href);
    const ready = Boolean(expectedUrl && expectedUrl === currentUrl);
    const snapshot = ready ? recoverableSnapshot(currentUrl) : null;
    if (message.type === "bridge:assistant-recovery-kick" && ready && snapshot &&
        retryTimer === null && retryAwaiting === null && !assistantErrorInFlight) {
      lastRecoverableSignature = "";
      scheduleScan();
    }
    sendResponse({
      ok: ready,
      reason: ready ? "ready" : "wrong_conversation",
      guardVersion: GUARD_VERSION,
      recoverableAssistantError: Boolean(snapshot),
      assistantGenerating: ready ? assistantIsGenerating() : false
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
