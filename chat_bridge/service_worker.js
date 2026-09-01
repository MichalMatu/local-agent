importScripts("control_protocol.js", "bridge_state.js");

const protocol = globalThis.LocalAgentBridgeProtocol;
const stateModel = globalThis.LocalAgentBridgeState;
const {
  MIN_INTERVAL_MINUTES,
  MAX_INTERVAL_MINUTES,
  normalizeConversationUrl,
  parseAssistantControl,
  conversationId
} = protocol;

const LEGACY_ALARM_NAME = "local-agent-chat-bridge";
const ALARM_PREFIX = "local-agent-chat:";
const RUNTIME_CACHE_MS = 30_000;
const RETRY_REASONS = new Set([
  "assistant_busy",
  "composer_not_empty",
  "composer_not_found",
  "content_script_unavailable",
  "send_button_not_ready",
  "page_not_ready"
]);

let stateQueue = Promise.resolve();
let runtimeCache = null;

function alarmName(chatId) {
  return `${ALARM_PREFIX}${chatId}`;
}

function clampNumber(value, fallback, minimum, maximum) {
  return stateModel.clampNumber(value, fallback, minimum, maximum);
}

async function loadStoredState() {
  const raw = await chrome.storage.local.get(null);
  const migrated = stateModel.migrateLegacyStorage(raw);
  if (migrated.migrated) {
    await chrome.storage.local.set({ bridgeState: migrated.state });
  }
  return migrated.state;
}

async function getBridgeState() {
  await stateQueue;
  return loadStoredState();
}

function mutateState(mutator) {
  const operation = stateQueue.then(async () => {
    const current = await loadStoredState();
    const result = await mutator(stateModel.normalizeState(current));
    const nextState = stateModel.normalizeState(result?.state || result || current);
    await chrome.storage.local.set({ bridgeState: nextState });
    return {
      state: nextState,
      value: result?.value,
      conversation: result?.conversation
    };
  });
  stateQueue = operation.catch(() => undefined);
  return operation;
}

function validatePrompt(value, fallback, maximum, label) {
  const prompt = String(value || fallback || "").trim();
  if (!prompt) throw new Error(`${label} must be a non-empty string`);
  if (prompt.length > maximum) throw new Error(`${label} exceeds ${maximum} characters`);
  return prompt;
}

function validateRuntimeConfig(raw, settings) {
  if (!raw || typeof raw !== "object" || ![1, 2].includes(raw.schema_version)) {
    throw new Error("runtime config must use schema_version=1 or schema_version=2");
  }

  const intervalMinutes = clampNumber(
    raw.interval_minutes,
    settings.fallbackIntervalMinutes,
    MIN_INTERVAL_MINUTES,
    MAX_INTERVAL_MINUTES
  );
  const busyRetryMinutes = clampNumber(
    raw.busy_retry_minutes,
    settings.fallbackBusyRetryMinutes,
    1,
    60
  );

  if (raw.schema_version === 1) {
    return {
      intervalMinutes,
      busyRetryMinutes,
      bootstrapPrompt: validatePrompt(
        raw.prompt,
        settings.fallbackBootstrapPrompt,
        8000,
        "runtime bootstrap prompt"
      ),
      wakePrompt: validatePrompt(
        settings.fallbackWakePrompt,
        stateModel.DEFAULT_WAKE_PROMPT,
        2000,
        "runtime wake prompt"
      )
    };
  }

  return {
    intervalMinutes,
    busyRetryMinutes,
    bootstrapPrompt: validatePrompt(
      raw.bootstrap_prompt,
      settings.fallbackBootstrapPrompt,
      8000,
      "runtime bootstrap prompt"
    ),
    wakePrompt: validatePrompt(
      raw.wake_prompt,
      settings.fallbackWakePrompt,
      2000,
      "runtime wake prompt"
    )
  };
}

function fallbackRuntime(settings) {
  return {
    intervalMinutes: clampNumber(
      settings.fallbackIntervalMinutes,
      10,
      MIN_INTERVAL_MINUTES,
      MAX_INTERVAL_MINUTES
    ),
    busyRetryMinutes: clampNumber(settings.fallbackBusyRetryMinutes, 1, 1, 60),
    bootstrapPrompt: validatePrompt(
      settings.fallbackBootstrapPrompt,
      stateModel.DEFAULT_BOOTSTRAP_PROMPT,
      8000,
      "fallback bootstrap prompt"
    ),
    wakePrompt: validatePrompt(
      settings.fallbackWakePrompt,
      stateModel.DEFAULT_WAKE_PROMPT,
      2000,
      "fallback wake prompt"
    )
  };
}

