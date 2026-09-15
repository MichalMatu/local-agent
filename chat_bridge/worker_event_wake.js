const EVENT_WAKE_STORAGE_KEY = "eventWakeState";
const EVENT_WAKE_STATE_VERSION = 1;
const NATIVE_EVENT_SCHEMA_VERSION = 1;
const MAX_RECENT_EVENTS = 128;
const RECENT_EVENT_TTL_MS = 7 * 24 * 60 * 60 * 1000;
const NATIVE_EVENT_ID_RE = /^evt-[0-9a-f]{32}$/;
const NATIVE_EVENT_STATUS_RE = /^[A-Za-z0-9._:-]{1,64}$/;

let eventWakeStateQueue = Promise.resolve();

function emptyEventWakeState() {
  return {
    version: EVENT_WAKE_STATE_VERSION,
    watches: {},
    recentEvents: {},
    pendingWakes: {},
    diagnostics: {
      nativeState: "unknown",
      nativeProtocolVersion: null,
      lastConnectAt: null,
      lastDisconnectAt: null,
      lastError: null,
      lastAcceptedEventId: null,
      lastAcceptedTaskId: null,
      lastAcceptedAt: null,
      lastDeliveredEventId: null,
      lastDeliveredAt: null
    }
  };
}

function boundedIso(value) {
  const text = String(value || "");
  return /^\d{4}-\d{2}-\d{2}T/.test(text) && text.length <= 64 ? text : null;
}

function sanitizeTaskWatch(raw) {
  if (!raw || typeof raw !== "object") return null;
  const conversationId = String(raw.conversationId || "");
  const repositoryId = stateModel.sanitizeRepositoryId(raw.repositoryId);
  const agentBinding = stateModel.sanitizeAgentBinding(raw.agentBinding);
  const taskId = String(raw.taskId || "");
  if (!protocol.CHAT_ID_RE.test(conversationId) || !repositoryId || !agentBinding || !protocol.TASK_ID_RE.test(taskId)) {
    return null;
  }
  return {
    conversationId,
    repositoryId,
    agentBinding,
    taskId,
    createdAt: boundedIso(raw.createdAt) || new Date().toISOString()
  };
}

function sanitizeNativeTaskEvent(raw, { receivedAt = null } = {}) {
  if (!raw || typeof raw !== "object") return null;
  if (raw.schema_version !== NATIVE_EVENT_SCHEMA_VERSION || raw.event_type !== "task_result_ready") return null;
  const eventId = String(raw.event_id || "");
  const repositoryId = stateModel.sanitizeRepositoryId(raw.repository_id);
  const repository = stateModel.sanitizeRepository(raw.repository);
  const agentBinding = stateModel.sanitizeAgentBinding(raw.agent_binding);
  const taskId = String(raw.task_id || "");
  const resultStatus = String(raw.result_status || "");
  const taskDigest = raw.task_digest === undefined ? null : String(raw.task_digest || "");
  if (!NATIVE_EVENT_ID_RE.test(eventId) || !repositoryId || !repository || !agentBinding) return null;
  if (!protocol.TASK_ID_RE.test(taskId) || !NATIVE_EVENT_STATUS_RE.test(resultStatus)) return null;
  if (taskDigest !== null && !/^[A-Za-z0-9._:-]{1,160}$/.test(taskDigest)) return null;
  const emittedAt = boundedIso(raw.emitted_at);
  if (!emittedAt) return null;
  return {
    eventId,
    eventType: "task_result_ready",
    repositoryId,
    repository,
    agentBinding,
    taskId,
    taskDigest,
    resultStatus,
    emittedAt,
    receivedAt: receivedAt || new Date().toISOString()
  };
}

function sanitizePendingWake(raw) {
  if (!raw || typeof raw !== "object") return null;
  const eventId = String(raw.eventId || "");
  const taskId = String(raw.taskId || "");
  if (!NATIVE_EVENT_ID_RE.test(eventId) || !protocol.TASK_ID_RE.test(taskId)) return null;
  return {
    eventId,
    taskId,
    receivedAt: boundedIso(raw.receivedAt) || new Date().toISOString()
  };
}

