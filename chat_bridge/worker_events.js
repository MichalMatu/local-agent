chrome.runtime.onInstalled.addListener(() => {
  reconcileSchedules().catch((error) => console.error(error));
});
chrome.runtime.onStartup.addListener(() => {
  reconcileSchedules().catch((error) => console.error(error));
});

chrome.alarms.onAlarm.addListener((alarm) => {
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
    "bridge:assistant-control": applyAssistantControl
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
      const [runtime, schedules] = await Promise.all([
        loadRuntimeConfig(state),
        getScheduleSnapshot(state)
      ]);
      sendResponse({ state, runtime, schedules });
    })().catch((error) => sendResponse({ error: String(error) }));
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
