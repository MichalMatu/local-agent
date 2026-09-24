(function initLocalAgentWorkflowAttentionState(root, factory) {
  const protocol =
    root.LocalAgentBridgeProtocol ||
    (typeof require === "function" ? require("./control_protocol.js") : null);
  const bridgeState =
    root.LocalAgentBridgeState ||
    (typeof require === "function" ? require("./bridge_state.js") : null);
  const api = factory(protocol, bridgeState);
  root.LocalAgentWorkflowAttentionState = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createWorkflowAttentionState(protocol, bridgeState) {
  "use strict";

  if (!protocol || !bridgeState) throw new Error("Local Agent workflow attention dependencies are unavailable");

  const STATE_VERSION = 1;
  const NATIVE_EVENT_SCHEMA_VERSION = 1;
  const MAX_RECENT_EVENTS = 128;
  const MAX_PENDING_WAKES = 128;
  const RECENT_EVENT_TTL_MS = 7 * 24 * 60 * 60 * 1000;
  const MAX_FUTURE_SKEW_MS = 5 * 60 * 1000;
  const EVENT_ID_RE = /^evt-[0-9a-f]{32}$/;
  const ID_RE = /^[A-Za-z0-9._-]{1,200}$/;
  const DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
  const OUTCOMES = new Set(["succeeded", "failed"]);

  function isoTimestamp(value) {
    if (typeof value !== "string") return null;
    const text = value.trim();
    if (text.length < 20 || text.length > 64 || !/^\d{4}-\d{2}-\d{2}T/.test(text)) return null;
    if (!/(?:Z|[+-]\d{2}:\d{2})$/.test(text)) return null;
    return Number.isFinite(Date.parse(text)) ? text : null;
  }

  function canonicalConversationUrl(value) {
    const normalized = protocol.normalizeConversationUrl(String(value || ""));
    return normalized || null;
  }

  function emptyState() {
    return { version: STATE_VERSION, watches: {}, recentEvents: {}, pendingWakes: {} };
  }

  function sanitizeWorkflowWatch(raw) {
    if (!raw || typeof raw !== "object") return null;
    const conversationId = String(raw.conversationId || "");
    const conversationUrl = canonicalConversationUrl(raw.conversationUrl);
    const workflowId = String(raw.workflowId || "");
    const bindingRevision = Number(raw.bindingRevision);
    const bindingSetAt = isoTimestamp(raw.bindingSetAt);
    const createdAt = isoTimestamp(raw.createdAt);
    if (!protocol.CHAT_ID_RE.test(conversationId) || !conversationUrl || !ID_RE.test(workflowId)) return null;
    if (!Number.isInteger(bindingRevision) || bindingRevision < 1 || !bindingSetAt || !createdAt) return null;
    return { conversationId, conversationUrl, workflowId, bindingRevision, bindingSetAt, createdAt };
  }

  function sanitizeNativeChildTerminalEvent(raw, { receivedAt = new Date().toISOString() } = {}) {
    if (!raw || typeof raw !== "object") return null;
    if (raw.schema_version !== NATIVE_EVENT_SCHEMA_VERSION || raw.event_type !== "child_terminal_ready") return null;
    const eventId = String(raw.event_id || "");
    const parentConversationUrl = canonicalConversationUrl(raw.parent_conversation_url);
    const workflowId = String(raw.workflow_id || "");
    const workflowNodeId = String(raw.workflow_node_id || "");
    const childRequestId = String(raw.child_request_id || "");
    const childRequestDigest = String(raw.child_request_digest || "");
    const terminalDigest = String(raw.terminal_digest || "");
    const outcome = String(raw.outcome || "");
    const emittedAt = isoTimestamp(raw.emitted_at);
    const acceptedAt = isoTimestamp(receivedAt);
    if (!EVENT_ID_RE.test(eventId) || !parentConversationUrl) return null;
    if (![workflowId, workflowNodeId, childRequestId].every((value) => ID_RE.test(value))) return null;
    if (!DIGEST_RE.test(childRequestDigest) || !DIGEST_RE.test(terminalDigest) || !OUTCOMES.has(outcome)) return null;
    if (!emittedAt || !acceptedAt) return null;
    return {
      eventId,
      eventType: "child_terminal_ready",
      parentConversationUrl,
      workflowId,
      workflowNodeId,
      childRequestId,
      childRequestDigest,
      terminalDigest,
      outcome,
      emittedAt,
      receivedAt: acceptedAt
    };
  }

  function sanitizeStoredEvent(raw) {
    if (!raw || typeof raw !== "object") return null;
    const receivedAt = isoTimestamp(raw.receivedAt);
    if (!receivedAt) return null;
    return sanitizeNativeChildTerminalEvent({
      schema_version: NATIVE_EVENT_SCHEMA_VERSION,
      event_id: raw.eventId,
      event_type: raw.eventType,
      emitted_at: raw.emittedAt,
      parent_conversation_url: raw.parentConversationUrl,
      workflow_id: raw.workflowId,
      workflow_node_id: raw.workflowNodeId,
      child_request_id: raw.childRequestId,
      child_request_digest: raw.childRequestDigest,
      terminal_digest: raw.terminalDigest,
      outcome: raw.outcome
    }, { receivedAt });
  }

  function sanitizePendingWake(raw) {
    if (!raw || typeof raw !== "object") return null;
    const eventId = String(raw.eventId || "");
    const conversationId = String(raw.conversationId || "");
    const parentConversationUrl = canonicalConversationUrl(raw.parentConversationUrl);
    const workflowId = String(raw.workflowId || "");
    const workflowNodeId = String(raw.workflowNodeId || "");
    const childRequestId = String(raw.childRequestId || "");
    const childRequestDigest = String(raw.childRequestDigest || "");
    const terminalDigest = String(raw.terminalDigest || "");
    const outcome = String(raw.outcome || "");
    const bindingRevision = Number(raw.bindingRevision);
    const bindingSetAt = isoTimestamp(raw.bindingSetAt);
    const receivedAt = isoTimestamp(raw.receivedAt);
    if (!EVENT_ID_RE.test(eventId) || !protocol.CHAT_ID_RE.test(conversationId) || !parentConversationUrl) return null;
    if (![workflowId, workflowNodeId, childRequestId].every((value) => ID_RE.test(value))) return null;
    if (!DIGEST_RE.test(childRequestDigest) || !DIGEST_RE.test(terminalDigest) || !OUTCOMES.has(outcome)) return null;
    if (!Number.isInteger(bindingRevision) || bindingRevision < 1 || !bindingSetAt || !receivedAt) return null;
    return {
      eventId,
      conversationId,
      parentConversationUrl,
      workflowId,
      workflowNodeId,
      childRequestId,
      childRequestDigest,
      terminalDigest,
      outcome,
      bindingRevision,
      bindingSetAt,
      receivedAt
    };
  }

  function boundedEntries(values, maximum, now) {
    return values
      .filter((item) => {
        const timestamp = Date.parse(item.receivedAt);
        if (!Number.isFinite(timestamp)) return false;
        const age = now - timestamp;
        return age >= -MAX_FUTURE_SKEW_MS && age <= RECENT_EVENT_TTL_MS;
      })
      .sort((left, right) => Date.parse(left.receivedAt) - Date.parse(right.receivedAt) || left.eventId.localeCompare(right.eventId))
      .slice(-maximum);
  }

  function pruneState(state, now = Date.now()) {
    state.recentEvents = Object.fromEntries(
      boundedEntries(Object.values(state.recentEvents), MAX_RECENT_EVENTS, now).map((event) => [event.eventId, event])
    );
    state.pendingWakes = Object.fromEntries(
      boundedEntries(Object.values(state.pendingWakes), MAX_PENDING_WAKES, now).map((pending) => [pending.eventId, pending])
    );
    return state;
  }

  function sanitizeState(raw, now = Date.now()) {
    const state = emptyState();
    if (!raw || raw.version !== STATE_VERSION) return state;
    for (const [chatId, watch] of Object.entries(raw.watches || {})) {
      const normalized = sanitizeWorkflowWatch(watch);
      if (normalized && normalized.conversationId === chatId) state.watches[chatId] = normalized;
    }
    for (const [eventId, event] of Object.entries(raw.recentEvents || {})) {
      const normalized = sanitizeStoredEvent(event);
      if (normalized && normalized.eventId === eventId) state.recentEvents[eventId] = normalized;
    }
    for (const [eventId, pending] of Object.entries(raw.pendingWakes || {})) {
      const normalized = sanitizePendingWake(pending);
      if (normalized && normalized.eventId === eventId) state.pendingWakes[eventId] = normalized;
    }
    return pruneState(state, now);
  }

  function watchMatchesConversation(watch, conversation) {
    return Boolean(
      watch && conversation && bridgeState.isBoundConversation(conversation) &&
      conversation.id === watch.conversationId &&
      conversation.url === watch.conversationUrl &&
      conversation.bindingRevision === watch.bindingRevision &&
      conversation.bindingSetAt === watch.bindingSetAt
    );
  }

  function eventMatchesWatch(event, watch) {
    return Boolean(
      event && watch &&
      event.parentConversationUrl === watch.conversationUrl &&
      event.workflowId === watch.workflowId
    );
  }

  function pendingWakeMatchesConversation(pending, conversation) {
    return Boolean(
      pending && conversation && bridgeState.isBoundConversation(conversation) &&
      pending.conversationId === conversation.id &&
      pending.parentConversationUrl === conversation.url &&
      pending.bindingRevision === conversation.bindingRevision &&
      pending.bindingSetAt === conversation.bindingSetAt
    );
  }

  function pendingWakeFromEvent(event, watch) {
    return {
      eventId: event.eventId,
      conversationId: watch.conversationId,
      parentConversationUrl: watch.conversationUrl,
      workflowId: event.workflowId,
      workflowNodeId: event.workflowNodeId,
      childRequestId: event.childRequestId,
      childRequestDigest: event.childRequestDigest,
      terminalDigest: event.terminalDigest,
      outcome: event.outcome,
      bindingRevision: watch.bindingRevision,
      bindingSetAt: watch.bindingSetAt,
      receivedAt: event.receivedAt
    };
  }

  return Object.freeze({
    STATE_VERSION,
    NATIVE_EVENT_SCHEMA_VERSION,
    MAX_RECENT_EVENTS,
    MAX_PENDING_WAKES,
    RECENT_EVENT_TTL_MS,
    MAX_FUTURE_SKEW_MS,
    EVENT_ID_RE,
    ID_RE,
    emptyState,
    isoTimestamp,
    sanitizeWorkflowWatch,
    sanitizeNativeChildTerminalEvent,
    sanitizePendingWake,
    sanitizeState,
    pruneState,
    watchMatchesConversation,
    eventMatchesWatch,
    pendingWakeMatchesConversation,
    pendingWakeFromEvent
  });
});
