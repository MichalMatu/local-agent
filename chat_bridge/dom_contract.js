(function initLocalAgentChatDomContract(root, factory) {
  const api = factory();
  root.LocalAgentChatDomContract = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function createDomContract() {
  "use strict";

  const CONVERSATION_LIMIT_TEXT = "You've reached the maximum length for this conversation";
  const START_NEW_CHAT_TEXT = "Start new chat";
  const MESSAGE_DELIVERY_TIMEOUT_TEXT = "Message delivery timed out. Please try again.";
  const RETRY_BUTTON_TEXT = "Retry";
  const RETRY_BUTTON_TEST_ID = "regenerate-thread-error-button";
  const CONNECTION_INTERRUPTED_TEXT = "Connection interrupted. Waiting for the complete answer";
  const EXTENDED_THINKING_TEXT = "Our systems are thinking a bit more about this request before responding.";

  function normalizedText(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }

  function assistantIdentity(message) {
    return String(
      message?.getAttribute?.("data-message-id") ||
      message?.getAttribute?.("data-turn-id") ||
      message?.getAttribute?.("data-testid") ||
      message?.id ||
      ""
    );
  }

  function latestTurn(root, role) {
    if (!root || typeof root.querySelectorAll !== "function") return null;
    const modern = Array.from(root.querySelectorAll(`[data-turn="${role}"]`));
    if (modern.length) return modern[modern.length - 1];
    const legacy = Array.from(root.querySelectorAll(`[data-message-author-role="${role}"]`));
    return legacy.length ? legacy[legacy.length - 1] : null;
  }

  function createProgressStallTracker(stallMs = 180000) {
    const thresholdMs = Math.max(1000, Number(stallMs) || 180000);
    let signature = "";
    let since = 0;

    function reset() {
      signature = "";
      since = 0;
    }

    function observe(currentSignature, { generating = false, blocked = false, now = Date.now() } = {}) {
      const current = String(currentSignature || "");
      const timestamp = Number(now);
      if (!generating || blocked || !current || !Number.isFinite(timestamp)) {
        reset();
        return false;
      }
      if (current !== signature) {
        signature = current;
        since = timestamp;
        return false;
      }
      return since > 0 && timestamp - since >= thresholdMs;
    }

    return Object.freeze({ observe, reset });
  }

  function findAssistantTransientState(root) {
    const message = latestTurn(root, "assistant");
    if (!message) return null;

    const interrupted = message.querySelector?.(".mask-shimmer-muted");
    const interruptedText = normalizedText(interrupted?.innerText || interrupted?.textContent);
    if (interrupted && interruptedText.includes(CONNECTION_INTERRUPTED_TEXT)) {
      return {
        kind: "connection_interrupted",
        message,
        status: interrupted,
        statusText: interruptedText,
        assistantIdentity: assistantIdentity(message)
      };
    }

    const streaming = message.querySelector?.("[data-streaming-response-status]");
    const streamingText = normalizedText(streaming?.innerText || streaming?.textContent);
    if (streaming && streamingText.includes(EXTENDED_THINKING_TEXT)) {
      return {
        kind: "extended_thinking",
        message,
        status: streaming,
        statusText: streamingText,
        assistantIdentity: assistantIdentity(message)
      };
    }

    return null;
  }

  function findConversationExhaustion(root) {
    if (!root || typeof root.querySelectorAll !== "function") return null;
    const messages = Array.from(root.querySelectorAll('[data-message-author-role="assistant"]'));
    for (let index = messages.length - 1; index >= 0; index -= 1) {
      const message = messages[index];
      const error = message?.querySelector?.(".text-token-text-error");
      if (!error) continue;
      const errorText = normalizedText(error.innerText || error.textContent);
      if (!errorText.includes(CONVERSATION_LIMIT_TEXT)) continue;
      const buttons = Array.from(error.querySelectorAll?.("button") || []);
      const button = buttons.find(
        (candidate) => normalizedText(candidate.innerText || candidate.textContent) === START_NEW_CHAT_TEXT
      );
      if (!button) continue;
      return {
        message,
        error,
        button,
        assistantIdentity: assistantIdentity(message)
      };
    }
    return null;
  }

  function findRecoverableAssistantError(root) {
    if (!root || typeof root.querySelectorAll !== "function") return null;
    const turns = Array.from(root.querySelectorAll("[data-message-author-role]"));
    if (!turns.length) return null;
    const message = turns[turns.length - 1];
    if (message?.getAttribute?.("data-message-author-role") !== "assistant") return null;

    const error = message?.querySelector?.(".text-token-text-error");
    if (!error) return null;
    const errorText = normalizedText(error.innerText || error.textContent);
    if (!errorText.includes(MESSAGE_DELIVERY_TIMEOUT_TEXT)) return null;
    const button =
      error.querySelector?.(`button[data-testid="${RETRY_BUTTON_TEST_ID}"]`) ||
      Array.from(error.querySelectorAll?.("button") || []).find(
        (candidate) => normalizedText(candidate.innerText || candidate.textContent) === RETRY_BUTTON_TEXT
      );
    if (!button) return null;
    return {
      kind: "message_delivery_timeout",
      message,
      error,
      button,
      errorText,
      assistantIdentity: assistantIdentity(message)
    };
  }

  return Object.freeze({
    CONVERSATION_LIMIT_TEXT,
    START_NEW_CHAT_TEXT,
    MESSAGE_DELIVERY_TIMEOUT_TEXT,
    RETRY_BUTTON_TEXT,
    RETRY_BUTTON_TEST_ID,
    CONNECTION_INTERRUPTED_TEXT,
    EXTENDED_THINKING_TEXT,
    normalizedText,
    latestTurn,
    createProgressStallTracker,
    findAssistantTransientState,
    findConversationExhaustion,
    findRecoverableAssistantError
  });
});