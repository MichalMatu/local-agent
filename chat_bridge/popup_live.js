(function attachPopupLiveState(root, factory) {
  const api = factory();
  root.LocalAgentBridgePopupLive = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createPopupLiveState() {
  "use strict";

  function orderedConversations(state) {
    return Object.values(state?.conversations || {}).sort((a, b) =>
      String(a.label || "").localeCompare(String(b.label || ""))
    );
  }

  function cardMap(root) {
    return new Map(
      Array.from(root.querySelectorAll(".conversation-card[data-conversation-id]"), (card) => [
        card.dataset.conversationId,
        card
      ])
    );
  }

  function patchCard(card, conversation, settings, schedule, runtime, updateNextWakeElement) {
    card.classList.toggle("is-paused", !conversation.enabled);

    const title = card.querySelector(".card-title");
    if (title) {
      title.textContent = conversation.label || conversation.id;
      title.title = conversation.label || conversation.id;
    }

    const repo = card.querySelector(".repo-badge");
    if (repo) repo.textContent = conversation.repositoryId || "UNBOUND";

    const enabled = card.querySelector(".enable-switch input");
    if (enabled) enabled.checked = Boolean(conversation.enabled);

    const status = card.querySelector(".status-text");
    if (status) {
      status.textContent = conversation.lastStatus || "ready";
      status.title = `Last status: ${conversation.lastStatus || "ready"}`;
    }

    const next = card.querySelector(".next-wake");
    if (next) {
      next.dataset.nextRunAt = schedule?.nextRunAt || "";
      next.dataset.masterEnabled = settings?.masterEnabled ? "true" : "false";
      next.dataset.conversationEnabled = conversation.enabled ? "true" : "false";
      updateNextWakeElement(next);
    }

    const intervalInput = card.querySelector(".wake-input-wrap input");
    if (intervalInput) {
      const fallback = runtime?.intervalMinutes || settings?.fallbackIntervalMinutes || 10;
      intervalInput.placeholder = String(fallback);
      intervalInput.title = `Leave empty to use global default (${fallback} min).`;
      if (intervalInput.ownerDocument.activeElement !== intervalInput) {
        intervalInput.value = conversation.intervalOverrideMinutes === null
          ? ""
          : String(conversation.intervalOverrideMinutes);
      }
    }
  }

  function patchConversationCards(root, state, schedules, runtime, updateNextWakeElement) {
    const conversations = orderedConversations(state);
    const cards = cardMap(root);
    if (cards.size !== conversations.length) return false;
    if (conversations.some((conversation) => !cards.has(conversation.id))) return false;

    for (const conversation of conversations) {
      patchCard(
        cards.get(conversation.id),
        conversation,
        state.settings,
        schedules?.[conversation.id] || null,
        runtime,
        updateNextWakeElement
      );
    }
    return true;
  }

  return { patchConversationCards };
});
