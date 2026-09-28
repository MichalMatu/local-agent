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
  const MESSAGE_SELECTORS = Object.freeze({
    assistant: Object.freeze([
      '[data-message-author-role="assistant"]',
      '[data-conversation-role="assistant"]'
    ]),
    user: Object.freeze([
      '[data-message-author-role="user"]',
      '[data-user-message-bubble]'
    ])
  });

  function normalizedText(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }

  function containingTurn(message) {
    return message?.closest?.('[data-turn-key]') || message;
  }

  function dedupeMessagesByTurn(messages) {
    const seenTurns = new Set();
    const result = [];
    for (const message of messages) {
      const turn = containingTurn(message);
      if (seenTurns.has(turn)) continue;
      seenTurns.add(turn);
      result.push(message);
    }
    return result;
  }

  const TURN_SELECTOR = '[data-turn-key]';
  const USER_SELECTOR = MESSAGE_SELECTORS.user.join(", ");

  function groupedAssistantTurns(root) {
    if (!root || typeof root.querySelectorAll !== "function") return [];
    return Array.from(root.querySelectorAll(TURN_SELECTOR)).filter(
      (turn) => Boolean(turn?.querySelector?.(USER_SELECTOR))
    );
  }

  function compareDocumentOrder(left, right) {
    if (left === right) return 0;
    const position = left?.compareDocumentPosition?.(right) || 0;
    if (position & 4) return -1;
    if (position & 2) return 1;
    return 0;
  }

  function mergeAssistantMessages(explicit, grouped) {
    const selected = new Map();
    for (const message of explicit) selected.set(containingTurn(message), message);
    for (const turn of grouped) if (!selected.has(turn)) selected.set(turn, turn);
    return Array.from(selected.values()).sort(compareDocumentOrder);
  }

  function messageElements(root, role) {
    if (!root || typeof root.querySelectorAll !== "function") return [];
    const selectors = MESSAGE_SELECTORS[role] || [];
    if (!selectors.length) return [];
    const explicit = dedupeMessagesByTurn(Array.from(root.querySelectorAll(selectors.join(", "))));
    if (role !== "assistant") return explicit;
    const grouped = groupedAssistantTurns(root);
    return grouped.length ? mergeAssistantMessages(explicit, grouped) : explicit;
  }

  function conversationMessages(root) {
    if (!root || typeof root.querySelectorAll !== "function") return [];
    const explicit = dedupeMessagesByTurn(Array.from(root.querySelectorAll(
      '[data-message-author-role], [data-conversation-role="assistant"], [data-user-message-bubble]'
    )));
    if (explicit.some((message) => messageRole(message) === "assistant")) return explicit;
    const grouped = groupedAssistantTurns(root);
    return grouped.length ? grouped : explicit;
  }

  function messageRole(message) {
    const legacy = String(message?.getAttribute?.("data-message-author-role") || "");
    if (legacy === "assistant" || legacy === "user") return legacy;
    if (message?.getAttribute?.("data-conversation-role") === "assistant") return "assistant";
    if (message?.getAttribute?.("data-user-message-bubble") !== null) return "user";
    return "";
  }

  function assistantIdentity(message) {
    const turnKey =
      message?.getAttribute?.("data-turn-key") ||
      message?.closest?.('[data-turn-key]')?.getAttribute?.("data-turn-key") ||
      "";
    return String(
      message?.getAttribute?.("data-message-id") ||
      message?.getAttribute?.("data-testid") ||
      message?.id ||
      turnKey ||
      ""
    );
  }

  function findConversationExhaustion(root) {
    if (!root || typeof root.querySelectorAll !== "function") return null;
    const messages = messageElements(root, "assistant");
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
    const turns = conversationMessages(root);
    if (!turns.length) return null;
    const message = turns[turns.length - 1];
    const role = messageRole(message);
    const groupedTurnFallback = role === "" &&
      message?.getAttribute?.("data-turn-key") !== null &&
      Boolean(message?.querySelector?.(USER_SELECTOR));
    if (role !== "assistant" && !groupedTurnFallback) return null;

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
    messageElements,
    conversationMessages,
    messageRole,
    assistantIdentity,
    findConversationExhaustion,
    findRecoverableAssistantError
  });
});