function sanitizeEventWakeState(raw) {
  const state = emptyEventWakeState();
  if (!raw || raw.version !== EVENT_WAKE_STATE_VERSION) return state;
  for (const [chatId, watch] of Object.entries(raw.watches || {})) {
    const normalized = sanitizeTaskWatch(watch);
    if (normalized && normalized.conversationId === chatId) state.watches[chatId] = normalized;
  }
  for (const [eventId, event] of Object.entries(raw.recentEvents || {})) {
    const normalized = sanitizeNativeTaskEvent({
      schema_version: NATIVE_EVENT_SCHEMA_VERSION,
      event_id: event?.eventId,
      event_type: event?.eventType,
      emitted_at: event?.emittedAt,
      repository_id: event?.repositoryId,
      repository: event?.repository,
      agent_binding: event?.agentBinding,
      task_id: event?.taskId,
      task_digest: event?.taskDigest ?? undefined,
      result_status: event?.resultStatus
    }, { receivedAt: boundedIso(event?.receivedAt) || new Date().toISOString() });
    if (normalized && normalized.eventId === eventId) state.recentEvents[eventId] = normalized;
  }
  for (const [chatId, pending] of Object.entries(raw.pendingWakes || {})) {
    const normalized = sanitizePendingWake(pending);
    if (protocol.CHAT_ID_RE.test(chatId) && normalized) state.pendingWakes[chatId] = normalized;
  }
  state.diagnostics = {
    ...state.diagnostics,
    ...(raw.diagnostics && typeof raw.diagnostics === "object" ? raw.diagnostics : {})
  };
  return pruneEventWakeState(state);
}

function pruneEventWakeState(state, now = Date.now()) {
  const entries = Object.values(state.recentEvents)
    .filter((event) => {
      const timestamp = Date.parse(event.receivedAt || event.emittedAt || "");
      return Number.isFinite(timestamp) && now - timestamp <= RECENT_EVENT_TTL_MS;
    })
    .sort((a, b) => Date.parse(a.receivedAt) - Date.parse(b.receivedAt) || a.eventId.localeCompare(b.eventId));
  state.recentEvents = Object.fromEntries(
    entries.slice(Math.max(0, entries.length - MAX_RECENT_EVENTS)).map((event) => [event.eventId, event])
  );
  return state;
}

async function loadEventWakeState() {
  await eventWakeStateQueue;
  const raw = await chrome.storage.local.get(EVENT_WAKE_STORAGE_KEY);
  return sanitizeEventWakeState(raw[EVENT_WAKE_STORAGE_KEY]);
}

function mutateEventWakeState(mutator) {
  const operation = eventWakeStateQueue.then(async () => {
    const raw = await chrome.storage.local.get(EVENT_WAKE_STORAGE_KEY);
    const state = sanitizeEventWakeState(raw[EVENT_WAKE_STORAGE_KEY]);
    const result = await mutator(state);
    const nextState = sanitizeEventWakeState(result?.state || result || state);
    await chrome.storage.local.set({ [EVENT_WAKE_STORAGE_KEY]: nextState });
    return { state: nextState, value: result?.value };
  });
  eventWakeStateQueue = operation.catch(() => undefined);
  return operation;
}

function eventMatchesWatch(event, watch) {
  return Boolean(
    event && watch &&
    event.repositoryId === watch.repositoryId &&
    event.agentBinding === watch.agentBinding &&
    event.taskId === watch.taskId
  );
}

function recentEventForWatch(state, watch) {
  return Object.values(state.recentEvents)
    .filter((event) => eventMatchesWatch(event, watch))
    .sort((a, b) => Date.parse(b.receivedAt) - Date.parse(a.receivedAt))[0] || null;
}

