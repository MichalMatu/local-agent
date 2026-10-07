async function refreshBridgeContentOnWorkerStart() {
  try {
    return await refreshConfiguredContentScripts();
  } catch (error) {
    console.error(error);
    return null;
  }
}

async function initializeBridgeLifecycle() {
  try {
    await initializeGithubControlPlane();
    await reconcileSchedules();
  } catch (error) {
    console.error(error);
  }
  return refreshBridgeContentOnWorkerStart();
}

chrome.runtime.onInstalled.addListener(() => initializeBridgeLifecycle());
chrome.runtime.onStartup.addListener(() => initializeBridgeLifecycle());

async function handleGithubControlAlarm() {
  await reconcileGithubConversationControls();
  try {
    await refreshConfiguredContentScripts();
  } catch (error) {
    console.error(error);
  }
  return pollConversationFabricCampaigns();
}
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === GITHUB_CONTROL_ALARM_NAME) {
    handleGithubControlAlarm().catch((error) => console.error(error));
    return;
  }
  if (!alarm.name.startsWith(ALARM_PREFIX)) return;
  const chatId = alarm.name.slice(ALARM_PREFIX.length);
  (async () => {
    await reconcileGithubConversationControls();
    return runFeedbackCycle({ conversationId: chatId });
  })().catch(async (error) => {
    console.error(error);
    const state = await getBridgeState();
    const conversation = state.conversations[chatId];
    if (!conversation) return;
    const generation = conversation.generation;
    const runtime = await loadRuntimeConfig(state, conversation);
    await updateConversationStatus(chatId, {
      lastRunAt: new Date().toISOString(),
      lastStatus: `worker_error:${String(error)}`,
      lastRuntimeSource: runtime.source
    }, generation);
    if (state.settings.masterEnabled && conversation.enabled && stateModel.isTransportReady(conversation)) {
      await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes, generation);
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
    "bridge:conversation-fabric-control": applyConversationFabricControl,
    "bridge:conversation-fabric-diagnostic-context": conversationFabricDiagnosticContext,
    "bridge:conversation-fabric-diagnostic": reportConversationFabricDiagnostic,
    "bridge:conversation-fabric-feedback": acknowledgeConversationFabricFeedback,
    "bridge:conversation-exhausted": reportConversationExhausted,
    "bridge:assistant-error": reportAssistantError,
    "bridge:authorize-assistant-retry": authorizeAssistantRetry
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
      await reconcileGithubConversationControls();
      const state = await getBridgeState();
      const [runtime, schedules, fabricStatus, fabricDiagnostics] = await Promise.all([
        loadRuntimeConfig(state),
        getScheduleSnapshot(state),
        conversationFabricOperatorSnapshot(),
        conversationFabricDiagnosticSnapshot()
      ]);
      const [githubOwnership, operatorStatus] = await Promise.all([
        githubOwnershipSnapshot(state, runtime),
        loadOperatorStatus(runtime)
      ]);
      const popupRuntime = {
        ...runtime,
        conversationControls: (runtime.conversationControls || []).filter((control) => {
          const ownership = githubOwnership[control.conversationId];
          return Boolean(
            ownership?.source === "remote" &&
            ownership.controlGeneration === control.controlGeneration &&
            ownership.bindingRevision === control.bindingRevision
          );
        })
      };
      sendResponse({
        state,
        runtime: popupRuntime,
        schedules,
        githubOwnership,
        fabricStatus,
        fabricDiagnostics,
        operatorStatus,
        bridgeInfo: {
          extensionVersion: chrome.runtime.getManifest().version,
          contentProtocolVersion: CONTENT_PROTOCOL_VERSION,
          fabricSchemaVersion: conversationFabricProtocol.SCHEMA_VERSION
        }
      });
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
    (async () => {
      await reconcileGithubConversationControls();
      return runFeedbackCycle({ conversationId: String(message.conversationId || ""), manual: true });
    })().then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  return false;
});

// Every service-worker activation restores the GitHub control plane first, reconciles
// schedules, and only then refreshes configured content scripts. This keeps cold-parent
// recovery and content reinjection ordered instead of racing independent startup paths.
initializeBridgeLifecycle().catch((error) => console.error(error));
