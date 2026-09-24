const WORKFLOW_ATTENTION_STORAGE_KEY = "workflowAttentionState";
const workflowAttentionModel = globalThis.LocalAgentWorkflowAttentionState;

let workflowAttentionStateQueue = Promise.resolve();

async function loadWorkflowAttentionState() {
  await workflowAttentionStateQueue;
  const raw = await chrome.storage.local.get(WORKFLOW_ATTENTION_STORAGE_KEY);
  return workflowAttentionModel.sanitizeState(raw[WORKFLOW_ATTENTION_STORAGE_KEY]);
}

function mutateWorkflowAttentionState(mutator) {
  const operation = workflowAttentionStateQueue.then(async () => {
    const raw = await chrome.storage.local.get(WORKFLOW_ATTENTION_STORAGE_KEY);
    const state = workflowAttentionModel.sanitizeState(raw[WORKFLOW_ATTENTION_STORAGE_KEY]);
    const result = await mutator(state);
    const nextState = workflowAttentionModel.sanitizeState(result?.state || result || state);
    await chrome.storage.local.set({ [WORKFLOW_ATTENTION_STORAGE_KEY]: nextState });
    return { state: nextState, value: result?.value };
  });
  workflowAttentionStateQueue = operation.catch(() => undefined);
  return operation;
}

function recentWorkflowEventsForWatch(state, watch) {
  return Object.values(state.recentEvents)
    .filter((event) => workflowAttentionModel.eventMatchesWatch(event, watch))
    .sort((left, right) =>
      Date.parse(left.receivedAt) - Date.parse(right.receivedAt) || left.eventId.localeCompare(right.eventId)
    );
}

function pendingWorkflowEventsForWatch(state, watch) {
  return Object.values(state.pendingWakes)
    .filter((pending) =>
      pending.conversationId === watch.conversationId && pending.workflowId === watch.workflowId
    )
    .sort((left, right) =>
      Date.parse(left.receivedAt) - Date.parse(right.receivedAt) || left.eventId.localeCompare(right.eventId)
    );
}

function sameWorkflowSubscription(left, right) {
  return Boolean(
    left && right &&
    left.conversationId === right.conversationId &&
    left.conversationUrl === right.conversationUrl &&
    left.workflowId === right.workflowId &&
    left.bindingRevision === right.bindingRevision &&
    left.bindingSetAt === right.bindingSetAt
  );
}

async function reconcileWorkflowAttentionOwnership(bridgeState = null) {
  const currentBridgeState = bridgeState || await getBridgeState();
  const currentAttentionState = await loadWorkflowAttentionState();
  const staleWatchIds = Object.entries(currentAttentionState.watches)
    .filter(([chatId, watch]) =>
      !workflowAttentionModel.watchMatchesConversation(watch, currentBridgeState.conversations[chatId])
    )
    .map(([chatId]) => chatId);
  const stalePendingIds = Object.entries(currentAttentionState.pendingWakes)
    .filter(([, pending]) =>
      !workflowAttentionModel.pendingWakeMatchesConversation(
        pending,
        currentBridgeState.conversations[pending.conversationId]
      )
    )
    .map(([eventId]) => eventId);
  if (!staleWatchIds.length && !stalePendingIds.length) return currentAttentionState;

  const result = await mutateWorkflowAttentionState((state) => {
    for (const chatId of staleWatchIds) {
      const watch = state.watches[chatId];
      if (watch && !workflowAttentionModel.watchMatchesConversation(
        watch,
        currentBridgeState.conversations[chatId]
      )) {
        delete state.watches[chatId];
      }
    }
    for (const eventId of stalePendingIds) {
      const pending = state.pendingWakes[eventId];
      if (pending && !workflowAttentionModel.pendingWakeMatchesConversation(
        pending,
        currentBridgeState.conversations[pending.conversationId]
      )) {
        delete state.pendingWakes[eventId];
      }
    }
    return state;
  });
  return result.state;
}