async function registerTaskWatch(conversation, taskId) {
  if (!stateModel.isBoundConversation(conversation) || !protocol.TASK_ID_RE.test(String(taskId || ""))) {
    return { ok: false, reason: "task_watch_invalid" };
  }
  const watch = sanitizeTaskWatch({
    conversationId: conversation.id,
    repositoryId: conversation.repositoryId,
    agentBinding: conversation.agentBinding,
    taskId,
    createdAt: new Date().toISOString()
  });
  if (!watch) return { ok: false, reason: "task_watch_invalid" };

  const result = await mutateEventWakeState((state) => {
    const conflict = Object.values(state.watches).find((candidate) =>
      candidate.conversationId !== conversation.id &&
      candidate.repositoryId === watch.repositoryId &&
      candidate.agentBinding === watch.agentBinding &&
      candidate.taskId === watch.taskId
    );
    if (conflict) {
      return { state, value: { ok: false, reason: "task_watch_conflict", conflictChatId: conflict.conversationId } };
    }
    state.watches[conversation.id] = watch;
    const event = recentEventForWatch(state, watch);
    if (event) {
      state.pendingWakes[conversation.id] = {
        eventId: event.eventId,
        taskId: event.taskId,
        receivedAt: event.receivedAt
      };
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
  return state.pendingWakes[chatId] || null;
}

async function acceptNativeTaskEvent(rawEvent) {
  const event = sanitizeNativeTaskEvent(rawEvent);
  if (!event) return { ok: false, reason: "native_event_invalid" };

  const bridgeState = await getBridgeState();
  const result = await mutateEventWakeState((state) => {
    state.recentEvents[event.eventId] = event;
    state.diagnostics.lastAcceptedEventId = event.eventId;
    state.diagnostics.lastAcceptedTaskId = event.taskId;
    state.diagnostics.lastAcceptedAt = event.receivedAt;

    const matching = Object.values(state.watches).filter((watch) => eventMatchesWatch(event, watch));
    if (matching.length > 1) {
      state.diagnostics.lastError = "task_watch_ambiguous";
      return { state, value: { ok: true, reason: "event_cached_ambiguous", matchedChatId: null } };
    }
    const watch = matching[0] || null;
    if (!watch) return { state, value: { ok: true, reason: "event_cached", matchedChatId: null } };

    const conversation = bridgeState.conversations[watch.conversationId];
    if (!conversation || !stateModel.isBoundConversation(conversation) ||
        conversation.repositoryId !== watch.repositoryId || conversation.agentBinding !== watch.agentBinding) {
      delete state.watches[watch.conversationId];
      delete state.pendingWakes[watch.conversationId];
      return { state, value: { ok: true, reason: "event_cached_stale_watch", matchedChatId: null } };
    }

    state.pendingWakes[watch.conversationId] = {
      eventId: event.eventId,
      taskId: event.taskId,
      receivedAt: event.receivedAt
    };
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

  const value = result.value;
  if (value?.matchedChatId && value.schedulable) {
    const scheduled = await scheduleAt(value.matchedChatId, Date.now() + 1000, value.generation);
    if (!scheduled) return { ok: false, reason: "event_schedule_failed" };
  }
  return value || { ok: true, reason: "event_cached" };
}

async function consumePendingEventWake(chatId, eventId) {
  await mutateEventWakeState((state) => {
    const pending = state.pendingWakes[chatId];
    if (!pending || pending.eventId !== eventId) return state;
    delete state.pendingWakes[chatId];
    const watch = state.watches[chatId];
    if (watch && watch.taskId === pending.taskId) delete state.watches[chatId];
    state.diagnostics.lastDeliveredEventId = eventId;
    state.diagnostics.lastDeliveredAt = new Date().toISOString();
    return state;
  });
}

async function updateNativeDiagnostics(patch) {
  await mutateEventWakeState((state) => {
    state.diagnostics = { ...state.diagnostics, ...patch };
    return state;
  });
}

function buildEventWakePrompt(runtime, conversation, pending) {
  const base = conversation.bootstrapPending
    ? buildBootstrapPrompt(runtime, conversation)
    : `${bindingPolicy(conversation, runtimeAgentForConversation(runtime, conversation))}\n${runtime.wakePrompt}`;
  return `${base}\n[LA_EVENT=task_result_ready]\n[LA_TASK=${pending.taskId}]\nExact terminal result evidence is now available. Read the exact result before deciding the next action; this event is only a wake hint.`;
}
