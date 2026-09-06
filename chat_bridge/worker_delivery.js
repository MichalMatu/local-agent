async function runFeedbackCycle({ conversationId: chatId, manual = false } = {}) {
  if (inFlightDeliveries.has(chatId)) return { ok: false, reason: "delivery_in_progress" };
  inFlightDeliveries.add(chatId);
  try {
    return await deliverConversation(chatId, manual);
  } finally {
    inFlightDeliveries.delete(chatId);
    activeDeliveries.delete(chatId);
  }
}

async function deliverConversation(chatId, manual) {
  const state = await getBridgeState();
  const conversation = state.conversations[chatId];
  if (!conversation) return { ok: false, reason: "conversation_not_found" };
  if (!stateModel.isBoundConversation(conversation)) {
    await updateConversationStatus(chatId, {
      enabled: false,
      lastStatus: "binding_required",
      nextRunAt: null
    });
    await clearConversationAlarm(chatId);
    return { ok: false, reason: "conversation_unbound" };
  }
  if ((!state.settings.masterEnabled || !conversation.enabled) && !manual) {
    await clearConversationAlarm(chatId);
    return { ok: false, reason: "disabled" };
  }

  const runtime = await loadRuntimeConfig(state, conversation);
  if (runtime.source === "unavailable") {
    await updateConversationStatus(chatId, {
      lastStatus: "runtime_unavailable",
      lastRuntimeSource: runtime.source
    });
    if (!manual) await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes, conversation.generation);
    return { ok: false, reason: "runtime_unavailable", runtime };
  }
  const runtimeAgent = runtimeAgentForConversation(runtime, conversation);
  if (!runtimeAgent) {
    await updateConversationStatus(chatId, {
      enabled: false,
      lastStatus: "binding_catalog_mismatch",
      nextRunAt: null
    });
    await clearConversationAlarm(chatId);
    return { ok: false, reason: "binding_catalog_mismatch", runtime };
  }

  const runAt = new Date().toISOString();
  const tab = await findConversationTab(conversation);
  if (!tab?.id) {
    await updateConversationStatus(chatId, {
      lastRunAt: runAt,
      lastStatus: "conversation_tab_missing",
      lastRuntimeSource: runtime.source
    });
    if (!manual) await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes, conversation.generation);
    return { ok: false, reason: "conversation_tab_missing", runtime };
  }
  if (conversation.preferredTabId !== tab.id) {
    await updateConversationStatus(chatId, { preferredTabId: tab.id });
  }

  const contentReady = await ensureContentScript(tab, conversation.url);
  if (!contentReady.ok) {
    const status = String(contentReady.reason || "content_script_unavailable");
    await updateConversationStatus(chatId, {
      lastRunAt: runAt,
      lastStatus: status,
      lastRuntimeSource: runtime.source
    });
    if (!manual) {
      await scheduleAfterMinutes(
        chatId,
        RETRY_REASONS.has(status) ? runtime.busyRetryMinutes : runtime.intervalMinutes,
        conversation.generation
      );
    }
    return {
      ...contentReady,
      runtime,
      status,
      conversationId: chatId,
      agentBinding: conversation.agentBinding,
      repositoryId: conversation.repositoryId,
      repository: conversation.repository,
      bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
    };
  }

  const prompt = conversation.bootstrapPending
    ? buildBootstrapPrompt(runtime, conversation)
    : buildWakePrompt(runtime, conversation);
  const deliveryId = crypto.randomUUID();
  const active = {
    id: deliveryId,
    tabId: tab.id,
    generation: conversation.generation,
    bindingRevision: conversation.bindingRevision,
    manual,
    assistantBaseline: ""
  };
  activeDeliveries.set(chatId, active);

  let response;
  let deliveryTimeout;
  try {
    response = await Promise.race([
      chrome.tabs.sendMessage(tab.id, {
        type: "bridge:feedback",
        prompt,
        expectedUrl: conversation.url,
        deliveryId,
        bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake",
        agentBinding: conversation.agentBinding,
        repositoryId: conversation.repositoryId,
        repository: conversation.repository
      }, { frameId: 0 }),
      new Promise((resolve) => {
        deliveryTimeout = setTimeout(
          () => resolve({ ok: false, reason: "delivery_unconfirmed", protocolVersion: CONTENT_PROTOCOL_VERSION }),
          DELIVERY_TIMEOUT_MS
        );
      })
    ]);
  } catch (error) {
    response = definitelyNoContentReceiver(error)
      ? { ok: false, reason: "content_script_unavailable", protocolVersion: CONTENT_PROTOCOL_VERSION, error: String(error) }
      : { ok: false, reason: "delivery_unconfirmed", protocolVersion: CONTENT_PROTOCOL_VERSION, error: String(error) };
  } finally {
    clearTimeout(deliveryTimeout);
    if (activeDeliveries.get(chatId)?.id === deliveryId) activeDeliveries.delete(chatId);
  }

  if (response?.protocolVersion !== CONTENT_PROTOCOL_VERSION) {
    response = { ok: false, reason: "content_script_protocol_mismatch", protocolVersion: response?.protocolVersion };
  }
  const status = response?.ok ? "sent" : String(response?.reason || "delivery_unconfirmed");
  await mutateState((current) => {
    const latest = current.conversations[chatId];
    if (!latest || latest.bindingRevision !== conversation.bindingRevision) return current;
    if (response?.ok) {
      latest.bootstrapPending = false;
      latest.assistantBaseline = active.assistantBaseline || latest.assistantBaseline || "";
    }
    if (latest.generation === conversation.generation) {
      latest.lastRunAt = runAt;
      latest.lastStatus = status;
      latest.lastRuntimeSource = runtime.source;
    }
    return current;
  });

  if (!manual) {
    const delay = response?.ok
      ? runtime.intervalMinutes
      : status === "delivery_unconfirmed"
        ? runtime.intervalMinutes
        : RETRY_REASONS.has(status)
          ? runtime.busyRetryMinutes
          : runtime.intervalMinutes;
    await scheduleAfterMinutes(chatId, delay, conversation.generation);
  }

  return {
    ...response,
    runtime,
    status,
    conversationId: chatId,
    agentBinding: conversation.agentBinding,
    repositoryId: conversation.repositoryId,
    repository: conversation.repository,
    bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
  };
}

