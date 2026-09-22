const ASSISTANT_TRANSIENT_RECOVERY_STORAGE_KEY = "bridgeAssistantTransientRecovery";
const ASSISTANT_TRANSIENT_RECOVERY_VERSION = 1;
const ASSISTANT_CONNECTION_CONTINUE_AFTER_MS = 45_000;
const ASSISTANT_CONNECTION_RELOAD_AFTER_MS = 120_000;
const ASSISTANT_CONNECTION_RELOAD_AFTER_CONTINUE_MS = 60_000;
const ASSISTANT_TRANSIENT_CONTINUE_PROMPT = "Continue.";
let assistantTransientRecoveryMutation = Promise.resolve();

function normalizeAssistantTransientRecovery(raw) {
  const entries = {};
  const source = raw?.version === ASSISTANT_TRANSIENT_RECOVERY_VERSION && raw.entries && typeof raw.entries === "object"
    ? raw.entries
    : {};
  for (const [chatId, value] of Object.entries(source).slice(0, 64)) {
    if (!/^chat-[0-9a-f]{8}$/.test(chatId)) continue;
    const key = String(value?.key || "").slice(0, 120);
    const kind = String(value?.kind || "").slice(0, 64);
    const signature = String(value?.signature || "").slice(0, 120);
    if (!key || !kind || !signature) continue;
    entries[chatId] = {
      key,
      kind,
      signature,
      firstSeenAt: String(value?.firstSeenAt || "").slice(0, 64),
      continueSentAt: String(value?.continueSentAt || "").slice(0, 64),
      reloadReservedAt: String(value?.reloadReservedAt || "").slice(0, 64)
    };
  }
  return { version: ASSISTANT_TRANSIENT_RECOVERY_VERSION, entries };
}

async function readAssistantTransientRecovery() {
  const stored = await chrome.storage.local.get(ASSISTANT_TRANSIENT_RECOVERY_STORAGE_KEY);
  return normalizeAssistantTransientRecovery(stored[ASSISTANT_TRANSIENT_RECOVERY_STORAGE_KEY]);
}

function mutateAssistantTransientRecovery(mutator) {
  const run = async () => {
    const recovery = await readAssistantTransientRecovery();
    const result = await mutator(recovery);
    const next = normalizeAssistantTransientRecovery(result?.state || recovery);
    await chrome.storage.local.set({ [ASSISTANT_TRANSIENT_RECOVERY_STORAGE_KEY]: next });
    return result?.value;
  };
  const next = assistantTransientRecoveryMutation.then(run, run);
  assistantTransientRecoveryMutation = next.then(() => undefined, () => undefined);
  return next;
}

function clearAssistantTransientRecovery(chatId) {
  return mutateAssistantTransientRecovery((recovery) => {
    const existed = Object.hasOwn(recovery.entries, chatId);
    delete recovery.entries[chatId];
    return { state: recovery, value: existed };
  });
}

function assistantTransientRecoveryKey(conversation, kind, signature) {
  return protocol.fnv1a32(
    `${conversation.url}\n${conversation.bindingRevision}\n${conversation.generation}\n${kind}\n${signature}`
  );
}

function normalizedAssistantTransientText(value) {
  return String(value || "").trim().replace(/\s+/g, " ");
}

function assistantTransientAgeMs(entry, field) {
  const timestamp = Date.parse(String(entry?.[field] || ""));
  return Number.isFinite(timestamp) ? Math.max(0, Date.now() - timestamp) : Number.POSITIVE_INFINITY;
}

function bridgeOwnsAssistantTransient(conversation, contentReady, entry) {
  const userIdentity = String(contentReady.assistantTransientUserIdentity || "");
  const userText = normalizedAssistantTransientText(contentReady.assistantTransientUserText);
  if (!userIdentity || !userText || !contentReady.assistantTransientSignature) return false;
  const expected = normalizedAssistantTransientText(
    `${bindingEnvelope(conversation)} Hard binding is immutable for this wake.`
  );
  if (userText.startsWith(expected)) return true;
  return Boolean(entry?.continueSentAt && userText === ASSISTANT_TRANSIENT_CONTINUE_PROMPT);
}

