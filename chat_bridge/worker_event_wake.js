const EVENT_WAKE_STORAGE_KEY = "eventWakeState";
const eventWakeModel = globalThis.LocalAgentEventWakeState;

let eventWakeStateQueue = Promise.resolve();

async function loadEventWakeState() {
  await eventWakeStateQueue;
  const raw = await chrome.storage.local.get(EVENT_WAKE_STORAGE_KEY);
  return eventWakeModel.sanitizeState(raw[EVENT_WAKE_STORAGE_KEY]);
}

function mutateEventWakeState(mutator) {
  const operation = eventWakeStateQueue.then(async () => {
    const raw = await chrome.storage.local.get(EVENT_WAKE_STORAGE_KEY);
    const state = eventWakeModel.sanitizeState(raw[EVENT_WAKE_STORAGE_KEY]);
    const result = await mutator(state);
    const nextState = eventWakeModel.sanitizeState(result?.state || result || state);
    await chrome.storage.local.set({ [EVENT_WAKE_STORAGE_KEY]: nextState });
    return { state: nextState, value: result?.value };
  });
  eventWakeStateQueue = operation.catch(() => undefined);
  return operation;
}

function recentEventForWatch(state, watch) {
  return Object.values(state.recentEvents)
    .filter((event) => eventWakeModel.eventMatchesWatch(event, watch))
    .sort((left, right) =>
      Date.parse(right.receivedAt) - Date.parse(left.receivedAt) || right.eventId.localeCompare(left.eventId)
    )[0] || null;
}

async function reconcileEventWakeOwnership(bridgeState = null) {
  const currentBridgeState = bridgeState || await getBridgeState();
  const currentEventState = await loadEventWakeState();
  const staleWatchIds = Object.entries(currentEventState.watches)
    .filter(([chatId, watch]) =>
      !eventWakeModel.watchMatchesConversation(watch, currentBridgeState.conversations[chatId])
    )
    .map(([chatId]) => chatId);
  const stalePendingIds = Object.entries(currentEventState.pendingWakes)
    .filter(([chatId, pending]) =>
      !eventWakeModel.pendingWakeMatchesConversation(pending, currentBridgeState.conversations[chatId])
    )
    .map(([chatId]) => chatId);
  if (!staleWatchIds.length && !stalePendingIds.length) return currentEventState;

  const result = await mutateEventWakeState((state) => {
    for (const chatId of staleWatchIds) {
      const watch = state.watches[chatId];
      if (watch && !eventWakeModel.watchMatchesConversation(watch, currentBridgeState.conversations[chatId])) {
        delete state.watches[chatId];
      }
    }
    for (const chatId of stalePendingIds) {
      const pending = state.pendingWakes[chatId];
      if (pending && !eventWakeModel.pendingWakeMatchesConversation(pending, currentBridgeState.conversations[chatId])) {
        delete state.pendingWakes[chatId];
      }
    }
    return state;
  });
  return result.state;
}

async function registerTaskWatch(conversation, taskId) {
  if (!stateModel.isBoundConversation(conversation) || !protocol.TASK_ID_RE.test(String(taskId || ""))) {
    return { ok: false, reason: "task_watch_invalid" };
  }
  const watch = eventWakeModel.sanitizeTaskWatch({
    conversationId: conversation.id,
    repositoryId: conversation.repositoryId,
    repository: conversation.repository,
    agentBinding: conversation.agentBinding,
    taskId,
    bindingRevision: conversation.bindingRevision,
    bindingSetAt: conversation.bindingSetAt,
    createdAt: new Date().toISOString()
  });
  if (!watch) return { ok: false, reason: "task_watch_invalid" };

  const bridgeState = await getBridgeState();
  if (!eventWakeModel.watchMatchesConversation(watch, bridgeState.conversations[conversation.id])) {
    return { ok: false, reason: "task_watch_stale_binding" };
  }
  await reconcileEventWakeOwnership(bridgeState);

  const result = await mutateEventWakeState((state) => {
    const watchConflict = Object.values(state.watches).find((candidate) =>
      candidate.conversationId !== conversation.id && eventWakeModel.sameTaskClaim(candidate, watch)
    );
    if (watchConflict) {
      return {
        state,
        value: {
          ok: false,
          reason: "task_watch_conflict",
          conflictChatId: watchConflict.conversationId
        }
      };
    }

    const pendingConflict = Object.entries(state.pendingWakes).find(([candidateChatId, candidate]) =>
      candidateChatId !== conversation.id && eventWakeModel.pendingWakeClaimsWatch(candidate, watch)
    );
    if (pendingConflict) {
      return {
        state,
        value: {
          ok: false,
          reason: "task_watch_conflict",
          conflictChatId: pendingConflict[0]
        }
      };
    }

    state.watches[conversation.id] = watch;
    const event = recentEventForWatch(state, watch);
    if (event) {
      state.pendingWakes[conversation.id] = eventWakeModel.pendingWakeFromEvent(event, watch);
      delete state.watches[conversation.id];
    } else {
      delete state.pendingWakes[conversation.id];
    }
    return {
      state,
      value: {
        ok: true,
        matchedRecentEvent: Boolean(event),
        eventId: event?.eventId || null
      }
    };
  });
  return result.value;
}

