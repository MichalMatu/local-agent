(function initLocalAgentEventWakeState(root, factory) {
  const protocol =
    root.LocalAgentBridgeProtocol ||
    (typeof require === "function" ? require("./control_protocol.js") : null);
  const bridgeState =
    root.LocalAgentBridgeState ||
    (typeof require === "function" ? require("./bridge_state.js") : null);
  const api = factory(protocol, bridgeState);
  root.LocalAgentEventWakeState = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createEventWakeState(protocol, bridgeState) {
  "use strict";

  if (!protocol || !bridgeState) throw new Error("Local Agent event wake dependencies are unavailable");

  const STATE_VERSION = 1;
  const NATIVE_EVENT_SCHEMA_VERSION = 1;
  const MAX_RECENT_EVENTS = 128;
  const RECENT_EVENT_TTL_MS = 7 * 24 * 60 * 60 * 1000;
  const MAX_FUTURE_SKEW_MS = 5 * 60 * 1000;
  const MAX_DIAGNOSTIC_ERROR_LENGTH = 512;
  const EVENT_ID_RE = /^evt-[0-9a-f]{32}$/;
  const EVENT_STATUS_RE = /^[A-Za-z0-9._:-]{1,64}$/;
  const EVENT_DIGEST_RE = /^[A-Za-z0-9._:-]{1,160}$/;
  const NATIVE_STATES = new Set([
    "unknown",
    "idle",
    "connecting",
    "connected",
    "disconnected",
    "unavailable",
    "unsupported",
    "incompatible"
  ]);

  function isoTimestamp(value) {
    if (typeof value !== "string") return null;
    const text = value.trim();
    if (text.length < 20 || text.length > 64 || !/^\d{4}-\d{2}-\d{2}T/.test(text)) return null;
    if (!/(?:Z|[+-]\d{2}:\d{2})$/.test(text)) return null;
    return Number.isFinite(Date.parse(text)) ? text : null;
  }

  function boundedError(value) {
    if (value === null || value === undefined || value === "") return null;
    return String(value).slice(0, MAX_DIAGNOSTIC_ERROR_LENGTH);
  }

  function emptyDiagnostics() {
    return {
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
    };
  }

  function sanitizeDiagnostics(raw) {
    const source = raw && typeof raw === "object" ? raw : {};
    const nativeState = String(source.nativeState || "unknown");
    const protocolVersion = Number(source.nativeProtocolVersion);
    const eventId = (value) => typeof value === "string" && EVENT_ID_RE.test(value) ? value : null;
    const taskId = (value) => typeof value === "string" && protocol.TASK_ID_RE.test(value) ? value : null;
    return {
      nativeState: NATIVE_STATES.has(nativeState) ? nativeState : "unknown",
      nativeProtocolVersion:
        Number.isInteger(protocolVersion) && protocolVersion > 0 && protocolVersion <= 100
          ? protocolVersion
          : null,
      lastConnectAt: isoTimestamp(source.lastConnectAt),
      lastDisconnectAt: isoTimestamp(source.lastDisconnectAt),
      lastError: boundedError(source.lastError),
      lastAcceptedEventId: eventId(source.lastAcceptedEventId),
      lastAcceptedTaskId: taskId(source.lastAcceptedTaskId),
      lastAcceptedAt: isoTimestamp(source.lastAcceptedAt),
      lastDeliveredEventId: eventId(source.lastDeliveredEventId),
      lastDeliveredAt: isoTimestamp(source.lastDeliveredAt)
    };
  }

  function emptyState() {
    return {
      version: STATE_VERSION,
      watches: {},
      recentEvents: {},
      pendingWakes: {},
      diagnostics: emptyDiagnostics()
    };
  }

  function sanitizeTaskWatch(raw) {
    if (!raw || typeof raw !== "object") return null;
    const conversationId = String(raw.conversationId || "");
    const repositoryId = bridgeState.sanitizeRepositoryId(raw.repositoryId);
    const repository = bridgeState.sanitizeRepository(raw.repository);
    const agentBinding = bridgeState.sanitizeAgentBinding(raw.agentBinding);
    const taskId = String(raw.taskId || "");
    const bindingRevision = Number(raw.bindingRevision);
    const bindingSetAt = isoTimestamp(raw.bindingSetAt);
    const createdAt = isoTimestamp(raw.createdAt);
    if (!protocol.CHAT_ID_RE.test(conversationId) || !repositoryId || !repository || !agentBinding) return null;
    if (!protocol.TASK_ID_RE.test(taskId) || !Number.isInteger(bindingRevision) || bindingRevision < 1) return null;
    if (!bindingSetAt || !createdAt) return null;
    return {
      conversationId,
      repositoryId,
      repository,
      agentBinding,
      taskId,
      bindingRevision,
      bindingSetAt,
      createdAt
    };
  }

  function sanitizeNativeTaskEvent(raw, { receivedAt = new Date().toISOString() } = {}) {
    if (!raw || typeof raw !== "object") return null;
    if (raw.schema_version !== NATIVE_EVENT_SCHEMA_VERSION || raw.event_type !== "task_result_ready") return null;
    const eventId = String(raw.event_id || "");
    const repositoryId = bridgeState.sanitizeRepositoryId(raw.repository_id);
    const repository = bridgeState.sanitizeRepository(raw.repository);
    const agentBinding = bridgeState.sanitizeAgentBinding(raw.agent_binding);
    const taskId = String(raw.task_id || "");
    const resultStatus = String(raw.result_status || "");
    const taskDigest = raw.task_digest === undefined ? null : String(raw.task_digest || "");
    const emittedAt = isoTimestamp(raw.emitted_at);
    const acceptedAt = isoTimestamp(receivedAt);
    if (!EVENT_ID_RE.test(eventId) || !repositoryId || !repository || !agentBinding) return null;
    if (!protocol.TASK_ID_RE.test(taskId) || !EVENT_STATUS_RE.test(resultStatus)) return null;
    if (taskDigest !== null && !EVENT_DIGEST_RE.test(taskDigest)) return null;
    if (!emittedAt || !acceptedAt) return null;
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
      receivedAt: acceptedAt
    };
  }

  function sanitizeStoredRecentEvent(raw) {
    if (!raw || typeof raw !== "object") return null;
    const receivedAt = isoTimestamp(raw.receivedAt);
    if (!receivedAt) return null;
    return sanitizeNativeTaskEvent({
      schema_version: NATIVE_EVENT_SCHEMA_VERSION,
      event_id: raw.eventId,
      event_type: raw.eventType,
      emitted_at: raw.emittedAt,
      repository_id: raw.repositoryId,
      repository: raw.repository,
      agent_binding: raw.agentBinding,
      task_id: raw.taskId,
      task_digest: raw.taskDigest ?? undefined,
      result_status: raw.resultStatus
    }, { receivedAt });
  }

  function sanitizePendingWake(raw) {
    if (!raw || typeof raw !== "object") return null;
    const eventId = String(raw.eventId || "");
    const taskId = String(raw.taskId || "");
    const repositoryId = bridgeState.sanitizeRepositoryId(raw.repositoryId);
    const repository = bridgeState.sanitizeRepository(raw.repository);
    const agentBinding = bridgeState.sanitizeAgentBinding(raw.agentBinding);
    const bindingRevision = Number(raw.bindingRevision);
    const bindingSetAt = isoTimestamp(raw.bindingSetAt);
    const receivedAt = isoTimestamp(raw.receivedAt);
    if (!EVENT_ID_RE.test(eventId) || !protocol.TASK_ID_RE.test(taskId)) return null;
    if (!repositoryId || !repository || !agentBinding) return null;
    if (!Number.isInteger(bindingRevision) || bindingRevision < 1 || !bindingSetAt || !receivedAt) return null;
    return {
      eventId,
      taskId,
      repositoryId,
      repository,
      agentBinding,
      bindingRevision,
      bindingSetAt,
      receivedAt
    };
  }

  function pruneState(state, now = Date.now()) {
    const entries = Object.values(state.recentEvents)
      .filter((event) => {
        const timestamp = Date.parse(event.receivedAt);
        if (!Number.isFinite(timestamp)) return false;
        const age = now - timestamp;
        return age >= -MAX_FUTURE_SKEW_MS && age <= RECENT_EVENT_TTL_MS;
      })
      .sort((left, right) =>
        Date.parse(left.receivedAt) - Date.parse(right.receivedAt) || left.eventId.localeCompare(right.eventId)
      );
    state.recentEvents = Object.fromEntries(
      entries.slice(Math.max(0, entries.length - MAX_RECENT_EVENTS)).map((event) => [event.eventId, event])
    );
    return state;
  }

  function sanitizeState(raw, now = Date.now()) {
    const state = emptyState();
    if (!raw || raw.version !== STATE_VERSION) return state;
    for (const [chatId, watch] of Object.entries(raw.watches || {})) {
      const normalized = sanitizeTaskWatch(watch);
      if (normalized && normalized.conversationId === chatId) state.watches[chatId] = normalized;
    }
    for (const [eventId, event] of Object.entries(raw.recentEvents || {})) {
      const normalized = sanitizeStoredRecentEvent(event);
      if (normalized && normalized.eventId === eventId) state.recentEvents[eventId] = normalized;
    }
    for (const [chatId, pending] of Object.entries(raw.pendingWakes || {})) {
      const normalized = sanitizePendingWake(pending);
      if (protocol.CHAT_ID_RE.test(chatId) && normalized) state.pendingWakes[chatId] = normalized;
    }
    state.diagnostics = sanitizeDiagnostics(raw.diagnostics);
    return pruneState(state, now);
  }

  function sameTaskClaim(left, right) {
    return Boolean(
      left && right &&
      left.repositoryId === right.repositoryId &&
      left.repository === right.repository &&
      left.agentBinding === right.agentBinding &&
      left.taskId === right.taskId
    );
  }

  function eventMatchesWatch(event, watch) {
    return sameTaskClaim(event, watch);
  }

  function watchMatchesConversation(watch, conversation) {
    return Boolean(
      watch && conversation && bridgeState.isBoundConversation(conversation) &&
      conversation.id === watch.conversationId &&
      conversation.repositoryId === watch.repositoryId &&
      conversation.repository === watch.repository &&
      conversation.agentBinding === watch.agentBinding &&
      conversation.bindingRevision === watch.bindingRevision &&
      conversation.bindingSetAt === watch.bindingSetAt
    );
  }

  function pendingWakeMatchesConversation(pending, conversation) {
    return Boolean(
      pending && conversation && bridgeState.isBoundConversation(conversation) &&
      conversation.repositoryId === pending.repositoryId &&
      conversation.repository === pending.repository &&
      conversation.agentBinding === pending.agentBinding &&
      conversation.bindingRevision === pending.bindingRevision &&
      conversation.bindingSetAt === pending.bindingSetAt
    );
  }

  function pendingWakeClaimsWatch(pending, watch) {
    return sameTaskClaim(pending, watch);
  }

  function pendingWakeFromEvent(event, watch) {
    return {
      eventId: event.eventId,
      taskId: event.taskId,
      repositoryId: watch.repositoryId,
      repository: watch.repository,
      agentBinding: watch.agentBinding,
      bindingRevision: watch.bindingRevision,
      bindingSetAt: watch.bindingSetAt,
      receivedAt: event.receivedAt
    };
  }

  return Object.freeze({
    STATE_VERSION,
    NATIVE_EVENT_SCHEMA_VERSION,
    MAX_RECENT_EVENTS,
    RECENT_EVENT_TTL_MS,
    MAX_FUTURE_SKEW_MS,
    EVENT_ID_RE,
    emptyState,
    isoTimestamp,
    sanitizeDiagnostics,
    sanitizeTaskWatch,
    sanitizeNativeTaskEvent,
    sanitizePendingWake,
    sanitizeState,
    pruneState,
    sameTaskClaim,
    eventMatchesWatch,
    watchMatchesConversation,
    pendingWakeMatchesConversation,
    pendingWakeClaimsWatch,
    pendingWakeFromEvent
  });
});