async function registerWorkflowWatch(conversation, workflowId) {
  if (!stateModel.isBoundConversation(conversation)) {
    return { ok: false, reason: "workflow_watch_invalid" };
  }
  const watch = workflowAttentionModel.sanitizeWorkflowWatch({
    conversationId: conversation.id,
    conversationUrl: conversation.url,
    workflowId,
    bindingRevision: conversation.bindingRevision,
    bindingSetAt: conversation.bindingSetAt,
    createdAt: new Date().toISOString()
  });
  if (!watch) return { ok: false, reason: "workflow_watch_invalid" };

  const bridgeState = await getBridgeState();
  if (!workflowAttentionModel.watchMatchesConversation(
    watch,
    bridgeState.conversations[conversation.id]
  )) {
    return { ok: false, reason: "workflow_watch_stale_binding" };
  }
  await reconcileWorkflowAttentionOwnership(bridgeState);

  const result = await mutateWorkflowAttentionState((state) => {
    const existing = state.watches[conversation.id] || null;
    if (sameWorkflowSubscription(existing, watch)) {
      const pending = pendingWorkflowEventsForWatch(state, existing);
      return {
        state,
        value: {
          ok: true,
          matchedRecentEvents: pending.length,
          oldestEventId: pending[0]?.eventId || null,
          subscriptionUnchanged: true
        }
      };
    }

    state.watches[conversation.id] = watch;
    for (const [eventId, pending] of Object.entries(state.pendingWakes)) {
      if (pending.conversationId === conversation.id && pending.workflowId !== watch.workflowId) {
        delete state.pendingWakes[eventId];
      }
    }
    const recent = recentWorkflowEventsForWatch(state, watch);
    for (const event of recent) {
      state.pendingWakes[event.eventId] = workflowAttentionModel.pendingWakeFromEvent(event, watch);
    }
    return {
      state,
      value: {
        ok: true,
        matchedRecentEvents: recent.length,
        oldestEventId: recent[0]?.eventId || null,
        subscriptionUnchanged: false
      }
    };
  });
  return result.value;
}

async function clearWorkflowWatch(chatId, { clearPending = true } = {}) {
  await mutateWorkflowAttentionState((state) => {
    delete state.watches[chatId];
    if (clearPending) {
      for (const [eventId, pending] of Object.entries(state.pendingWakes)) {
        if (pending.conversationId === chatId) delete state.pendingWakes[eventId];
      }
    }
    return state;
  });
}

async function pendingWorkflowAttention(chatId) {
  const state = await loadWorkflowAttentionState();
  const candidates = Object.values(state.pendingWakes)
    .filter((pending) => pending.conversationId === chatId)
    .sort((left, right) =>
      Date.parse(left.receivedAt) - Date.parse(right.receivedAt) || left.eventId.localeCompare(right.eventId)
    );
  if (!candidates.length) return null;

  const bridgeState = await getBridgeState();
  const conversation = bridgeState.conversations[chatId];
  const pending = candidates[0];
  if (workflowAttentionModel.pendingWakeMatchesConversation(pending, conversation)) return pending;

  await mutateWorkflowAttentionState((nextState) => {
    const current = nextState.pendingWakes[pending.eventId];
    if (current && !workflowAttentionModel.pendingWakeMatchesConversation(current, conversation)) {
      delete nextState.pendingWakes[pending.eventId];
    }
    return nextState;
  });
  return null;
}

async function persistNativeChildTerminalEvent(rawEvent) {
  const event = workflowAttentionModel.sanitizeNativeChildTerminalEvent(rawEvent);
  if (!event) return { ok: false, reason: "native_event_invalid" };

  const bridgeState = await getBridgeState();
  const result = await mutateWorkflowAttentionState((state) => {
    state.recentEvents[event.eventId] = event;
    const matching = Object.values(state.watches).filter((watch) =>
      workflowAttentionModel.eventMatchesWatch(event, watch)
    );
    if (matching.length > 1) {
      return {
        state,
        value: { ok: true, reason: "workflow_event_cached_ambiguous", matchedChatId: null }
      };
    }
    const watch = matching[0] || null;
    if (!watch) {
      return { state, value: { ok: true, reason: "workflow_event_cached", matchedChatId: null } };
    }
    const conversation = bridgeState.conversations[watch.conversationId];
    if (!workflowAttentionModel.watchMatchesConversation(watch, conversation)) {
      delete state.watches[watch.conversationId];
      return {
        state,
        value: { ok: true, reason: "workflow_event_cached_stale_watch", matchedChatId: null }
      };
    }
    state.pendingWakes[event.eventId] = workflowAttentionModel.pendingWakeFromEvent(event, watch);
    return {
      state,
      value: {
        ok: true,
        reason: "workflow_event_pending",
        matchedChatId: watch.conversationId,
        generation: conversation.generation,
        schedulable: bridgeState.settings.masterEnabled && conversation.enabled
      }
    };
  });
  return result.value || { ok: true, reason: "workflow_event_cached", matchedChatId: null };
}

async function consumePendingWorkflowAttention(eventId) {
  await mutateWorkflowAttentionState((state) => {
    delete state.pendingWakes[eventId];
    return state;
  });
}
