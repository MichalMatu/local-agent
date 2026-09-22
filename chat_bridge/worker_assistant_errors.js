const ASSISTANT_ERROR_RECOVERY_STORAGE_KEY = "bridgeAssistantErrorRecovery";
const ASSISTANT_ERROR_RECOVERY_VERSION = 1;
const ASSISTANT_ERROR_RETRY_LIMIT = 3;
const ASSISTANT_ERROR_RETRY_DELAYS_MS = Object.freeze([1500, 5000, 15000]);
const ASSISTANT_ERROR_KIND = "message_delivery_timeout";
const ASSISTANT_ERROR_MAX_IDENTITY = 500;
const ASSISTANT_ERROR_MAX_USER_TEXT = 12000;
let assistantErrorRecoveryMutation = Promise.resolve();

function normalizedAssistantErrorText(value) {
  return String(value || "").trim().replace(/\s+/g, " ");
}

function normalizeAssistantErrorPayload(message) {
  const kind = String(message?.kind || "");
  const userIdentity = String(message?.userIdentity || "").slice(0, ASSISTANT_ERROR_MAX_IDENTITY);
  const assistantIdentity = String(message?.assistantIdentity || "").slice(0, ASSISTANT_ERROR_MAX_IDENTITY);
  const userText = String(message?.userText || "").slice(0, ASSISTANT_ERROR_MAX_USER_TEXT);
  const signature = String(message?.signature || "").slice(0, 120);
  if (kind !== ASSISTANT_ERROR_KIND || !userIdentity || !userText || !signature) return null;
  return { kind, userIdentity, assistantIdentity, userText, signature };
}

function normalizeAssistantRetryContext(message) {
  const bindingRevision = Number(message?.bindingRevision);
  const generation = Number(message?.generation);
  if (!Number.isInteger(bindingRevision) || bindingRevision < 1) return null;
  if (!Number.isInteger(generation) || generation < 0) return null;
  return { bindingRevision, generation };
}

function assistantErrorConversationForSender(state, message, sender) {
  const conversation = conversationForSender(state, message, sender);
  if (!conversation) return { conversation: null, reason: "conversation_not_found" };
  if (!Number.isInteger(conversation.preferredTabId) || conversation.preferredTabId !== sender?.tab?.id) {
    return { conversation: null, reason: "assistant_error_wrong_tab" };
  }
  return { conversation, reason: null };
}

function bridgeOwnsAssistantError(conversation, payload) {
  if (!stateModel.isBoundConversation(conversation)) return false;
  const expected = normalizedAssistantErrorText(
    `${bindingEnvelope(conversation)} Hard binding is immutable for this wake.`
  );
  return normalizedAssistantErrorText(payload.userText).startsWith(expected);
}

function assistantErrorRecoveryKey(conversation, payload) {
  return protocol.fnv1a32(
    `${conversation.url}\n${conversation.bindingRevision}\n${payload.userIdentity}\n${payload.kind}`
  );
}

function normalizeAssistantErrorRecovery(raw) {
  const entries = {};
  const source = raw?.version === ASSISTANT_ERROR_RECOVERY_VERSION && raw.entries && typeof raw.entries === "object"
    ? raw.entries
    : {};
  for (const [chatId, value] of Object.entries(source).slice(0, 64)) {
    if (!/^chat-[0-9a-f]{8}$/.test(chatId)) continue;
    const key = String(value?.key || "").slice(0, 120);
    if (!key) continue;
    entries[chatId] = {
      key,
      attempts: Math.max(0, Math.min(ASSISTANT_ERROR_RETRY_LIMIT, Math.trunc(Number(value?.attempts) || 0))),
      updatedAt: String(value?.updatedAt || "").slice(0, 64)
    };
  }
  return { version: ASSISTANT_ERROR_RECOVERY_VERSION, entries };
}

async function readAssistantErrorRecovery() {
  const stored = await chrome.storage.local.get(ASSISTANT_ERROR_RECOVERY_STORAGE_KEY);
  return normalizeAssistantErrorRecovery(stored[ASSISTANT_ERROR_RECOVERY_STORAGE_KEY]);
}

function mutateAssistantErrorRecovery(mutator) {
  const run = async () => {
    const recovery = await readAssistantErrorRecovery();
    const result = await mutator(recovery);
    const next = normalizeAssistantErrorRecovery(result?.state || recovery);
    await chrome.storage.local.set({ [ASSISTANT_ERROR_RECOVERY_STORAGE_KEY]: next });
    return result?.value;
  };
  const next = assistantErrorRecoveryMutation.then(run, run);
  assistantErrorRecoveryMutation = next.then(() => undefined, () => undefined);
  return next;
}

function clearAssistantErrorRecovery(chatId) {
  return mutateAssistantErrorRecovery((recovery) => {
    const existed = Object.hasOwn(recovery.entries, chatId);
    delete recovery.entries[chatId];
    return { state: recovery, value: existed };
  });
}