function applyConversationInterval(runtime, conversation) {
  if (!conversation || conversation.intervalOverrideMinutes === null) {
    return { ...runtime, intervalOverridden: false };
  }
  return {
    ...runtime,
    intervalMinutes: clampNumber(
      conversation.intervalOverrideMinutes,
      runtime.intervalMinutes,
      MIN_INTERVAL_MINUTES,
      MAX_INTERVAL_MINUTES
    ),
    intervalOverridden: true
  };
}

async function fetchRuntime(settings) {
  const fallback = fallbackRuntime(settings);
  const runtimeUrl = String(settings.runtimeUrl || "").trim();
  if (!runtimeUrl) return { ...fallback, source: "fallback" };

  if (
    runtimeCache &&
    runtimeCache.url === runtimeUrl &&
    runtimeCache.expiresAt > Date.now()
  ) {
    return runtimeCache.value;
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const separator = runtimeUrl.includes("?") ? "&" : "?";
    const response = await fetch(`${runtimeUrl}${separator}ts=${Date.now()}`, {
      cache: "no-store",
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`runtime fetch returned HTTP ${response.status}`);
    const raw = await response.json();
    const value = { ...validateRuntimeConfig(raw, settings), source: "remote" };
    runtimeCache = { url: runtimeUrl, expiresAt: Date.now() + RUNTIME_CACHE_MS, value };
    return value;
  } catch (error) {
    console.warn("Local Agent Chat Bridge runtime config fallback:", error);
    const value = { ...fallback, source: "fallback", runtimeError: String(error) };
    runtimeCache = { url: runtimeUrl, expiresAt: Date.now() + RUNTIME_CACHE_MS, value };
    return value;
  } finally {
    clearTimeout(timeout);
  }
}

async function loadRuntimeConfig(state, conversation = null) {
  const runtime = await fetchRuntime(state.settings);
  return applyConversationInterval(runtime, conversation);
}

function buildBootstrapPrompt(runtime, conversation) {
  const hints = [
    "Bridge v0.3 controls are conversation-scoped. Prefer short final-line controls: [LAB:STOP], [LAB:PAUSE], [LAB:RESUME], [LAB:NEXT=30s], [LAB:NEXT=10m], [LAB:INTERVAL=30m], [LAB:INTERVAL=AUTO]. NEXT changes only the next wake, not the normal interval."
  ];
  if (conversation.label) hints.push(`Bridge label: ${conversation.label}.`);
  if (conversation.repositoryId) {
    hints.push(`Configured Local Agent repository id: ${conversation.repositoryId}.`);
  }
  return `${runtime.bootstrapPrompt}\n${hints.join(" ")}`;
}

async function clearConversationAlarm(chatId) {
  await chrome.alarms.clear(alarmName(chatId));
  await mutateState((state) => {
    if (!state.conversations[chatId]) return state;
    return stateModel.patchConversation(state, chatId, { nextRunAt: null }).state;
  });
}

async function scheduleAt(chatId, when) {
  const state = await getBridgeState();
  const conversation = state.conversations[chatId];
  if (!conversation || !state.settings.masterEnabled || !conversation.enabled) {
    await clearConversationAlarm(chatId);
    return false;
  }
  const safeWhen = Math.max(Date.now() + 1000, Number(when));
  chrome.alarms.create(alarmName(chatId), { when: safeWhen });
  await mutateState((nextState) => {
    if (!nextState.conversations[chatId]) return nextState;
    return stateModel.patchConversation(nextState, chatId, {
      nextRunAt: new Date(safeWhen).toISOString()
    }).state;
  });
  return true;
}

async function scheduleAfterSeconds(chatId, seconds) {
  const delaySeconds = clampNumber(seconds, 600, protocol.MIN_NEXT_SECONDS, protocol.MAX_NEXT_SECONDS);
  return scheduleAt(chatId, Date.now() + delaySeconds * 1000);
}

async function scheduleAfterMinutes(chatId, minutes) {
  const delayMinutes = clampNumber(minutes, 10, MIN_INTERVAL_MINUTES, MAX_INTERVAL_MINUTES);
  return scheduleAt(chatId, Date.now() + delayMinutes * 60_000);
}

async function scheduleDefault(chatId, useBusyRetry = false) {
  const state = await getBridgeState();
  const conversation = state.conversations[chatId];
  if (!conversation) return false;
  const runtime = await loadRuntimeConfig(state, conversation);
  return scheduleAfterMinutes(
    chatId,
    useBusyRetry ? runtime.busyRetryMinutes : runtime.intervalMinutes
  );
}

async function reconcileSchedules() {
  await chrome.alarms.clear(LEGACY_ALARM_NAME);
  const state = await getBridgeState();
  const alarms = await chrome.alarms.getAll();
  const validAlarmNames = new Set(
    Object.keys(state.conversations).map((chatId) => alarmName(chatId))
  );
  await Promise.all(
    alarms
      .filter((alarm) => alarm.name.startsWith(ALARM_PREFIX) && !validAlarmNames.has(alarm.name))
      .map((alarm) => chrome.alarms.clear(alarm.name))
  );

  if (!state.settings.masterEnabled) {
    await Promise.all(Object.keys(state.conversations).map(clearConversationAlarm));
    return;
  }

  for (const conversation of Object.values(state.conversations)) {
    if (!conversation.enabled) {
      await clearConversationAlarm(conversation.id);
      continue;
    }
    const storedWhen = Date.parse(conversation.nextRunAt || "");
    if (Number.isFinite(storedWhen) && storedWhen > Date.now() + 1000) {
      chrome.alarms.create(alarmName(conversation.id), { when: storedWhen });
    } else {
      await scheduleDefault(conversation.id);
    }
  }
}

async function findConversationTab(conversation) {
  const tabs = await chrome.tabs.query({
    url: ["https://chatgpt.com/*", "https://chat.openai.com/*"]
  });
  const matches = tabs.filter(
    (tab) => normalizeConversationUrl(tab.url || "") === conversation.url
  );
  if (conversation.preferredTabId !== null) {
    const preferred = matches.find((tab) => tab.id === conversation.preferredTabId);
    if (preferred) return preferred;
  }
  return matches[0] || null;
}

async function updateConversationStatus(chatId, patch) {
  return mutateState((state) => {
    if (!state.conversations[chatId]) return state;
    return stateModel.patchConversation(state, chatId, patch).state;
  });
}

async function applyAssistantControl(message, sender) {
  const state = await getBridgeState();
  const senderUrl = normalizeConversationUrl(sender?.tab?.url || sender?.url || "");
  const declaredUrl = normalizeConversationUrl(message.conversationUrl || "");
  const conversation = stateModel.findConversationByUrl(state, declaredUrl);

  if (!conversation || !senderUrl || senderUrl !== conversation.url || declaredUrl !== conversation.url) {
    return { ok: false, reason: "control_wrong_conversation" };
  }

  const fingerprint = String(message.fingerprint || "");
  if (!/^[0-9a-f]{8}$/.test(fingerprint)) {
    return { ok: false, reason: "control_invalid_fingerprint" };
  }
  if (conversation.lastControlFingerprint === fingerprint) {
    return { ok: true, reason: "control_duplicate", duplicate: true };
  }

  const parsed = parseAssistantControl(String(message.control?.marker || ""));
  if (!parsed) return { ok: false, reason: "control_invalid_marker" };

  const controlAt = new Date().toISOString();
  const common = {
    lastControlFingerprint: fingerprint,
    lastControlAction: parsed.marker,
    lastControlAt: controlAt
  };

  if (parsed.action === "stop") {
    await updateConversationStatus(conversation.id, {
      ...common,
      enabled: false,
      intervalOverrideMinutes: null,
      lastStatus: "stopped_by_assistant",
      nextRunAt: null
    });
    await chrome.alarms.clear(alarmName(conversation.id));
    return { ok: true, reason: "stopped", conversationId: conversation.id };
  }

  if (parsed.action === "pause") {
    await updateConversationStatus(conversation.id, {
      ...common,
      enabled: false,
      lastStatus: "paused_by_assistant",
      nextRunAt: null
    });
    await chrome.alarms.clear(alarmName(conversation.id));
    return { ok: true, reason: "paused", conversationId: conversation.id };
  }

  if (parsed.action === "resume") {
    await updateConversationStatus(conversation.id, {
      ...common,
      enabled: true,
      lastStatus: "resumed_by_assistant"
    });
    const updated = await getBridgeState();
    if (updated.settings.masterEnabled) await scheduleDefault(conversation.id, true);
    return { ok: true, reason: "resumed", conversationId: conversation.id };
  }

  if (parsed.action === "interval" && parsed.mode === "auto") {
    await updateConversationStatus(conversation.id, {
      ...common,
      intervalOverrideMinutes: null,
      lastStatus: "interval_auto_by_assistant"
    });
    const updated = await getBridgeState();
    if (updated.settings.masterEnabled && updated.conversations[conversation.id]?.enabled) {
      await scheduleDefault(conversation.id);
    }
    return { ok: true, reason: "interval_auto", conversationId: conversation.id };
  }

  if (parsed.action === "interval" && parsed.mode === "fixed") {
    await updateConversationStatus(conversation.id, {
      ...common,
      intervalOverrideMinutes: parsed.minutes,
      lastStatus: `interval_${parsed.minutes}_by_assistant`
    });
    const updated = await getBridgeState();
    if (updated.settings.masterEnabled && updated.conversations[conversation.id]?.enabled) {
      await scheduleAfterMinutes(conversation.id, parsed.minutes);
    }
    return {
      ok: true,
      reason: "interval_fixed",
      minutes: parsed.minutes,
      conversationId: conversation.id
    };
  }

  if (parsed.action === "next") {
    await updateConversationStatus(conversation.id, {
      ...common,
      lastStatus: `next_${parsed.seconds}s_by_assistant`
    });
    const updated = await getBridgeState();
    if (updated.settings.masterEnabled && updated.conversations[conversation.id]?.enabled) {
      await scheduleAfterSeconds(conversation.id, parsed.seconds);
    }
    return {
      ok: true,
      reason: "next_scheduled",
      seconds: parsed.seconds,
      conversationId: conversation.id
    };
  }

  return { ok: false, reason: "control_unsupported" };
}

async function runFeedbackCycle({ conversationId: chatId, manual = false } = {}) {
  const state = await getBridgeState();
  const conversation = state.conversations[chatId];
  if (!conversation) return { ok: false, reason: "conversation_not_found" };

  if ((!state.settings.masterEnabled || !conversation.enabled) && !manual) {
    await clearConversationAlarm(chatId);
    return { ok: false, reason: "disabled" };
  }

  const runtime = await loadRuntimeConfig(state, conversation);
  const runAt = new Date().toISOString();
  const tab = await findConversationTab(conversation);

  if (!tab?.id) {
    await updateConversationStatus(chatId, {
      lastRunAt: runAt,
      lastStatus: "conversation_tab_missing",
      lastRuntimeSource: runtime.source
    });
    if (!manual) await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes);
    return { ok: false, reason: "conversation_tab_missing", runtime };
  }

  if (conversation.preferredTabId !== tab.id) {
    await updateConversationStatus(chatId, { preferredTabId: tab.id });
  }

  const prompt = conversation.bootstrapPending
    ? buildBootstrapPrompt(runtime, conversation)
    : runtime.wakePrompt;

  let response;
  try {
    response = await chrome.tabs.sendMessage(tab.id, {
      type: "bridge:feedback",
      prompt,
      expectedUrl: conversation.url,
      bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
    });
  } catch (error) {
    response = { ok: false, reason: "content_script_unavailable", error: String(error) };
  }

  const status = response?.ok ? "sent" : String(response?.reason || "unknown_failure");
  const patch = {
    lastRunAt: runAt,
    lastStatus: status,
    lastRuntimeSource: runtime.source
  };
  if (response?.ok && conversation.bootstrapPending) patch.bootstrapPending = false;
  await updateConversationStatus(chatId, patch);

  if (!manual) {
    await scheduleAfterMinutes(
      chatId,
      response?.ok || !RETRY_REASONS.has(status)
        ? runtime.intervalMinutes
        : runtime.busyRetryMinutes
    );
  }

  return {
    ...response,
    runtime,
    status,
    conversationId: chatId,
    bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
  };
}

