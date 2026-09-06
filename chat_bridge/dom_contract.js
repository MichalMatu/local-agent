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

  function normalizedText(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
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
        assistantIdentity: String(
          message.getAttribute?.("data-message-id") ||
          message.getAttribute?.("data-testid") ||
          message.id ||
          ""
        )
      };
    }
    return null;
  }

  return Object.freeze({
    CONVERSATION_LIMIT_TEXT,
    START_NEW_CHAT_TEXT,
    normalizedText,
    findConversationExhaustion
  });
});
