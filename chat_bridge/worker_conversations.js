async function saveGlobalSettings(patch) {
  runtimeCache = null;
  const result = await mutateState((state) => {
    state.settings = stateModel.sanitizeSettings({ ...state.settings, ...patch });
    for (const conversation of Object.values(state.conversations)) conversation.generation += 1;
    return state;
  });
  await reconcileSchedules();
  return result.state;
}

async function upsertConversation(patch) {
  const currentState = await getBridgeState();
  const runtime = await loadRuntimeConfig(currentState);
  const url = normalizeConversationUrl(patch.url || "");
  if (!url) throw new Error("Open a concrete ChatGPT conversation first.");
  const id = conversationId(url);
  const existing = currentState.conversations[id];
  const agent = existing ? runtimeAgentForConversation(runtime, existing) : resolveBindingInput(runtime, patch);
  if (!agent) throw new Error("Existing conversation binding is invalid; remove and add the chat again.");

  const result = await mutateState((state) => {
    const previous = state.conversations[id];
    const currentAgent = previous ? runtimeAgentForConversation(runtime, previous) : agent;
    if (!currentAgent || (previous && previous.url !== url)) {
      throw new Error("Conversation identity changed during update; reopen the popup.");
    }
    const upserted = stateModel.upsertConversation(state, {
      label: patch.label,
      enabled: previous ? previous.enabled : patch.enabled,
      preferredTabId: patch.preferredTabId,
      url,
      repositoryId: currentAgent.repositoryId,
      repository: currentAgent.repository,
      agentBinding: currentAgent.agentBinding,
      bindingRevision: previous?.bindingRevision || 1,
      bindingSetAt: previous?.bindingSetAt || new Date().toISOString(),
      assistantBaseline: previous?.assistantBaseline || String(patch.assistantBaseline || ""),
      bootstrapPending: previous ? previous.bootstrapPending : true
    });
    if (!stateModel.isBoundConversation(upserted.conversation)) {
      throw new Error("conversation binding is required");
    }
    return { state: upserted.state, conversation: upserted.conversation };
  });
  if (result.conversation?.enabled) await scheduleDefault(result.conversation.id, true);
  return result.conversation;
}

async function rebindConversation(chatId, patch) {
  const state = await getBridgeState();
  const previous = state.conversations[chatId];
  if (!previous) throw new Error("conversation not found");
  if (inFlightDeliveries.has(chatId)) {
    throw new Error("Wait for the in-progress wake before changing this conversation.");
  }
  const runtime = await loadRuntimeConfig(state, previous);
  const agent = resolveBindingInput(runtime, patch);
  const result = await mutateState((nextState) => {
    const current = nextState.conversations[chatId];
    if (!current) throw new Error("conversation not found");
    const updated = stateModel.patchConversation(nextState, chatId, {
      repositoryId: agent.repositoryId,
      repository: agent.repository,
      agentBinding: agent.agentBinding,
      bindingRevision: Math.max(0, current.bindingRevision || 0) + 1,
      bindingSetAt: new Date().toISOString(),
      generation: current.generation + 1,
      assistantBaseline: "",
      bootstrapPending: true,
      lastControlFingerprint: "",
      lastControlAction: "",
      lastControlAt: null,
      lastStatus: "rebound_by_operator",
      enabled: true
    });
    return { state: updated.state, conversation: updated.conversation };
  });
  await scheduleDefault(chatId, true);
  return result.conversation;
}

async function updateConversation(chatId, patch) {
  const result = await mutateState((state) => {
    const previous = state.conversations[chatId];
    if (!previous) throw new Error("conversation not found");
    const safePatch = {};
    const previousInterval = previous.intervalOverrideMinutes;
    const previousEnabled = previous.enabled;

    if ("enabled" in patch) safePatch.enabled = Boolean(patch.enabled);
    if ("label" in patch) safePatch.label = patch.label;
    if ("intervalOverrideMinutes" in patch) safePatch.intervalOverrideMinutes = patch.intervalOverrideMinutes;
    if (safePatch.enabled && !stateModel.isBoundConversation(previous)) {
      throw new Error("conversation must be explicitly bound before it can be enabled");
    }
    if ("enabled" in safePatch || "intervalOverrideMinutes" in safePatch) {
      safePatch.generation = previous.generation + 1;
    }

    const updated = stateModel.patchConversation(state, chatId, safePatch);
    return {
      state: updated.state,
      conversation: updated.conversation,
      value: {
        enabledChanged: previousEnabled !== updated.conversation.enabled,
        pacingChanged: previousInterval !== updated.conversation.intervalOverrideMinutes
      }
    };
  });

  if (!result.conversation?.enabled) {
    await clearConversationAlarm(chatId);
  } else if (result.value?.enabledChanged) {
    await scheduleDefault(chatId, true);
  } else if (result.value?.pacingChanged) {
    await scheduleDefault(chatId);
  }
  return result.conversation;
}

async function deleteConversation(chatId) {
  if (inFlightDeliveries.has(chatId)) {
    throw new Error("Wait for the in-progress wake before removing this conversation.");
  }
  const result = await mutateState(async (state) => {
    await chrome.alarms.clear(alarmName(chatId));
    return stateModel.removeConversation(state, chatId);
  });
  return result.state;
}

