(() => {
  "use strict";

  const bridgeProtocol = globalThis.LocalAgentBridgeProtocol;
  const fabricProtocol = globalThis.LocalAgentConversationFabricProtocol;
  const retryPolicy = globalThis.LocalAgentBridgeContentRetry;
  if (!bridgeProtocol || !fabricProtocol || !retryPolicy) {
    throw new Error("Conversation Fabric content dependencies are unavailable");
  }
  const { CONTENT_PROTOCOL_VERSION, normalizeConversationUrl, controlFingerprint, fnv1a32 } = bridgeProtocol;
  const { parseConversationFabricControl, MAX_PROMPT_CHARS } = fabricProtocol;

  const existing = globalThis.__localAgentConversationFabricContent;
  if (existing?.protocolVersion === CONTENT_PROTOCOL_VERSION) return;
  try { existing?.dispose?.(); } catch (_error) {}

  const retryGate = retryPolicy.createRetryGate();
  let scanTimer = null;
  let scanInFlight = false;
  let lastScannedSignature = "";
  let lastSubmittedFingerprint = "";

  const ASSISTANT_SELECTORS = [
    '[data-message-author-role="assistant"]',
    '[data-conversation-role="assistant"]'
  ];
  const USER_SELECTORS = [
    '[data-message-author-role="user"]',
    '[data-user-message-bubble]'
  ];

  function assistantIsGenerating() {
    const buttons = document.querySelectorAll(
      'button[data-testid="stop-button"], button[data-testid="composer-stop-button"]'
    );
    return Array.from(buttons).some((button) => {
      try {
        return button.checkVisibility({ checkVisibilityCSS: true, checkOpacity: true });
      } catch (_error) {
        return true;
      }
    });
  }

  function childCompletionMarker(fingerprint, childId) {
    const checksum = fnv1a32(`${fingerprint}\n${childId}`);
    return `<<<LOCAL_AGENT_CF_CHILD_COMPLETE:${fingerprint}:${childId}:${checksum}>>>`;
  }

  function decorateDelegateControl(control, fingerprint) {
    if (control?.action !== "delegate") return control;
    const children = control.children.map((child) => {
      const completionMarker = childCompletionMarker(fingerprint, child.id);
      const suffix = [
        "When the bounded task is fully complete, append the exact marker below as the final non-whitespace text of your final answer.",
        "Never emit this marker in progress, commentary, tool-use, or any intermediate response.",
        completionMarker
      ].join("\n");
      const prompt = `${child.prompt.trimEnd()}\n\n${suffix}`;
      if (prompt.length > MAX_PROMPT_CHARS) {
        throw new Error("Conversation Fabric child prompt exceeds the bounded limit after completion guard");
      }
      return { ...child, prompt };
    });
    return { ...control, children };
  }

  function cleanTurnText(turn) {
    const bodies = turn?.querySelectorAll?.('[data-content-search-unit-key$=":assistant"] [data-chatgpt-selection-message-id], [data-chatgpt-search-unit-key$=":assistant"] [data-chatgpt-selection-message-id]');
    const body = bodies?.length ? bodies[bodies.length - 1] : turn;
    const clone = body?.cloneNode?.(true);
    if (!clone || typeof clone.querySelectorAll !== "function") return "";
    clone.querySelectorAll(
      `${USER_SELECTORS.join(",")}, button, [role="button"], form, textarea, .sr-only`
    ).forEach((node) => node.remove?.());
    return String(clone.textContent || "").replace(/^\s*ChatGPT said:\s*/i, "").trim();
  }

  function latestAssistantMessage() {
    const explicit = Array.from(document.querySelectorAll(ASSISTANT_SELECTORS.join(",")));
    if (explicit.length) {
      const message = explicit[explicit.length - 1];
      const turn = message.closest?.('[data-turn-key]') || message;
      const text = cleanTurnText(turn) || String(message.innerText || message.textContent || "").trim();
      const identity = String(
        turn.getAttribute?.("data-turn-key") ||
        message.getAttribute?.("data-message-id") ||
        message.id ||
        ""
      );
      return { text, identity: identity || `assistant:${fnv1a32(text)}` };
    }
    const turns = Array.from(document.querySelectorAll('[data-turn-key]')).reverse();
    for (const turn of turns) {
      const text = cleanTurnText(turn);
      if (!text) continue;
      const identity = String(turn.getAttribute("data-turn-key") || "");
      return { text, identity: identity || `assistant:${fnv1a32(text)}` };
    }
    return null;
  }

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
    return composer?.innerText || composer?.textContent || "";
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

  function findSendButton(composer) {
    const selectors = [
      "#composer-submit-button",
      'button[data-testid="send-button"]',
      'button[data-testid="composer-send-button"]',
      'button[aria-label="Send prompt"]',
      'button[aria-label="Send message"]',
      'button[aria-label="Send"]'
    ];
    const form = composer?.closest?.("form");
    for (const scope of form ? [form, document] : [document]) {
      for (const selector of selectors) {
        const button = scope.querySelector(selector);
        if (button instanceof HTMLButtonElement && !button.disabled) return button;
      }
    }
    return null;
  }

  function latestUserText() {
    const messages = Array.from(document.querySelectorAll(USER_SELECTORS.join(",")));
    const latest = messages[messages.length - 1];
    return String(latest?.innerText || latest?.textContent || "");
  }

  async function deliverFabricFeedback(prompt, expectedUrl) {
    const normalizedUrl = normalizeConversationUrl(expectedUrl);
    const normalized = (value) => String(value || "").trim().replace(/\s+/g, " ");
    if (!normalizedUrl || normalizeConversationUrl(location.href) !== normalizedUrl) {
      return { ok: false, reason: "wrong_conversation" };
    }
    if (normalized(latestUserText()) === normalized(prompt)) {
      return { ok: true, reason: "already_sent" };
    }
    if (document.visibilityState === "prerender") return { ok: false, reason: "page_not_ready" };
    if (assistantIsGenerating()) return { ok: false, reason: "assistant_busy" };
    const composer = findComposer();
    if (!composer) return { ok: false, reason: "composer_not_found" };
    const existingComposerText = composerText(composer);
    const reuseExactPrompt = Boolean(existingComposerText && normalized(existingComposerText) === normalized(prompt));
    if (existingComposerText.trim() && !reuseExactPrompt) {
      return { ok: false, reason: "composer_not_empty" };
    }

    if (!reuseExactPrompt) {
      try {
        setComposerText(composer, prompt);
      } catch (error) {
        return { ok: false, reason: "composer_write_failed", error: String(error) };
      }
    }
    const inserted = composerText(composer);
    if (!inserted.trim()) return { ok: false, reason: "composer_write_failed" };

    const deadline = Date.now() + 4500;
    let button = findSendButton(composer);
    while (!button && Date.now() < deadline) {
      if (assistantIsGenerating()) return { ok: false, reason: "assistant_busy" };
      await new Promise((resolve) => setTimeout(resolve, 100));
      button = findSendButton(composer);
    }
    if (!button) return { ok: false, reason: "send_button_not_ready" };
    if (
      normalizeConversationUrl(location.href) !== normalizedUrl ||
      findComposer() !== composer ||
      composerText(composer) !== inserted
    ) {
      return { ok: false, reason: "composer_changed" };
    }

    const previousUser = latestUserText();
    try {
      button.click();
    } catch (error) {
      return { ok: false, reason: "send_button_not_ready", error: String(error) };
    }
    const confirmDeadline = Date.now() + 5000;
    while (Date.now() < confirmDeadline) {
      const current = latestUserText();
      if (current !== previousUser && normalized(current) === normalized(prompt)) {
        return { ok: true, reason: "sent" };
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return { ok: false, reason: "delivery_unconfirmed" };
  }

  async function scanLatestConversationFabricControl() {
    if (assistantIsGenerating() || scanInFlight) return;
    const latest = latestAssistantMessage();
    if (!latest) return;
    const url = normalizeConversationUrl(location.href);
    if (!url) return;
    const signature = fnv1a32(`${url}\n${latest.identity}\n${latest.text}`);
    if (signature === lastScannedSignature) return;

    const control = parseConversationFabricControl(latest.text);
    if (!control) {
      lastScannedSignature = signature;
      retryGate.reset(signature);
      return;
    }
    const fingerprint = controlFingerprint(location.href, latest.text, control, latest.identity);
    if (fingerprint === lastSubmittedFingerprint) return;
    if (!retryGate.canAttempt(signature)) return;

    let requestControl;
    try {
      requestControl = decorateDelegateControl(control, fingerprint);
    } catch (error) {
      // Prompt length is deterministic for this assistant turn. Retrying cannot
      // make the completion guard fit, so fail closed until a new turn arrives.
      lastScannedSignature = signature;
      retryGate.reset(signature);
      console.warn("Local Agent Conversation Fabric completion guard failed:", error);
      return;
    }

    scanInFlight = true;
    try {
      const response = await chrome.runtime.sendMessage({
        type: "bridge:conversation-fabric-control",
        conversationUrl: url,
        fingerprint,
        assistantIdentity: latest.identity,
        contentProtocolVersion: CONTENT_PROTOCOL_VERSION,
        control: requestControl
      });
      if (!response?.ok) {
        retryGate.defer(signature);
        return;
      }
      if (response.feedbackPrompt) {
        const feedback = await deliverFabricFeedback(String(response.feedbackPrompt), url);
        if (!feedback.ok) {
          retryGate.defer(signature);
          return;
        }
        const receipt = await chrome.runtime.sendMessage({
          type: "bridge:conversation-fabric-feedback",
          conversationUrl: url,
          fingerprint,
          assistantIdentity: latest.identity,
          contentProtocolVersion: CONTENT_PROTOCOL_VERSION,
          control: requestControl,
          campaignId: response.campaignId
        });
        if (!receipt?.ok) {
          retryGate.defer(signature);
          return;
        }
      }
      lastSubmittedFingerprint = fingerprint;
      lastScannedSignature = signature;
      retryGate.reset(signature);
    } catch (error) {
      retryGate.defer(signature);
      console.warn("Local Agent Conversation Fabric control failed:", error);
    } finally {
      scanInFlight = false;
    }
  }

  function scheduleScan() {
    if (scanTimer !== null) clearTimeout(scanTimer);
    scanTimer = setTimeout(() => {
      scanTimer = null;
      scanLatestConversationFabricControl().catch((error) => console.warn(error));
    }, 600);
  }

  const observerTarget = document.body || document.documentElement;
  const observer = observerTarget ? new MutationObserver(scheduleScan) : null;
  if (observer && observerTarget) {
    observer.observe(observerTarget, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["hidden", "style", "class", "data-testid"]
    });
  }
  scheduleScan();
  const retryInterval = setInterval(() => {
    scanLatestConversationFabricControl().catch((error) => console.warn(error));
  }, 5000);

  globalThis.__localAgentConversationFabricContent = {
    protocolVersion: CONTENT_PROTOCOL_VERSION,
    dispose() {
      try { observer?.disconnect(); } catch (_error) {}
      if (scanTimer !== null) clearTimeout(scanTimer);
      clearInterval(retryInterval);
    }
  };
})();