async function assistantErrorAttemptSnapshot(conversation, payload) {
  const recovery = await readAssistantErrorRecovery();
  const entry = recovery.entries[conversation.id];
  const key = assistantErrorRecoveryKey(conversation, payload);
  return entry?.key === key ? entry.attempts : 0;
}

async function markAssistantRetryExhausted(conversation) {
  const bindingRevision = conversation.bindingRevision;
  const result = await mutateState((current) => {
    const latest = current.conversations[conversation.id];
    if (!latest || latest.url !== conversation.url || latest.bindingRevision !== bindingRevision) {
      return { state: current, value: null };
    }
    if (!latest.enabled && latest.lastStatus === "assistant_retry_exhausted") {
      return { state: current, value: latest.generation };
    }
    const disabledGeneration = latest.generation + 1;
    return {
      state: stateModel.patchConversation(current, conversation.id, {
        enabled: false,
        generation: disabledGeneration,
        lastStatus: "assistant_retry_exhausted",
        nextRunAt: null
      }).state,
      value: disabledGeneration
    };
  });
  if (result.value !== null) await clearConversationAlarm(conversation.id, result.value);
}

async function reportAssistantError(message, sender) {
  const payload = normalizeAssistantErrorPayload(message);
  if (!payload) return { ok: false, reason: "assistant_error_invalid" };
  const state = await getBridgeState();
  const resolved = assistantErrorConversationForSender(state, message, sender);
  if (!resolved.conversation) return { ok: false, reason: resolved.reason };
  const conversation = resolved.conversation;

  const bridgeOwned = bridgeOwnsAssistantError(conversation, payload);
  const attempts = bridgeOwned ? await assistantErrorAttemptSnapshot(conversation, payload) : 0;
  if (bridgeOwned && attempts >= ASSISTANT_ERROR_RETRY_LIMIT) {
    await markAssistantRetryExhausted(conversation);
    return {
      ok: true,
      reason: "assistant_retry_exhausted",
      bridgeOwned: true,
      retryEligible: false,
      attempts,
      retryLimit: ASSISTANT_ERROR_RETRY_LIMIT,
      bindingRevision: conversation.bindingRevision,
      generation: conversation.generation
    };
  }

  const status = bridgeOwned ? "assistant_delivery_timeout" : "assistant_delivery_timeout_unowned";
  await updateConversationStatus(conversation.id, { lastStatus: status }, conversation.generation);
  const retryEligible = Boolean(bridgeOwned && state.settings.masterEnabled && conversation.enabled);
  return {
    ok: true,
    reason: status,
    bridgeOwned,
    retryEligible,
    attempts,
    retryLimit: ASSISTANT_ERROR_RETRY_LIMIT,
    retryAfterMs: retryEligible ? ASSISTANT_ERROR_RETRY_DELAYS_MS[attempts] : null,
    bindingRevision: conversation.bindingRevision,
    generation: conversation.generation
  };
}

async function authorizeAssistantRetry(message, sender) {
  const payload = normalizeAssistantErrorPayload(message);
  if (!payload) return { ok: false, reason: "assistant_error_invalid" };
  const retryContext = normalizeAssistantRetryContext(message);
  if (!retryContext) return { ok: false, reason: "assistant_retry_context_invalid" };
  const state = await getBridgeState();
  const resolved = assistantErrorConversationForSender(state, message, sender);
  if (!resolved.conversation) return { ok: false, reason: resolved.reason };
  const conversation = resolved.conversation;
  if (
    conversation.bindingRevision !== retryContext.bindingRevision ||
    conversation.generation !== retryContext.generation
  ) {
    return { ok: false, reason: "assistant_retry_stale_context" };
  }
  if (!state.settings.masterEnabled || !conversation.enabled) {
    return { ok: false, reason: "assistant_retry_cancelled" };
  }
  if (!bridgeOwnsAssistantError(conversation, payload)) {
    return { ok: false, reason: "assistant_retry_not_bridge_owned" };
  }

  const key = assistantErrorRecoveryKey(conversation, payload);
  const attempt = await mutateAssistantErrorRecovery((recovery) => {
    const previous = recovery.entries[conversation.id];
    const attempts = previous?.key === key ? previous.attempts : 0;
    if (attempts >= ASSISTANT_ERROR_RETRY_LIMIT) {
      return { state: recovery, value: null };
    }
    const nextAttempt = attempts + 1;
    recovery.entries[conversation.id] = {
      key,
      attempts: nextAttempt,
      updatedAt: new Date().toISOString()
    };
    return { state: recovery, value: nextAttempt };
  });

  if (attempt === null) {
    await markAssistantRetryExhausted(conversation);
    return { ok: false, reason: "assistant_retry_exhausted", retryLimit: ASSISTANT_ERROR_RETRY_LIMIT };
  }

  await updateConversationStatus(
    conversation.id,
    { lastStatus: `assistant_retry_${attempt}` },
    conversation.generation
  );
  return {
    ok: true,
    reason: "assistant_retry_authorized",
    attempt,
    retryLimit: ASSISTANT_ERROR_RETRY_LIMIT
  };
}
