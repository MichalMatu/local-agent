(() => {
  const protocol = globalThis.LocalAgentBridgeProtocol;
  if (!protocol) throw new Error("Local Agent Chat Bridge control protocol is unavailable");
  const retryPolicy = globalThis.LocalAgentBridgeContentRetry;
  if (!retryPolicy) throw new Error("Local Agent Chat Bridge content retry policy is unavailable");
  const {
    CONTENT_PROTOCOL_VERSION,
    normalizeConversationUrl,
    parseAssistantControl,
    parseOperatorControl,
    controlFingerprint,
    fnv1a32
  } = protocol;

  const existingBridge = globalThis.__localAgentChatBridgeState;
  if (existingBridge?.protocolVersion === CONTENT_PROTOCOL_VERSION) return;
  try {
    existingBridge?.dispose?.();
  } catch (_error) {
    // A stale extension context may already be detached; continue with a fresh listener.
  }

  globalThis.__localAgentChatBridgeLoaded = true;
  globalThis.__localAgentChatBridgeProtocolVersion = CONTENT_PROTOCOL_VERSION;

  const controlRetryGate = retryPolicy.createRetryGate();
  const operatorRetryGate = retryPolicy.createRetryGate();

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
    const buttons = document.querySelectorAll(
      'button[data-testid="stop-button"], button[data-testid="composer-stop-button"]'
    );
    return Array.from(buttons).some((button) => button.checkVisibility({
      checkVisibilityCSS: true,
      checkOpacity: true
    }));
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
    // Follow the same DOM path as a real operator click. ChatGPT's React handlers may
    // attach behavior to the live button that is not reproduced by requestSubmit().
    if (sendButton instanceof HTMLButtonElement && sendButton.isConnected && !sendButton.disabled) {
      sendButton.click();
      return;
    }
    const form = composer.closest("form");
    if (form instanceof HTMLFormElement && typeof form.requestSubmit === "function") {
      form.requestSubmit();
      return;
    }
    throw new Error("send control unavailable");
  }

  async function waitForSendButton(composer, timeoutMs = 4500) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (assistantIsGenerating()) return null;
      const button = findSendButton(composer);
      if (button) return button;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return null;
  }

  function latestMessage(role) {
    const messages = document.querySelectorAll(`[data-message-author-role="${role}"]`);
    if (!messages.length) return null;
    const latest = messages[messages.length - 1];
    const text = latest.innerText || latest.textContent || "";
    const stableId = latest.getAttribute("data-message-id") || latest.getAttribute("data-testid") || latest.id || "";
    return { text, identity: stableId || `${role}:${messages.length}:${fnv1a32(text)}` };
  }

  function latestAssistantMessage() {
    return latestMessage("assistant");
  }

  function latestUserMessage() {
    return latestMessage("user");
  }

  function localMessageSignature(url, message) {
    return message && url ? fnv1a32(`${url}\n${message.identity}\n${message.text}`) : "";
  }

  let deliveryInFlight = false;

  async function sendFeedback(
    prompt,
    expectedUrl,
    deliveryId,
    recoverBridgePrompt = false,
    requireAuthorization = true
  ) {
    if (deliveryInFlight) return { ok: false, reason: "delivery_in_progress" };
    deliveryInFlight = true;
    try {
      return await deliverFeedback(
        prompt,
        expectedUrl,
        deliveryId,
        recoverBridgePrompt,
        requireAuthorization
      );
    } finally {
      deliveryInFlight = false;
    }
  }

  async function deliverFeedback(
    prompt,
    expectedUrl,
    deliveryId,
    recoverBridgePrompt,
    requireAuthorization
  ) {
    const normalizedUrl = normalizeConversationUrl(expectedUrl);
    if (!normalizedUrl || normalizeConversationUrl(location.href) !== normalizedUrl) {
      return { ok: false, reason: "wrong_conversation" };
    }
    if (document.visibilityState === "prerender") return { ok: false, reason: "page_not_ready" };
    if (assistantIsGenerating()) return { ok: false, reason: "assistant_busy" };

    const composer = findComposer();
    if (!composer) return { ok: false, reason: "composer_not_found" };
    const existingComposerText = composerText(composer);
    const reuseExactBridgePrompt = Boolean(
      recoverBridgePrompt && existingComposerText && existingComposerText === prompt
    );
    if (existingComposerText.trim() && !reuseExactBridgePrompt) {
      return { ok: false, reason: "composer_not_empty" };
    }

    if (!reuseExactBridgePrompt) {
      try {
        setComposerText(composer, prompt);
      } catch (error) {
        return { ok: false, reason: "composer_write_failed", error: String(error) };
      }
    }
    // Rich contenteditable editors may canonicalize whitespace/newlines while preserving
    // the inserted visible text. From this point protect the exact DOM snapshot we
    // actually produced; any later operator edit changes that snapshot and fails closed.
    const insertedComposerText = composerText(composer);
    if (!insertedComposerText.trim()) {
      return { ok: false, reason: "composer_write_failed" };
    }

    let sendButton = await waitForSendButton(composer);
    if (!sendButton) {
      return { ok: false, reason: "send_button_not_ready" };
    }

    if (requireAuthorization) {
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
    }
    if (normalizeConversationUrl(location.href) !== normalizedUrl) {
      clearComposer(composer, insertedComposerText);
      return { ok: false, reason: "wrong_conversation" };
    }
    if (!composer.isConnected || findComposer() !== composer || composerText(composer) !== insertedComposerText) {
      return { ok: false, reason: "composer_changed" };
    }
    if (assistantIsGenerating()) {
      return { ok: false, reason: "send_button_not_ready" };
    }

    // React may replace the Send button while reconciling composer state. Resolve the
    // live control again immediately before submission instead of trusting a stale node.
    sendButton = findSendButton(composer) || await waitForSendButton(composer, 1200);
    if (!sendButton) {
      return { ok: false, reason: "send_button_not_ready" };
    }

    const previousUserMessages = document.querySelectorAll('[data-message-author-role="user"]').length;
    const normalizedText = (text) => String(text || "").trim().replace(/\s+/g, " ");
    try {
      submitComposer(composer, sendButton);
    } catch (error) {
      return { ok: false, reason: "send_button_not_ready", error: String(error) };
    }
    const deadline = Date.now() + 5000;
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
  let controlScanInFlight = false;
  let lastSubmittedOperatorFingerprint = "";
  let operatorBaselineUrl = normalizeConversationUrl(location.href);
  let lastScannedUserSignature = localMessageSignature(operatorBaselineUrl, latestUserMessage());
  let operatorScanInFlight = false;

  async function scanLatestAssistantControl() {
    if (assistantIsGenerating() || controlScanInFlight) return;
    const latest = latestAssistantMessage();
    if (!latest) return;
    const url = normalizeConversationUrl(location.href);
    if (!url) return;
    const signature = localMessageSignature(url, latest);
    if (signature === lastScannedAssistantSignature) return;

    const control = parseAssistantControl(latest.text);
    if (!control) {
      lastScannedAssistantSignature = signature;
      return;
    }
    const fingerprint = controlFingerprint(location.href, latest.text, control, latest.identity);
    if (fingerprint === lastSubmittedControlFingerprint) return;
    if (!controlRetryGate.canAttempt(signature)) return;

    controlScanInFlight = true;
    try {
      let context = null;
      if (control.action !== "inspect") {
        context = await chrome.runtime.sendMessage({
          type: "bridge:control-context",
          conversationUrl: url
        });
        if (!context?.ok) {
          controlRetryGate.defer(signature);
          return;
        }
        if (context.assistantBaseline === latest.identity) {
          lastScannedAssistantSignature = signature;
          controlRetryGate.reset(signature);
          return;
        }
      }

      const response = await chrome.runtime.sendMessage({
        type: "bridge:assistant-control",
        conversationUrl: url,
        fingerprint,
        bindingRevision: context?.bindingRevision,
        assistantIdentity: latest.identity,
        contentProtocolVersion: CONTENT_PROTOCOL_VERSION,
        control
      });
      if (response?.ok) {
        if (response.feedbackPrompt) {
          const feedback = await sendFeedback(
            String(response.feedbackPrompt),
            url,
            null,
            true,
            false
          );
          if (!feedback.ok) {
            controlRetryGate.defer(signature);
            return;
          }
        }
        lastSubmittedControlFingerprint = fingerprint;
        lastScannedAssistantSignature = signature;
        controlRetryGate.reset(signature);
      } else if (response?.reason === "control_stale_binding") {
        lastScannedAssistantSignature = signature;
        controlRetryGate.reset(signature);
      } else {
        controlRetryGate.defer(signature);
      }
    } catch (error) {
      controlRetryGate.defer(signature);
      console.warn("Local Agent Chat Bridge control delivery failed:", error);
    } finally {
      controlScanInFlight = false;
    }
  }

  const terminalOperatorReasons = new Set([
    "operator_chat_already_bound",
    "operator_chat_not_configured",
    "operator_invalid_marker",
    "operator_invalid_fingerprint",
    "operator_wrong_conversation"
  ]);

  async function scanLatestOperatorControl() {
    if (operatorScanInFlight) return;
    const url = normalizeConversationUrl(location.href);
    if (!url) return;
    const latest = latestUserMessage();
    if (!latest) {
      operatorBaselineUrl = url;
      lastScannedUserSignature = "";
      return;
    }
    const signature = localMessageSignature(url, latest);
    if (url !== operatorBaselineUrl) {
      operatorBaselineUrl = url;
      lastScannedUserSignature = signature;
      lastSubmittedOperatorFingerprint = "";
      operatorRetryGate.reset(signature);
      return;
    }
    if (signature === lastScannedUserSignature) return;

    const control = parseOperatorControl(latest.text);
    if (!control) {
      lastScannedUserSignature = signature;
      return;
    }
    const fingerprint = controlFingerprint(location.href, latest.text, control, latest.identity);
    if (fingerprint === lastSubmittedOperatorFingerprint) return;
    if (!operatorRetryGate.canAttempt(signature)) return;

    operatorScanInFlight = true;
    try {
      const response = await chrome.runtime.sendMessage({
        type: "bridge:operator-control",
        conversationUrl: url,
        fingerprint,
        userIdentity: latest.identity,
        chatLabel: document.title,
        assistantBaseline: latestAssistantMessage()?.identity || "",
        contentProtocolVersion: CONTENT_PROTOCOL_VERSION,
        control
      });
      if (response?.ok || terminalOperatorReasons.has(response?.reason)) {
        lastSubmittedOperatorFingerprint = fingerprint;
        lastScannedUserSignature = signature;
        operatorRetryGate.reset(signature);
      } else {
        operatorRetryGate.defer(signature);
      }
    } catch (error) {
      operatorRetryGate.defer(signature);
      console.warn("Local Agent Chat Bridge operator control failed:", error);
    } finally {
      operatorScanInFlight = false;
    }
  }

  function scheduleControlScan() {
    if (controlScanTimer !== null) clearTimeout(controlScanTimer);
    controlScanTimer = setTimeout(() => {
      controlScanTimer = null;
      scanLatestAssistantControl().catch((error) => console.warn(error));
      scanLatestOperatorControl().catch((error) => console.warn(error));
    }, 600);
  }

  const observerTarget = document.body || document.documentElement;
  const observer = observerTarget ? new MutationObserver(scheduleControlScan) : null;
  if (observer && observerTarget) {
    observer.observe(observerTarget, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["hidden", "style", "class", "data-testid"]
    });
  }
  scheduleControlScan();
  const controlRetryInterval = setInterval(() => {
    scanLatestAssistantControl().catch((error) => console.warn(error));
    scanLatestOperatorControl().catch((error) => console.warn(error));
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
        assistantIdentity: latestAssistantMessage()?.identity || "",
        userIdentity: latestUserMessage()?.identity || ""
      });
      return false;
    }
    if (message?.type !== "bridge:feedback") return false;
    sendFeedback(
      String(message.prompt || ""),
      String(message.expectedUrl || ""),
      message.deliveryId,
      message.recoverBridgePrompt === true,
      true
    )
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
