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

  function normalizedText(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }

  function assistantIdentity(message) {
    return String(
      message?.getAttribute?.("data-message-id") ||
      message?.getAttribute?.("data-testid") ||
      message?.id ||
      ""
    );
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
    normalizedText,
    findConversationExhaustion,
    findRecoverableAssistantError
  });
});