function observeAssistantTransient(conversation, contentReady) {
  const kind = String(contentReady.assistantTransientState || "");
  const signature = String(contentReady.assistantTransientSignature || "").slice(0, 120);
  const key = assistantTransientRecoveryKey(conversation, kind, signature);
  const userText = normalizedAssistantTransientText(contentReady.assistantTransientUserText);
  return mutateAssistantTransientRecovery((recovery) => {
    const previous = recovery.entries[conversation.id];
    const sameKey = previous?.key === key;
    const continuationOfPrevious = Boolean(
      previous &&
      previous.kind === "connection_interrupted" &&
      kind === "connection_interrupted" &&
      previous.continueSentAt &&
      userText === ASSISTANT_TRANSIENT_CONTINUE_PROMPT
    );
    const reservedReloadEpisode = Boolean(
      previous && previous.kind === kind && previous.reloadReservedAt
    );
    const isNew = !previous || (!sameKey && !continuationOfPrevious && !reservedReloadEpisode);
    const entry = isNew
      ? {
          key,
          kind,
          signature,
          firstSeenAt: new Date().toISOString(),
          continueSentAt: "",
          reloadReservedAt: ""
        }
      : previous;
    recovery.entries[conversation.id] = entry;
    return { state: recovery, value: { key: entry.key, isNew, entry: { ...entry } } };
  });
}

function markAssistantTransientContinueSent(chatId, key) {
  return mutateAssistantTransientRecovery((recovery) => {
    const entry = recovery.entries[chatId];
    if (!entry || entry.key !== key) return { state: recovery, value: false };
    if (!entry.continueSentAt) entry.continueSentAt = new Date().toISOString();
    return { state: recovery, value: true };
  });
}

function reserveAssistantTransientReload(chatId, key) {
  return mutateAssistantTransientRecovery((recovery) => {
    const entry = recovery.entries[chatId];
    if (!entry || entry.key !== key || entry.reloadReservedAt) {
      return { state: recovery, value: false };
    }
    entry.reloadReservedAt = new Date().toISOString();
    return { state: recovery, value: true };
  });
}

