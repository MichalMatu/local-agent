const STARTUP_RECONCILE_ALARM_PREFIX = "local-agent-chat-startup-reconcile:";
const STARTUP_RECONCILE_DELAYS_MS = [1000, 3000, 8000];

async function refreshBridgeContentOnWorkerStart() {
  try {
    return await refreshConfiguredContentScripts();
  } catch (error) {
    console.error(error);
    return null;
  }
}

async function scheduleStartupReconciliation() {
  await Promise.all(STARTUP_RECONCILE_DELAYS_MS.map((delayMs, index) =>
    chrome.alarms.create(`${STARTUP_RECONCILE_ALARM_PREFIX}${index}`, {
      when: Date.now() + delayMs
    })
  ));
}

async function reconcileRestoredTabsAfterStartup() {
  const content = await refreshBridgeContentOnWorkerStart();
  const state = await getBridgeState();
  if (!state.settings.masterEnabled) return { content, pendingScheduled: 0 };

  let pendingScheduled = 0;
  for (const conversation of Object.values(state.conversations || {})) {
    if (!conversation.enabled || !stateModel.isBoundConversation(conversation)) continue;
    const pending = await pendingEventWake(conversation.id);
    if (!pending) continue;
    const scheduled = await scheduleAt(
      conversation.id,
      Date.now() + 1000,
      conversation.generation
    );
    if (scheduled) pendingScheduled += 1;
  }
  return { content, pendingScheduled };
}

async function initializeBridgeLifecycle({ startupRecovery = false } = {}) {
  initializeNativeEventTransport();
  try {
    await reconcileSchedules();
  } catch (error) {
    console.error(error);
  }
  const content = await refreshBridgeContentOnWorkerStart();
  if (startupRecovery) {
    try {
      await scheduleStartupReconciliation();
    } catch (error) {
      console.error(error);
    }
  }
  return content;
}

async function reconcilePendingWakeForCompletedTab(tabId, changeInfo, tab) {
  if (!Number.isInteger(tabId) || changeInfo?.status !== "complete") return false;
  const url = normalizeConversationUrl(tab?.url || changeInfo?.url || "");
  if (!url) return false;

  const state = await getBridgeState();
  const conversation = Object.values(state.conversations || {}).find((candidate) => candidate.url === url);
  if (
    !conversation ||
    !state.settings.masterEnabled ||
    !conversation.enabled ||
    !stateModel.isBoundConversation(conversation)
  ) {
    return false;
  }

  const pending = await pendingEventWake(conversation.id);
  if (!pending) return false;
  return scheduleAt(conversation.id, Date.now() + 1000, conversation.generation);
}

chrome.runtime.onInstalled.addListener(() => initializeBridgeLifecycle());
chrome.runtime.onStartup.addListener(() => initializeBridgeLifecycle({ startupRecovery: true }));

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) =>
  reconcilePendingWakeForCompletedTab(tabId, changeInfo, tab).catch(console.error)
);

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name.startsWith(STARTUP_RECONCILE_ALARM_PREFIX)) {
    reconcileRestoredTabsAfterStartup().catch(console.error);
    return;
  }
  if (!alarm.name.startsWith(ALARM_PREFIX)) return;
  const chatId = alarm.name.slice(ALARM_PREFIX.length);
  runFeedbackCycle({ conversationId: chatId }).catch(async (error) => {
    console.error(error);
    const state = await getBridgeState();
    const conversation = state.conversations[chatId];
    if (!conversation) return;
    const runtime = await loadRuntimeConfig(state, conversation);
    await updateConversationStatus(chatId, {
      lastRunAt: new Date().toISOString(),
      lastStatus: `worker_error:${String(error)}`,
      lastRuntimeSource: runtime.source
    });
    if (state.settings.masterEnabled && conversation.enabled && stateModel.isBoundConversation(conversation)) {
      await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes);
    }
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  const contentHandlers = {
    "bridge:authorize-delivery": authorizeDelivery,
    "bridge:control-context": controlContext,
    "bridge:assistant-control": applyAssistantControl,
    "bridge:operator-control": applyOperatorLabControl,
    "bridge:conversation-exhausted": reportConversationExhausted
  };
  if (Object.hasOwn(contentHandlers, message.type)) {
    contentHandlers[message.type](message, sender).then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (sender?.id !== chrome.runtime.id || sender?.url !== chrome.runtime.getURL("popup.html")) {
    sendResponse({ ok: false, reason: "operator_ui_required" });
    return false;
  }

  if (message.type === "bridge:get-state") {
    (async () => {
      const state = await getBridgeState();
      const [runtime, schedules, eventWake] = await Promise.all([
        loadRuntimeConfig(state),
        getScheduleSnapshot(state),
        loadEventWakeState()
      ]);
      sendResponse({ state, runtime, schedules, eventWake });
    })().catch((error) => sendResponse({ error: String(error) }));
    return true;
  }
  if (message.type === "bridge:ensure-tab-content") {
    const tabId = Number(message.tabId);
    const expectedUrl = normalizeConversationUrl(message.expectedUrl || "");
    if (!Number.isInteger(tabId) || !expectedUrl) {
      sendResponse({ ok: false, reason: "invalid_tab_content_request" });
      return false;
    }
    labForceReloadContent(tabId, expectedUrl)
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  if (message.type === "bridge:save-global-settings") {
    saveGlobalSettings(message.settings || {})
      .then((state) => sendResponse({ ok: true, state }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  if (message.type === "bridge:upsert-conversation") {
    upsertConversation(message.conversation || {})
      .then((conversation) => sendResponse({ ok: true, conversation }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  if (message.type === "bridge:rebind-conversation") {
    rebindConversation(String(message.conversationId || ""), message.binding || {})
      .then((conversation) => sendResponse({ ok: true, conversation }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  if (message.type === "bridge:update-conversation") {
    updateConversation(String(message.conversationId || ""), message.patch || {})
      .then((conversation) => sendResponse({ ok: true, conversation }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  if (message.type === "bridge:remove-conversation") {
    deleteConversation(String(message.conversationId || ""))
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  if (message.type === "bridge:run-now") {
    runFeedbackCycle({ conversationId: String(message.conversationId || ""), manual: true })
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  return false;
});

// A manually reloaded unpacked extension starts a fresh service worker while existing
// ChatGPT tabs stay open. Probe configured tabs immediately so stale/unavailable content
// scripts are replaced with this worker's protocol without a page reload or a wake.
// Native transport is also reconnected here so durable local result events can replay.
// Browser startup additionally arms a short bounded sequence of alarm-backed probes because
// session-restored tabs can appear after onStartup and may never emit tabs.onUpdated=complete.
// Do not reconcile ordinary schedules here: service-worker activation itself is transport
// lifecycle, not a scheduling event. Persisted Chrome alarms remain the fallback.
initializeNativeEventTransport();
refreshBridgeContentOnWorkerStart();