async function saveGlobalSettings(patch) {
  runtimeCache = null;
  const result = await mutateState((state) => ({
    state: {
      ...state,
      settings: stateModel.sanitizeSettings({ ...state.settings, ...patch })
    }
  }));
  await reconcileSchedules();
  return result.state;
}

async function upsertConversation(patch) {
  const result = await mutateState((state) => {
    const url = normalizeConversationUrl(patch.url || "");
    if (!url) throw new Error("Open a concrete ChatGPT conversation first.");
    const id = conversationId(url);
    const previous = state.conversations[id];
    const repositoryChanged =
      previous && String(previous.repositoryId || "") !== String(patch.repositoryId || "");
    const upserted = stateModel.upsertConversation(state, {
      ...patch,
      url,
      bootstrapPending: previous ? previous.bootstrapPending || repositoryChanged : true
    });
    return { state: upserted.state, conversation: upserted.conversation };
  });
  if (result.conversation?.enabled) await scheduleDefault(result.conversation.id, true);
  return result.conversation;
}

async function updateConversation(chatId, patch) {
  const result = await mutateState((state) => {
    const previous = state.conversations[chatId];
    if (!previous) throw new Error("conversation not found");
    const safePatch = {};
    if ("enabled" in patch) safePatch.enabled = Boolean(patch.enabled);
    if ("label" in patch) safePatch.label = patch.label;
    if ("repositoryId" in patch) {
      safePatch.repositoryId = patch.repositoryId;
      if (String(previous.repositoryId || "") !== String(patch.repositoryId || "")) {
        safePatch.bootstrapPending = true;
      }
    }
    if ("intervalOverrideMinutes" in patch) {
      safePatch.intervalOverrideMinutes = patch.intervalOverrideMinutes;
    }
    const updated = stateModel.patchConversation(state, chatId, safePatch);
    return { state: updated.state, conversation: updated.conversation };
  });
  if (result.conversation?.enabled) await scheduleDefault(chatId, true);
  else await clearConversationAlarm(chatId);
  return result.conversation;
}