async function sendAssistantTransientContinue(conversation, tab) {
  const deliveryId = crypto.randomUUID();
  const active = {
    id: deliveryId,
    tabId: tab.id,
    generation: conversation.generation,
    bindingRevision: conversation.bindingRevision,
    manual: false,
    assistantBaseline: ""
  };
  activeDeliveries.set(conversation.id, active);
  let deliveryTimeout;
  try {
    const response = await Promise.race([
      chrome.tabs.sendMessage(tab.id, {
        type: "bridge:feedback",
        prompt: ASSISTANT_TRANSIENT_CONTINUE_PROMPT,
        expectedUrl: conversation.url,
        deliveryId,
        recoverBridgePrompt: false,
        bridgeMode: "recovery",
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
    if (response?.protocolVersion !== CONTENT_PROTOCOL_VERSION) {
      return {
        ok: false,
        reason: "content_script_protocol_mismatch",
        protocolVersion: response?.protocolVersion
      };
    }
    return response || {
      ok: false,
      reason: "delivery_unconfirmed",
      protocolVersion: CONTENT_PROTOCOL_VERSION
    };
  } catch (error) {
    return definitelyNoContentReceiver(error)
      ? {
          ok: false,
          reason: "content_script_unavailable",
          protocolVersion: CONTENT_PROTOCOL_VERSION,
          error: String(error)
        }
      : {
          ok: false,
          reason: "delivery_unconfirmed",
          protocolVersion: CONTENT_PROTOCOL_VERSION,
          error: String(error)
        };
  } finally {
    clearTimeout(deliveryTimeout);
    if (activeDeliveries.get(conversation.id)?.id === deliveryId) {
      activeDeliveries.delete(conversation.id);
    }
  }
}

async function reloadAssistantTabAtomic(conversation, tab, key, kind) {
  const reserved = await reserveAssistantTransientReload(conversation.id, key);
  if (!reserved) {
    return {
      ok: false,
      reason: kind === "stalled" ? "assistant_stalled_after_reload" : "assistant_connection_reload_exhausted",
      action: "none"
    };
  }
  try {
    await chrome.tabs.reload(tab.id);
    return { ok: false, reason: "assistant_tab_reloaded", action: "reload" };
  } catch (error) {
    return {
      ok: false,
      reason: "assistant_tab_reload_failed",
      action: "reload",
      error: String(error)
    };
  }
}

async function recoverAssistantTransient(conversation, tab, contentReady) {
  const kind = String(contentReady.assistantTransientState || "");
  if (!["connection_interrupted", "stalled"].includes(kind)) return null;
  if (!contentReady.assistantTransientSignature) {
    return { ok: false, reason: "assistant_transient_invalid", action: "none" };
  }

  const observation = await observeAssistantTransient(conversation, contentReady);
  const { key, entry } = observation;

  if (contentReady.composerOccupied) {
    return { ok: false, reason: "composer_not_empty", action: "wait" };
  }

  if (kind === "stalled") {
    if (!bridgeOwnsAssistantTransient(conversation, contentReady, entry)) {
      return { ok: false, reason: "assistant_stalled_unowned", action: "none" };
    }
    if (entry.reloadReservedAt) {
      return { ok: false, reason: "assistant_stalled_after_reload", action: "none" };
    }
    return reloadAssistantTabAtomic(conversation, tab, key, kind);
  }

  if (entry.reloadReservedAt) {
    return { ok: false, reason: "assistant_connection_reload_exhausted", action: "none" };
  }

  const firstSeenAgeMs = assistantTransientAgeMs(entry, "firstSeenAt");
  if (!entry.continueSentAt && firstSeenAgeMs < ASSISTANT_CONNECTION_CONTINUE_AFTER_MS) {
    return { ok: false, reason: "assistant_connection_interrupted", action: "wait" };
  }

  if (!bridgeOwnsAssistantTransient(conversation, contentReady, entry)) {
    return { ok: false, reason: "assistant_connection_interrupted_unowned", action: "none" };
  }

  if (!entry.continueSentAt) {
    if (!contentReady.assistantGenerating) {
      const continuation = await sendAssistantTransientContinue(conversation, tab);
      if (continuation?.ok || continuation?.reason === "delivery_unconfirmed") {
        await markAssistantTransientContinueSent(conversation.id, key);
        return {
          ok: false,
          reason: continuation?.ok ? "assistant_connection_continue_sent" : "assistant_connection_continue_pending",
          action: "continue",
          recovery: continuation
        };
      }
      if (continuation?.reason === "composer_not_empty") {
        return { ok: false, reason: "composer_not_empty", action: "wait", recovery: continuation };
      }
      if (firstSeenAgeMs < ASSISTANT_CONNECTION_RELOAD_AFTER_MS) {
        return {
          ok: false,
          reason: "assistant_connection_continue_pending",
          action: "wait",
          recovery: continuation
        };
      }
    } else if (firstSeenAgeMs < ASSISTANT_CONNECTION_RELOAD_AFTER_MS) {
      return { ok: false, reason: "assistant_connection_continue_pending", action: "wait" };
    }

    return reloadAssistantTabAtomic(conversation, tab, key, kind);
  }

  if (assistantTransientAgeMs(entry, "continueSentAt") < ASSISTANT_CONNECTION_RELOAD_AFTER_CONTINUE_MS) {
    return { ok: false, reason: "assistant_connection_continue_sent", action: "wait" };
  }
  return reloadAssistantTabAtomic(conversation, tab, key, kind);
}
