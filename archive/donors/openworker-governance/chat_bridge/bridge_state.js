(function initLocalAgentBridgeState(root, factory) {
  const protocol =
    root.LocalAgentBridgeProtocol ||
    (typeof require === "function" ? require("./control_protocol.js") : null);
  const api = factory(protocol);
  root.LocalAgentBridgeState = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createBridgeState(protocol) {
  "use strict";

  if (!protocol) throw new Error("Local Agent Bridge protocol is unavailable");

  const SCHEMA_VERSION = 3;
  const AGENT_BINDING_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  const DEFAULT_RUNTIME_URL =
    "https://raw.githubusercontent.com/MichalMatu/local-agent/chat-bridge-state/chat_bridge/runtime.json";
  const DEFAULT_BOOTSTRAP_PROMPT =
    "Local Agent Chat Bridge is enabled for this hard-bound conversation. Continue only its active goal from exact bound-repository evidence. Use direct GitHub edits when the exact diff and relevant CI can verify them; use Local Agent for Mac command execution, local builds/tests and devices. Check active local tasks before editing the same branch. For hybrid work verify the exact committed SHA. Follow MichalMatu/local-agent docs/AUTONOMOUS_CHAT_LOOP.md and docs/OPERATIONS.md. Never infer or switch repository identity.";
  const DEFAULT_WAKE_PROMPT =
    "[LA_WAKE] Continue the active goal from exact bound-repository evidence. Choose direct GitHub work or bounded local execution as appropriate; verify the exact commit/result. Do not recap unchanged state; keep this wake terse.";
  const DEFAULT_SETTINGS = Object.freeze({
    masterEnabled: true,
    runtimeUrl: DEFAULT_RUNTIME_URL,
    fallbackIntervalMinutes: 10,
    fallbackBusyRetryMinutes: 1,
    fallbackBootstrapPrompt: DEFAULT_BOOTSTRAP_PROMPT,
    fallbackWakePrompt: DEFAULT_WAKE_PROMPT
  });

  function clampNumber(value, fallback, minimum, maximum) {
    const number = Number(value);
    if (!Number.isFinite(number)) return fallback;
    return Math.min(maximum, Math.max(minimum, number));
  }

  function sanitizeSettings(raw = {}) {
    return {
      masterEnabled: raw.masterEnabled !== false,
      runtimeUrl: String(raw.runtimeUrl || DEFAULT_RUNTIME_URL).trim(),
      fallbackIntervalMinutes: clampNumber(
        raw.fallbackIntervalMinutes,
        DEFAULT_SETTINGS.fallbackIntervalMinutes,
        protocol.MIN_INTERVAL_MINUTES,
        protocol.MAX_INTERVAL_MINUTES
      ),
      fallbackBusyRetryMinutes: clampNumber(
        raw.fallbackBusyRetryMinutes,
        DEFAULT_SETTINGS.fallbackBusyRetryMinutes,
        1,
        60
      ),
      fallbackBootstrapPrompt: String(raw.fallbackBootstrapPrompt || DEFAULT_BOOTSTRAP_PROMPT).trim(),
      fallbackWakePrompt: String(raw.fallbackWakePrompt || DEFAULT_WAKE_PROMPT).trim()
    };
  }

  function sanitizeLabel(value, fallback = "ChatGPT conversation") {
    const label = String(value || "").trim().replace(/\s+/g, " ");
    return (label || fallback).slice(0, 120);
  }

  function sanitizeRepositoryId(value) {
    const repositoryId = String(value || "").trim();
    return /^[A-Za-z0-9._-]{1,120}$/.test(repositoryId) ? repositoryId : null;
  }

  function sanitizeRepository(value) {
    const repository = String(value || "").trim();
    return /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repository) ? repository : null;
  }

  function sanitizeAgentBinding(value) {
    const binding = String(value || "").trim();
    return AGENT_BINDING_RE.test(binding) ? binding : null;
  }

  function sanitizeConversation(raw = {}, fallbackUrl = "") {
    const url = protocol.normalizeConversationUrl(raw.url || fallbackUrl);
    if (!url) return null;
    const id = protocol.conversationId(url);
    const repositoryId = sanitizeRepositoryId(raw.repositoryId);
    const repository = sanitizeRepository(raw.repository);
    const agentBinding = sanitizeAgentBinding(raw.agentBinding);
    return {
      id,
      url,
      label: sanitizeLabel(raw.label, url.split("/").pop()),
      enabled: raw.enabled !== false,
      preferredTabId: Number.isInteger(raw.preferredTabId) ? raw.preferredTabId : null,
      repositoryId,
      repository,
      agentBinding,
      bindingRevision: Math.max(0, Math.trunc(Number(raw.bindingRevision) || 0)),
      bindingSetAt: raw.bindingSetAt || null,
      generation: Math.max(0, Math.trunc(Number(raw.generation) || 0)),
      assistantBaseline: String(raw.assistantBaseline || ""),
      intervalOverrideMinutes:
        raw.intervalOverrideMinutes === null || raw.intervalOverrideMinutes === undefined
          ? null
          : clampNumber(
              raw.intervalOverrideMinutes,
              null,
              protocol.MIN_INTERVAL_MINUTES,
              protocol.MAX_INTERVAL_MINUTES
            ),
      bootstrapPending: raw.bootstrapPending !== false,
      lastStatus: String(raw.lastStatus || "never_run"),
      lastRunAt: raw.lastRunAt || null,
      nextRunAt: raw.nextRunAt || null,
      lastRuntimeSource: String(raw.lastRuntimeSource || "fallback"),
      lastControlFingerprint: String(raw.lastControlFingerprint || ""),
      lastControlAction: String(raw.lastControlAction || ""),
      lastControlAt: raw.lastControlAt || null
    };
  }

  function isBoundConversation(conversation) {
    return Boolean(
      conversation &&
        sanitizeRepositoryId(conversation.repositoryId) &&
        sanitizeRepository(conversation.repository) &&
        sanitizeAgentBinding(conversation.agentBinding)
    );
  }

  function emptyState(settings = {}) {
    return { schemaVersion: SCHEMA_VERSION, settings: sanitizeSettings(settings), conversations: {} };
  }

  function normalizeState(raw) {
    const state = emptyState(raw?.settings || {});
    const sourceConversations = raw?.conversations;
    if (!sourceConversations || typeof sourceConversations !== "object") return state;
    for (const value of Object.values(sourceConversations)) {
      const conversation = sanitizeConversation(value);
      if (conversation) state.conversations[conversation.id] = conversation;
    }
    return state;
  }

  function migrateLegacyStorage(raw = {}) {
    if (raw.bridgeState?.schemaVersion === SCHEMA_VERSION) {
      const state = normalizeState(raw.bridgeState);
      const hadLegacyDeliveryState = Object.values(raw.bridgeState.conversations || {}).some(
        (conversation) => Object.hasOwn(conversation || {}, "pendingDelivery") ||
          String(conversation?.lastStatus || "") === "delivery_uncertain"
      );
      if (hadLegacyDeliveryState) {
        for (const conversation of Object.values(state.conversations)) {
          if (conversation.lastStatus === "delivery_uncertain") conversation.lastStatus = "delivery_unconfirmed";
        }
      }
      return { state, migrated: hadLegacyDeliveryState };
    }

    if (raw.bridgeState?.schemaVersion === 2) {
      const previous = normalizeState(raw.bridgeState);
      for (const conversation of Object.values(previous.conversations)) {
        if (!isBoundConversation(conversation)) {
          conversation.enabled = false;
          conversation.bootstrapPending = true;
          conversation.lastStatus = "binding_required";
          conversation.nextRunAt = null;
        }
      }
      return { state: previous, migrated: true };
    }

    const settings = sanitizeSettings({
      masterEnabled: true,
      runtimeUrl: raw.runtimeUrl,
      fallbackIntervalMinutes: raw.fallbackIntervalMinutes,
      fallbackBusyRetryMinutes: raw.fallbackBusyRetryMinutes,
      fallbackBootstrapPrompt: raw.fallbackPrompt,
      fallbackWakePrompt: DEFAULT_WAKE_PROMPT
    });
    const state = emptyState(settings);
    const legacyUrl = protocol.normalizeConversationUrl(raw.conversationUrl || "");
    if (legacyUrl) {
      const conversation = sanitizeConversation({
        url: legacyUrl,
        label: "Migrated conversation",
        enabled: false,
        intervalOverrideMinutes: raw.intervalOverrideMinutes === undefined ? null : raw.intervalOverrideMinutes,
        bootstrapPending: true,
        lastStatus: "binding_required",
        lastRunAt: raw.lastRunAt,
        nextRunAt: null,
        lastRuntimeSource: raw.lastRuntimeSource,
        lastControlFingerprint: raw.lastControlFingerprint,
        lastControlAction: raw.lastControlAction,
        lastControlAt: raw.lastControlAt
      });
      if (conversation) state.conversations[conversation.id] = conversation;
    }
    return { state, migrated: true };
  }

  function upsertConversation(state, patch) {
    const normalized = normalizeState(state);
    const url = protocol.normalizeConversationUrl(patch?.url || "");
    if (!url) throw new Error("invalid conversation URL");
    const id = protocol.conversationId(url);
    const previous = normalized.conversations[id] || {};
    const conversation = sanitizeConversation({
      ...previous,
      ...patch,
      url,
      id,
      bootstrapPending:
        patch.bootstrapPending !== undefined
          ? patch.bootstrapPending
          : previous.id
            ? previous.bootstrapPending
            : true
    });
    normalized.conversations[id] = conversation;
    return { state: normalized, conversation };
  }

  function patchConversation(state, conversationId, patch) {
    const normalized = normalizeState(state);
    const previous = normalized.conversations[conversationId];
    if (!previous) throw new Error("conversation not found");
    const updated = sanitizeConversation({ ...previous, ...patch, url: previous.url });
    normalized.conversations[conversationId] = updated;
    return { state: normalized, conversation: updated };
  }

  function removeConversation(state, conversationId) {
    const normalized = normalizeState(state);
    delete normalized.conversations[conversationId];
    return normalized;
  }

  function findConversationByUrl(state, url) {
    const normalizedUrl = protocol.normalizeConversationUrl(url);
    if (!normalizedUrl) return null;
    return normalizeState(state).conversations[protocol.conversationId(normalizedUrl)] || null;
  }

  return Object.freeze({
    SCHEMA_VERSION,
    AGENT_BINDING_RE,
    DEFAULT_RUNTIME_URL,
    DEFAULT_BOOTSTRAP_PROMPT,
    DEFAULT_WAKE_PROMPT,
    DEFAULT_SETTINGS,
    clampNumber,
    sanitizeSettings,
    sanitizeRepositoryId,
    sanitizeRepository,
    sanitizeAgentBinding,
    sanitizeConversation,
    isBoundConversation,
    emptyState,
    normalizeState,
    migrateLegacyStorage,
    upsertConversation,
    patchConversation,
    removeConversation,
    findConversationByUrl
  });
});
