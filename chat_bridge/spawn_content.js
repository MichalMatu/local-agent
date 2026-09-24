(() => {
  "use strict";

  const protocol = globalThis.LocalAgentBridgeProtocol;
  if (!protocol) throw new Error("Local Agent Chat Bridge protocol is unavailable");
  const { normalizeConversationUrl } = protocol;
  const SPAWN_PROTOCOL_VERSION = 1;
  const MAX_BOOTSTRAP_CHARS = 32_768;
  const TRANSACTION_RE = /^spawn-[0-9a-f]{64}$/;
  const DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
  const CLAIM_PREFIX = "local-agent:conversation-spawn:";

  const existing = globalThis.__localAgentConversationSpawnContent;
  if (existing?.protocolVersion === SPAWN_PROTOCOL_VERSION) return;
  try { existing?.dispose?.(); } catch (_error) {}

  function routeState() {
    try {
      const url = new URL(location.href);
      if (url.protocol !== "https:" || !["chatgpt.com", "chat.openai.com"].includes(url.hostname)) {
        return { kind: "unexpected" };
      }
      const childConversationUrl = normalizeConversationUrl(url.href);
      if (childConversationUrl) return { kind: "child", childConversationUrl };
      const path = url.pathname.replace(/\/+$/, "") || "/";
      return path === "/" ? { kind: "fresh" } : { kind: "unexpected" };
    } catch (_error) {
      return { kind: "unexpected" };
    }
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

  function clearComposer(composer, insertedText) {
    if (!composer?.isConnected || composerText(composer) !== insertedText) return;
    try { setComposerText(composer, ""); } catch (_error) {}
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

  function findSendButton(composer) {
    const selectors = [
      "#composer-submit-button",
      'button[data-testid="send-button"]',
      'button[data-testid="composer-submit-button"]',
      'button[aria-label="Send prompt"]',
      'button[aria-label="Send message"]',
      'button[aria-label="Send"]'
    ];
    const form = composer?.closest("form");
    for (const scope of form ? [form, document] : [document]) {
      for (const selector of selectors) {
        const button = scope.querySelector(selector);
        if (button instanceof HTMLButtonElement && !button.disabled) return button;
      }
    }
    return null;
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

  function latestExactUserMessage(prompt) {
    const normalized = (text) => String(text || "").trim().replace(/\s+/g, " ");
    const messages = document.querySelectorAll('[data-message-author-role="user"]');
    const latest = messages[messages.length - 1];
    if (!latest) return false;
    return normalized(latest.innerText || latest.textContent) === normalized(prompt);
  }

  async function sha256(text) {
    const bytes = new TextEncoder().encode(String(text));
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
  }

  async function validateSpawnMessage(message) {
    const transactionId = String(message.transactionId || "");
    const childRequestDigest = String(message.childRequestDigest || "");
    const bootstrapDigest = String(message.bootstrapDigest || "");
    const bootstrapText = String(message.bootstrapText || "");
    if (!TRANSACTION_RE.test(transactionId)) throw new Error("invalid spawn transaction id");
    if (!DIGEST_RE.test(childRequestDigest)) throw new Error("invalid spawn child request digest");
    if (!DIGEST_RE.test(bootstrapDigest)) throw new Error("invalid spawn bootstrap digest");
    if (!bootstrapText.trim() || bootstrapText.length > MAX_BOOTSTRAP_CHARS) {
      throw new Error("invalid spawn bootstrap text");
    }
    const actual = `sha256:${await sha256(bootstrapText)}`;
    if (actual !== bootstrapDigest) throw new Error("spawn bootstrap digest mismatch");
    return { transactionId, childRequestDigest, bootstrapDigest, bootstrapText };
  }

  function claimKey(transactionId) {
    return `${CLAIM_PREFIX}${transactionId}`;
  }

  function readClaim(transactionId) {
    try {
      const raw = sessionStorage.getItem(claimKey(transactionId));
      if (!raw) return null;
      const claim = JSON.parse(raw);
      return claim && typeof claim === "object" ? claim : null;
    } catch (_error) {
      return null;
    }
  }

  function writeClaim(validated, state) {
    const claim = {
      transactionId: validated.transactionId,
      childRequestDigest: validated.childRequestDigest,
      bootstrapDigest: validated.bootstrapDigest,
      state
    };
    sessionStorage.setItem(claimKey(validated.transactionId), JSON.stringify(claim));
    return claim;
  }

  function clearClaim(transactionId) {
    try { sessionStorage.removeItem(claimKey(transactionId)); } catch (_error) {}
  }

  function claimMatches(claim, validated) {
    return Boolean(
      claim &&
      claim.transactionId === validated.transactionId &&
      claim.childRequestDigest === validated.childRequestDigest &&
      claim.bootstrapDigest === validated.bootstrapDigest
    );
  }

  function reconcileValidatedSpawn(validated) {
    const claim = readClaim(validated.transactionId);
    if (!claim) return { ok: false, reason: "spawn_claim_missing" };
    if (!claimMatches(claim, validated)) {
      return { ok: false, reason: "spawn_claim_conflict" };
    }
    const route = routeState();
    if (route.kind === "child" && latestExactUserMessage(validated.bootstrapText)) {
      return {
        ok: true,
        reason: "identity_discovered",
        childConversationUrl: route.childConversationUrl
      };
    }
    return {
      ok: false,
      reason: "spawn_submission_ambiguous",
      route: route.kind,
      exactUserMessage: latestExactUserMessage(validated.bootstrapText)
    };
  }

  async function submitSpawnBootstrap(message) {
    let validated;
    try {
      validated = await validateSpawnMessage(message);
    } catch (error) {
      return { ok: false, reason: "spawn_intent_invalid", error: String(error) };
    }

    const existingClaim = readClaim(validated.transactionId);
    if (existingClaim) return reconcileValidatedSpawn(validated);
    if (routeState().kind !== "fresh") {
      return { ok: false, reason: "spawn_unexpected_route" };
    }
    if (document.visibilityState === "prerender") {
      return { ok: false, reason: "spawn_page_not_ready" };
    }
    if (assistantIsGenerating()) {
      return { ok: false, reason: "spawn_assistant_busy" };
    }

    const composer = findComposer();
    if (!composer) return { ok: false, reason: "spawn_composer_not_found" };
    if (composerText(composer).trim()) {
      return { ok: false, reason: "spawn_composer_not_empty" };
    }

    try {
      setComposerText(composer, validated.bootstrapText);
    } catch (error) {
      return { ok: false, reason: "spawn_composer_write_failed", error: String(error) };
    }
    const insertedText = composerText(composer);
    if (!insertedText.trim()) {
      return { ok: false, reason: "spawn_composer_write_failed" };
    }

    let button = await waitForSendButton(composer);
    if (!button) {
      clearComposer(composer, insertedText);
      return { ok: false, reason: "spawn_send_button_not_ready" };
    }
    if (
      routeState().kind !== "fresh" ||
      !composer.isConnected ||
      findComposer() !== composer ||
      composerText(composer) !== insertedText
    ) {
      return { ok: false, reason: "spawn_composer_changed" };
    }
    button = findSendButton(composer) || await waitForSendButton(composer, 1200);
    if (!button) {
      clearComposer(composer, insertedText);
      return { ok: false, reason: "spawn_send_button_not_ready" };
    }

    try {
      writeClaim(validated, "submitting");
    } catch (error) {
      clearComposer(composer, insertedText);
      return { ok: false, reason: "spawn_claim_write_failed", error: String(error) };
    }

    try {
      button.click();
      writeClaim(validated, "submitted");
    } catch (error) {
      return {
        ok: false,
        reason: "spawn_submission_ambiguous",
        error: String(error)
      };
    }

    const deadline = Date.now() + 5000;
    while (Date.now() < deadline) {
      const route = routeState();
      if (route.kind === "child" && latestExactUserMessage(validated.bootstrapText)) {
        return {
          ok: true,
          reason: "identity_discovered",
          childConversationUrl: route.childConversationUrl
        };
      }
      if (route.kind === "unexpected") {
        return {
          ok: false,
          reason: "spawn_submission_ambiguous",
          route: "unexpected"
        };
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return reconcileValidatedSpawn(validated);
  }

  async function reconcileSpawn(message) {
    let validated;
    try {
      validated = await validateSpawnMessage(message);
    } catch (error) {
      return { ok: false, reason: "spawn_intent_invalid", error: String(error) };
    }
    return reconcileValidatedSpawn(validated);
  }

  const listener = (message, _sender, sendResponse) => {
    if (message?.type === "bridge:spawn-capabilities") {
      sendResponse({
        ok: true,
        reason: "ready",
        protocolVersion: SPAWN_PROTOCOL_VERSION,
        route: routeState().kind
      });
      return false;
    }
    if (message?.type === "bridge:spawn-bootstrap") {
      submitSpawnBootstrap(message)
        .then((response) => sendResponse({ ...response, protocolVersion: SPAWN_PROTOCOL_VERSION }))
        .catch((error) => sendResponse({
          ok: false,
          reason: "spawn_unexpected_error",
          error: String(error),
          protocolVersion: SPAWN_PROTOCOL_VERSION
        }));
      return true;
    }
    if (message?.type === "bridge:spawn-reconcile") {
      reconcileSpawn(message)
        .then((response) => sendResponse({ ...response, protocolVersion: SPAWN_PROTOCOL_VERSION }))
        .catch((error) => sendResponse({
          ok: false,
          reason: "spawn_unexpected_error",
          error: String(error),
          protocolVersion: SPAWN_PROTOCOL_VERSION
        }));
      return true;
    }
    return false;
  };

  chrome.runtime.onMessage.addListener(listener);
  globalThis.__localAgentConversationSpawnContent = {
    protocolVersion: SPAWN_PROTOCOL_VERSION,
    dispose() {
      try { chrome.runtime.onMessage.removeListener(listener); } catch (_error) {}
    }
  };
})();
