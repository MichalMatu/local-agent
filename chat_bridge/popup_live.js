(function attachPopupLiveState(root, factory) {
  const api = factory();
  root.LocalAgentBridgePopupLive = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;

  if (typeof document !== "undefined" && typeof chrome !== "undefined") {
    const controller = api.createController({
      elements,
      request,
      renderConversations,
      refreshCurrentTabForm,
      restartCountdownTimer,
      updateNextWakeElement,
      setLatestState: (value) => { latestState = value; },
      setLatestRuntime: (value) => { latestRuntime = value; },
      document,
      storageOnChanged: chrome.storage.onChanged,
      addPageHideListener: (listener) => addEventListener("pagehide", listener, { once: true })
    });
    root.LocalAgentBridgePopupLiveController = controller;
    controller.start();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function createPopupLiveStateApi() {
  "use strict";

  const LIVE_SYNC_MS = 500;

  function orderedConversations(state) {
    return Object.values(state?.conversations || {}).sort((a, b) =>
      String(a.label || "").localeCompare(String(b.label || ""))
    );
  }

  function createController(deps) {
    const {
      elements,
      request,
      renderConversations,
      refreshCurrentTabForm,
      restartCountdownTimer,
      updateNextWakeElement,
      setLatestState,
      setLatestRuntime,
      document,
      storageOnChanged,
      addPageHideListener = () => {},
      setIntervalFn = setInterval,
      clearIntervalFn = clearInterval,
      logger = console
    } = deps;

    let syncPromise = null;
    let timer = null;

    function conversationCards(conversations) {
      const cards = Array.from(elements.conversationList.querySelectorAll(".conversation-card"));
      if (cards.length !== conversations.length) return null;

      const identified = cards.every((card) => card.dataset.conversationId);
      if (identified) {
        const byId = new Map(cards.map((card) => [card.dataset.conversationId, card]));
        if (conversations.every((conversation) => byId.has(conversation.id))) return byId;
        return null;
      }

      const byId = new Map();
      conversations.forEach((conversation, index) => {
        cards[index].dataset.conversationId = conversation.id;
        byId.set(conversation.id, cards[index]);
      });
      return byId;
    }

    function patchCard(card, conversation, settings, schedule, runtime) {
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
        if (document.activeElement !== intervalInput) {
          intervalInput.value = conversation.intervalOverrideMinutes === null
            ? ""
            : String(conversation.intervalOverrideMinutes);
        }
      }
    }

    async function syncNow() {
      if (syncPromise) return syncPromise;
      syncPromise = (async () => {
        const response = await request({ type: "bridge:get-state" });
        if (!response?.state) return;

        const state = response.state;
        const runtime = response.runtime || null;
        const schedules = response.schedules || {};
        const conversations = orderedConversations(state);
        let cards = conversationCards(conversations);

        setLatestState(state);
        setLatestRuntime(runtime);
        elements.masterEnabled.checked = Boolean(state.settings.masterEnabled);
        elements.runtimeSource.textContent = runtime?.source || "-";
        elements.runtimeInterval.textContent = runtime?.intervalMinutes ? `${runtime.intervalMinutes} min` : "-";
        elements.conversationCount.textContent = String(conversations.length);

        if (!cards) {
          renderConversations(state, schedules, runtime);
          cards = conversationCards(conversations);
          await refreshCurrentTabForm(state, runtime);
          restartCountdownTimer();
        }

        if (!cards) return;
        for (const conversation of conversations) {
          patchCard(
            cards.get(conversation.id),
            conversation,
            state.settings,
            schedules[conversation.id] || null,
            runtime
          );
        }
      })().catch((error) => {
        logger.warn("Local Agent Chat Bridge live popup sync failed:", error);
      }).finally(() => {
        syncPromise = null;
      });
      return syncPromise;
    }

    function stop() {
      if (timer !== null) clearIntervalFn(timer);
      timer = null;
    }

    function start() {
      if (timer === null) timer = setIntervalFn(syncNow, LIVE_SYNC_MS);
      if (storageOnChanged?.addListener) {
        storageOnChanged.addListener((changes, areaName) => {
          if (areaName === "local" && changes.bridgeState) syncNow();
        });
      }
      addPageHideListener(stop);
      syncNow();
    }

    return { start, stop, syncNow };
  }

  return { LIVE_SYNC_MS, createController };
});