async function deleteConversation(chatId) {
  await chrome.alarms.clear(alarmName(chatId));
  const result = await mutateState((state) => stateModel.removeConversation(state, chatId));
  return result.state;
}

chrome.runtime.onInstalled.addListener(() => {
  reconcileSchedules().catch((error) => console.error(error));
});

chrome.runtime.onStartup.addListener(() => {
  reconcileSchedules().catch((error) => console.error(error));
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (!alarm.name.startsWith(ALARM_PREFIX)) return;
  const chatId = alarm.name.slice(ALARM_PREFIX.length);
  runFeedbackCycle({ conversationId: chatId }).catch(async (error) => {
    console.error(error);
    const state = await getBridgeState();
    const conversation = state.conversations[chatId];
    if (!conversation) return;
    const runtime = await loadRuntimeConfig(state, conversation);
    await updateConversationStatus(chatId, {
      lastRunAt: new Date().toISOString(),
      lastStatus: `worker_error:${String(error)}`,
      lastRuntimeSource: runtime.source
    });
    if (state.settings.masterEnabled && conversation.enabled) {
      await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes);
    }
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  if (message.type === "bridge:get-state") {
    (async () => {
      const state = await getBridgeState();
      const runtime = await loadRuntimeConfig(state);
      sendResponse({ state, runtime });
    })().catch((error) => sendResponse({ error: String(error) }));
    return true;
  }

  if (message.type === "bridge:save-global-settings") {
    saveGlobalSettings(message.settings || {})
      .then((state) => sendResponse({ ok: true, state }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "bridge:upsert-conversation") {
    upsertConversation(message.conversation || {})
      .then((conversation) => sendResponse({ ok: true, conversation }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "bridge:update-conversation") {
    updateConversation(String(message.conversationId || ""), message.patch || {})
      .then((conversation) => sendResponse({ ok: true, conversation }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "bridge:remove-conversation") {
    deleteConversation(String(message.conversationId || ""))
      .then(() => sendResponse({ ok: true }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "bridge:run-now") {
    runFeedbackCycle({
      conversationId: String(message.conversationId || ""),
      manual: true
    })
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "bridge:assistant-control") {
    applyAssistantControl(message, sender)
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  return false;
});
