(() => {
  const CONTENT_PROTOCOL_VERSION = 3;
  const existingBridge = globalThis.__localAgentChatBridgeState;
  if (existingBridge?.protocolVersion === CONTENT_PROTOCOL_VERSION) return;
  try {
    existingBridge?.dispose?.();
  } catch (_error) {
    // A stale extension context may already be detached; continue with a fresh listener.
  }

  globalThis.__localAgentChatBridgeLoaded = true;
  globalThis.__localAgentChatBridgeProtocolVersion = CONTENT_PROTOCOL_VERSION;

  const protocol = globalThis.LocalAgentBridgeProtocol;
  if (!protocol) throw new Error("Local Agent Chat Bridge control protocol is unavailable");
  const { normalizeConversationUrl, parseAssistantControl, controlFingerprint, fnv1a32 } = protocol;

  function findComposer() {
    return (
      document.querySelector("#prompt-textarea") ||
      document.querySelector('form [contenteditable="true"][data-lexical-editor="true"]') ||
      document.querySelector('form [contenteditable="true"]') ||
      document.querySelector("form textarea")
    );
  }

  function composerText(composer) {
    if (composer instanceof HTMLTextAreaElement || composer instanceof HTMLInputElement) {
      return composer.value || "";
    }
    return composer.innerText || composer.textContent || "";
  }

  function assistantIsGenerating() {
    return Boolean(
      document.querySelector('button[data-testid="stop-button"]') ||
      document.querySelector('button[data-testid="composer-stop-button"]')
    );
  }

  function selectContent(element) {
    const selection = window.getSelection();
    if (!selection) return;
    const range = document.createRange();
    range.selectNodeContents(element);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function setComposerText(composer, text) {
    composer.focus();
    if (composer instanceof HTMLTextAreaElement) {
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
      if (!setter) throw new Error("textarea value setter unavailable");
      setter.call(composer, text);
      composer.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    if (!(composer instanceof HTMLElement) || composer.contentEditable !== "true") {
      throw new Error("unsupported composer element");
    }
    selectContent(composer);
    const inserted = document.execCommand("insertText", false, text);
    if (!inserted) {
      composer.textContent = text;
      composer.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        inputType: "insertText",
        data: text
      }));
    }
  }

  function clearComposer(composer, insertedText) {
    if (!composer.isConnected || composerText(composer) !== insertedText) return;
    try {
      setComposerText(composer, "");
    } catch (_error) {
      // Remove only our exact unchanged insertion; preserve every operator edit.
    }
  }

  function findSendButton(composer) {
    const selectors = [
      "#composer-submit-button",
      'button[data-testid="send-button"]',
      'button[data-testid="composer-submit-button"]',
      'button[aria-label="Send prompt"]',
      'button[aria-label="Send message"]',
      'button[aria-label="Send"]'
    ];
    const form = composer.closest("form");
    const scopes = form ? [form, document] : [document];
    for (const scope of scopes) {
      for (const selector of selectors) {
        const button = scope.querySelector(selector);
        if (button instanceof HTMLButtonElement && !button.disabled) return button;
      }
    }
    return null;
  }

  function submitComposer(composer, sendButton) {
    const form = composer.closest("form");
    if (
      form instanceof HTMLFormElement &&
      sendButton.form === form &&
      sendButton.type === "submit" &&
      typeof form.requestSubmit === "function"
    ) {
      form.requestSubmit(sendButton);
      return;
    }
    sendButton.click();
  }

  async function waitForSendButton(composer, timeoutMs = 2000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (assistantIsGenerating()) return null;
      const button = findSendButton(composer);
      if (button) return button;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return null;
  }

  function latestAssistantMessage() {
    const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
    if (!messages.length) return null;
    const latest = messages[messages.length - 1];
    const text = latest.innerText || latest.textContent || "";
    const stableId = latest.getAttribute("data-message-id") || latest.getAttribute("data-testid") || latest.id || "";
    return { text, identity: stableId || `${messages.length}:${fnv1a32(text)}` };
  }

  let deliveryInFlight = false;

  async function sendFeedback(prompt, expectedUrl, deliveryId) {
    if (deliveryInFlight) return { ok: false, reason: "delivery_in_progress" };
    deliveryInFlight = true;
    try {
      return await deliverFeedback(prompt, expectedUrl, deliveryId);
    } finally {
      deliveryInFlight = false;
    }
  }

  async function deliverFeedback(prompt, expectedUrl, deliveryId) {
    const normalizedUrl = normalizeConversationUrl(expectedUrl);
    if (!normalizedUrl || normalizeConversationUrl(location.href) !== normalizedUrl) {
      return { ok: false, reason: "wrong_conversation" };
    }
    if (document.visibilityState === "prerender") return { ok: false, reason: "page_not_ready" };
    if (assistantIsGenerating()) return { ok: false, reason: "assistant_busy" };

    const composer = findComposer();
    if (!composer) return { ok: false, reason: "composer_not_found" };
    if (composerText(composer).trim()) return { ok: false, reason: "composer_not_empty" };

    try {
      setComposerText(composer, prompt);
    } catch (error) {
      return { ok: false, reason: "composer_write_failed", error: String(error) };
    }
    const insertedComposerText = composerText(composer);
    if (!insertedComposerText.trim()) return { ok: false, reason: "composer_write_failed" };

    const sendButton = await waitForSendButton(composer);
    if (!sendButton) {
      clearComposer(composer, insertedComposerText);
      return { ok: false, reason: "send_button_not_ready" };
    }

    const baseline = latestAssistantMessage()?.identity || "";
    const authorized = await chrome.runtime.sendMessage({
      type: "bridge:authorize-delivery",
      conversationUrl: normalizedUrl,
      deliveryId,
      assistantBaseline: baseline
    });
    if (!authorized?.ok) {
      clearComposer(composer, insertedComposerText);
      return { ok: false, reason: "delivery_cancelled" };
    }
    if (normalizeConversationUrl(location.href) !== normalizedUrl) {
      clearComposer(composer, insertedComposerText);
      return { ok: false, reason: "wrong_conversation" };
    }
    if (!composer.isConnected || findComposer() !== composer || composerText(composer) !== insertedComposerText) {
      return { ok: false, reason: "composer_changed" };
    }
    if (assistantIsGenerating() || !sendButton.isConnected || sendButton.disabled) {
      clearComposer(composer, insertedComposerText);
      return { ok: false, reason: "send_button_not_ready" };
    }

    const previousUserMessages = document.querySelectorAll('[data-message-author-role="user"]').length;
    const normalizedText = (text) => String(text || "").trim().replace(/\s+/g, " ");
    submitComposer(composer, sendButton);
    const deadline = Date.now() + 3000;
    while (Date.now() < deadline) {
      if (normalizeConversationUrl(location.href) !== normalizedUrl) break;
      const userMessages = document.querySelectorAll('[data-message-author-role="user"]');
      const lastUser = userMessages[userMessages.length - 1];
      if (
        userMessages.length > previousUserMessages &&
        normalizedText(lastUser?.innerText || lastUser?.textContent) === normalizedText(prompt)
      ) {
        return { ok: true, reason: "sent" };
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return { ok: false, reason: "delivery_unconfirmed" };
  }

  let controlScanTimer = null;
  let lastSubmittedControlFingerprint = "";
  let lastScannedAssistantSignature = "";
  let controlRetrySignature = "";
  let controlRetryCount = 0;

  async function scanLatestAssistantControl() {
    if (assistantIsGenerating()) return;
    const latest = latestAssistantMessage();
    if (!latest) return;
    const url = normalizeConversationUrl(location.href);
    if (!url) return;
    const signature = fnv1a32(`${url}\n${latest.identity}\n${latest.text}`);
    if (signature === lastScannedAssistantSignature) return;

    const control = parseAssistantControl(latest.text);
    if (!control) {
      lastScannedAssistantSignature = signature;
      return;
    }
    const fingerprint = controlFingerprint(location.href, latest.text, control, latest.identity);
    if (fingerprint === lastSubmittedControlFingerprint) return;
    if (controlRetrySignature !== signature) {
      controlRetrySignature = signature;
      controlRetryCount = 0;
    }
    if (controlRetryCount >= 3) return;
    controlRetryCount += 1;

    try {
      const context = await chrome.runtime.sendMessage({
        type: "bridge:control-context",
        conversationUrl: url
      });
      if (!context?.ok || context.assistantBaseline === latest.identity) return;
      const response = await chrome.runtime.sendMessage({
        type: "bridge:assistant-control",
        conversationUrl: url,
        fingerprint,
        bindingRevision: context.bindingRevision,
        assistantIdentity: latest.identity,
        control
      });
      if (response?.ok) {
        lastSubmittedControlFingerprint = fingerprint;
        lastScannedAssistantSignature = signature;
      } else if (response?.reason === "control_stale_binding") {
        lastScannedAssistantSignature = signature;
      }
    } catch (error) {
      console.warn("Local Agent Chat Bridge control delivery failed:", error);
    }
  }

  function scheduleControlScan() {
    if (controlScanTimer !== null) clearTimeout(controlScanTimer);
    controlScanTimer = setTimeout(() => {
      controlScanTimer = null;
      scanLatestAssistantControl().catch((error) => console.warn(error));
    }, 600);
  }

  const observerTarget = document.body || document.documentElement;
  const observer = observerTarget ? new MutationObserver(scheduleControlScan) : null;
  if (observer && observerTarget) {
    observer.observe(observerTarget, { childList: true, subtree: true, characterData: true });
  }
  scheduleControlScan();
  const controlRetryInterval = setInterval(() => {
    scanLatestAssistantControl().catch((error) => console.warn(error));
  }, 5000);

  const messageListener = (message, _sender, sendResponse) => {
    if (message?.type === "bridge:capabilities") {
      const expectedUrl = normalizeConversationUrl(String(message.expectedUrl || ""));
      const currentUrl = normalizeConversationUrl(location.href);
      const ok = Boolean(expectedUrl && currentUrl === expectedUrl);
      sendResponse({
        ok,
        reason: ok ? "ready" : "wrong_conversation",
        protocolVersion: CONTENT_PROTOCOL_VERSION,
        assistantIdentity: latestAssistantMessage()?.identity || ""
      });
      return false;
    }
    if (message?.type !== "bridge:feedback") return false;
    sendFeedback(String(message.prompt || ""), String(message.expectedUrl || ""), message.deliveryId)
      .then((response) => sendResponse({ ...response, protocolVersion: CONTENT_PROTOCOL_VERSION }))
      .catch((error) => sendResponse({
        ok: false,
        reason: "unexpected_error",
        error: String(error),
        protocolVersion: CONTENT_PROTOCOL_VERSION
      }));
    return true;
  };
  chrome.runtime.onMessage.addListener(messageListener);

  globalThis.__localAgentChatBridgeState = {
    protocolVersion: CONTENT_PROTOCOL_VERSION,
    dispose() {
      try { chrome.runtime.onMessage.removeListener(messageListener); } catch (_error) {}
      try { observer?.disconnect(); } catch (_error) {}
      if (controlScanTimer !== null) clearTimeout(controlScanTimer);
      clearInterval(controlRetryInterval);
    }
  };
})();