async function clearTaskWatch(chatId, { clearPending = true } = {}) {
  await mutateEventWakeState((state) => {
    delete state.watches[chatId];
    if (clearPending) delete state.pendingWakes[chatId];
    return state;
  });
}

async function pendingEventWake(chatId) {
  const state = await loadEventWakeState();
  const pending = state.pendingWakes[chatId] || null;
  if (!pending) return null;

  const bridgeState = await getBridgeState();
  const conversation = bridgeState.conversations[chatId];
  if (eventWakeModel.pendingWakeMatchesConversation(pending, conversation)) return pending;

  await mutateEventWakeState((nextState) => {
    const current = nextState.pendingWakes[chatId];
    if (
      current &&
      current.eventId === pending.eventId &&
      current.bindingRevision === pending.bindingRevision &&
      current.bindingSetAt === pending.bindingSetAt
    ) {
      delete nextState.pendingWakes[chatId];
    }
    return nextState;
  });
  return null;
}

async function persistNativeTaskEvent(rawEvent) {
  const event = eventWakeModel.sanitizeNativeTaskEvent(rawEvent);
  if (!event) return { ok: false, reason: "native_event_invalid" };

  const bridgeState = await getBridgeState();
  const result = await mutateEventWakeState((state) => {
    state.recentEvents[event.eventId] = event;
    state.diagnostics.lastAcceptedEventId = event.eventId;
    state.diagnostics.lastAcceptedTaskId = event.taskId;
    state.diagnostics.lastAcceptedAt = event.receivedAt;

    const matching = Object.values(state.watches).filter((watch) =>
      eventWakeModel.eventMatchesWatch(event, watch)
    );
    if (matching.length > 1) {
      state.diagnostics.lastError = "task_watch_ambiguous";
      return {
        state,
        value: { ok: true, reason: "event_cached_ambiguous", matchedChatId: null }
      };
    }

    const watch = matching[0] || null;
    if (!watch) {
      return { state, value: { ok: true, reason: "event_cached", matchedChatId: null } };
    }

    const conversation = bridgeState.conversations[watch.conversationId];
    if (!eventWakeModel.watchMatchesConversation(watch, conversation)) {
      delete state.watches[watch.conversationId];
      delete state.pendingWakes[watch.conversationId];
      return {
        state,
        value: { ok: true, reason: "event_cached_stale_watch", matchedChatId: null }
      };
    }

    state.pendingWakes[watch.conversationId] = eventWakeModel.pendingWakeFromEvent(event, watch);
    delete state.watches[watch.conversationId];
    return {
      state,
      value: {
        ok: true,
        reason: "event_pending",
        matchedChatId: watch.conversationId,
        generation: conversation.generation,
        schedulable: bridgeState.settings.masterEnabled && conversation.enabled
      }
    };
  });
  return result.value || { ok: true, reason: "event_cached", matchedChatId: null };
}

async function consumePendingEventWake(chatId, eventId) {
  await mutateEventWakeState((state) => {
    const pending = state.pendingWakes[chatId];
    if (!pending || pending.eventId !== eventId) return state;
    delete state.pendingWakes[chatId];
    delete state.watches[chatId];
    state.diagnostics.lastDeliveredEventId = eventId;
    state.diagnostics.lastDeliveredAt = new Date().toISOString();
    return state;
  });
}

async function updateNativeDiagnostics(patch) {
  await mutateEventWakeState((state) => {
    state.diagnostics = eventWakeModel.sanitizeDiagnostics({ ...state.diagnostics, ...patch });
    return state;
  });
}