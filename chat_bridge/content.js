if (!globalThis.__localAgentChatBridgeLoaded) {
  globalThis.__localAgentChatBridgeLoaded = true;

  const protocol = globalThis.LocalAgentBridgeProtocol;
  if (!protocol) {
    throw new Error("Local Agent Chat Bridge control protocol is unavailable");
  }
  const {
    normalizeConversationUrl,
    parseAssistantControl,
    controlFingerprint,
    fnv1a32
  } = protocol;

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
      const setter = Object.getOwnPropertyDescriptor(
        HTMLTextAreaElement.prototype,
        "value"
      )?.set;
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
      composer.dispatchEvent(
        new InputEvent("input", {
          bubbles: true,
          inputType: "insertText",
          data: text
        })
      );
    }
  }

  function clearComposer(composer) {
    try {
      setComposerText(composer, "");
    } catch (_error) {
      // The composer was empty before bridge insertion, so best-effort cleanup is safe.
    }
  }

  function findSendButton(composer) {
    const selectors = [
      'button[data-testid="send-button"]',
      'button[data-testid="composer-submit-button"]',
      'button[type="submit"]'
    ];
    const form = composer.closest("form") || document;
    for (const selector of selectors) {
      const button = form.querySelector(selector) || document.querySelector(selector);
      if (button instanceof HTMLButtonElement && !button.disabled) return button;
    }
    return null;
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

  async function sendFeedback(prompt, expectedUrl) {
    if (normalizeConversationUrl(location.href) !== normalizeConversationUrl(expectedUrl)) {
      return { ok: false, reason: "wrong_conversation" };
    }
    if (document.visibilityState === "prerender") {
      return { ok: false, reason: "page_not_ready" };
    }
    if (assistantIsGenerating()) {
      return { ok: false, reason: "assistant_busy" };
    }

    const composer = findComposer();
    if (!composer) return { ok: false, reason: "composer_not_found" };
    if (composerText(composer).trim()) {
      return { ok: false, reason: "composer_not_empty" };
    }

    try {
      setComposerText(composer, prompt);
    } catch (error) {
      return { ok: false, reason: "composer_write_failed", error: String(error) };
    }

    const sendButton = await waitForSendButton(composer);
    if (!sendButton) {
      clearComposer(composer);
      return { ok: false, reason: "send_button_not_ready" };
    }

    sendButton.click();
    return { ok: true, reason: "sent" };
  }

  function latestAssistantMessage() {
    const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
    if (!messages.length) return null;
    const latest = messages[messages.length - 1];
    const text = latest.innerText || latest.textContent || "";
    const stableId =
      latest.getAttribute("data-message-id") || latest.getAttribute("data-testid") || latest.id || "";
    return {
      text,
      identity: `${messages.length}:${stableId}`
    };
  }

  let controlScanTimer = null;
  let lastSubmittedControlFingerprint = "";
  let lastScannedAssistantSignature = "";

  async function scanLatestAssistantControl() {
    if (assistantIsGenerating()) return;
    const latest = latestAssistantMessage();
    if (!latest) return;

    const signature = fnv1a32(`${latest.identity}\n${latest.text}`);
    if (signature === lastScannedAssistantSignature) return;
    lastScannedAssistantSignature = signature;

    const control = parseAssistantControl(latest.text);
    if (!control) return;

    const fingerprint = controlFingerprint(
      location.href,
      latest.text,
      control,
      latest.identity
    );
    if (fingerprint === lastSubmittedControlFingerprint) return;

    try {
      const response = await chrome.runtime.sendMessage({
        type: "bridge:assistant-control",
        conversationUrl: normalizeConversationUrl(location.href),
        fingerprint,
        control
      });
      if (response?.ok) lastSubmittedControlFingerprint = fingerprint;
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
  if (observerTarget) {
    const observer = new MutationObserver(scheduleControlScan);
    observer.observe(observerTarget, {
      childList: true,
      subtree: true,
      characterData: true
    });
  }
  scheduleControlScan();

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message?.type !== "bridge:feedback") return false;
    sendFeedback(String(message.prompt || ""), String(message.expectedUrl || ""))
      .then(sendResponse)
      .catch((error) =>
        sendResponse({ ok: false, reason: "unexpected_error", error: String(error) })
      );
    return true;
  });
}
