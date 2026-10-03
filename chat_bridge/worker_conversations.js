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
  const agent = existing
    ? (runtimeAgentForConversation(runtime, existing) || transportAgent(runtime))
    : resolveBindingInput(runtime, patch);

  const result = await mutateState((state) => {
    const previous = state.conversations[id];
    if (previous && previous.url !== url) {
      throw new Error("Conversation identity changed during update; reopen the popup.");
    }
    const currentAgent = previous
      ? (runtimeAgentForConversation(runtime, previous) || agent)
      : agent;
    const upserted = stateModel.upsertConversation(state, {
      label: patch.label,
      enabled: previous ? previous.enabled : patch.enabled,
      preferredTabId: patch.preferredTabId,
      url,
      // These fields are compatibility metadata only. The selected transport workspace
      // never determines the repository target of executable work.
      repositoryId: currentAgent?.repositoryId || previous?.repositoryId || null,
      repository: currentAgent?.repository || previous?.repository || null,
      agentBinding: currentAgent?.agentBinding || previous?.agentBinding || null,
      bindingRevision: previous?.bindingRevision || 1,
      bindingSetAt: previous?.bindingSetAt || new Date().toISOString(),
      assistantBaseline: previous?.assistantBaseline || String(patch.assistantBaseline || ""),
      bootstrapPending: previous ? previous.bootstrapPending : true,
      lastStatus: previous?.lastStatus || "transport_ready"
    });
    return { state: upserted.state, conversation: upserted.conversation };
  });
  if (!existing) await clearAssistantErrorRecovery(result.conversation.id);
  if (result.conversation?.enabled) {
    await scheduleDefault(result.conversation.id, true, result.conversation.generation);
  }
  return result.conversation;
}

async function rebindConversation(chatId, _patch) {
  // Bridge 0.8 compatibility path: repository rebinding is no longer meaningful.
  // Refresh only the transport-workspace metadata so old callers do not fail.
  return serializeGithubControlOperation(async () => {
    const state = await getBridgeState();
    const previous = state.conversations[chatId];
    if (!previous) throw new Error("conversation not found");
    if (inFlightDeliveries.has(chatId)) {
      throw new Error("Wait for the in-progress wake before refreshing this conversation.");
    }
    const runtime = await loadRuntimeConfig(state, previous);
    const agent = transportAgent(runtime);
    const result = await mutateState((nextState) => {
      const current = nextState.conversations[chatId];
      if (!current) throw new Error("conversation not found");
      const updated = stateModel.patchConversation(nextState, chatId, {
        repositoryId: agent?.repositoryId || current.repositoryId,
        repository: agent?.repository || current.repository,
        agentBinding: agent?.agentBinding || current.agentBinding,
        bindingRevision: Math.max(1, Number(current.bindingRevision) || 0),
        bindingSetAt: current.bindingSetAt || new Date().toISOString(),
        generation: current.generation + 1,
        assistantBaseline: "",
        bootstrapPending: true,
        lastControlFingerprint: "",
        lastControlAction: "",
        lastControlAt: null,
        lastStatus: "transport_scope_refreshed",
        enabled: true
      });
      return { state: updated.state, conversation: updated.conversation };
    });
    await clearAssistantErrorRecovery(chatId);
    await scheduleDefault(chatId, true, result.conversation.generation);
    return result.conversation;
  });
}

async function updateConversation(chatId, patch) {
  if ("enabled" in patch || "intervalOverrideMinutes" in patch) {
    const state = await getBridgeState();
    const current = state.conversations[chatId];
    if (!current) throw new Error("conversation not found");
    const authority = await githubScheduleAuthority(current, state);
    if (authority) {
      throw new Error("Conversation schedule is managed by GitHub desired state.");
    }
  }

  const result = await mutateState((state) => {
    const previous = state.conversations[chatId];
    if (!previous) throw new Error("conversation not found");
    const safePatch = {};
    const previousInterval = previous.intervalOverrideMinutes;
    const previousEnabled = previous.enabled;

    if ("enabled" in patch) safePatch.enabled = Boolean(patch.enabled);
    if ("label" in patch) safePatch.label = patch.label;
    if ("intervalOverrideMinutes" in patch) safePatch.intervalOverrideMinutes = patch.intervalOverrideMinutes;
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
    await clearConversationAlarm(chatId, result.conversation?.generation ?? null);
  } else if (result.value?.enabledChanged) {
    await scheduleDefault(chatId, true, result.conversation.generation);
  } else if (result.value?.pacingChanged) {
    await scheduleDefault(chatId, false, result.conversation.generation);
  }
  return result.conversation;
}

async function deleteConversation(chatId) {
  return serializeGithubControlOperation(async () => {
    if (inFlightDeliveries.has(chatId)) {
      throw new Error("Wait for the in-progress wake before removing this conversation.");
    }
    const result = await mutateState(async (state) => {
      await chrome.alarms.clear(alarmName(chatId));
      return stateModel.removeConversation(state, chatId);
    });
    await clearAssistantErrorRecovery(chatId);
    await clearAppliedGithubControl(chatId);
    return result.state;
  });
}
