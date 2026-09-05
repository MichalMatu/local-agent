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
const CONTENT_PROTOCOL_VERSION = 2;
const CONTENT_PREFLIGHT_TIMEOUT_MS = 1500;
const RETRY_REASONS = new Set([
  "assistant_busy",
  "composer_not_empty",
  "composer_not_found",
  "content_script_unavailable",
  "content_script_protocol_mismatch",
  "send_button_not_ready",
  "page_not_ready",
  "wrong_conversation"
]);

let stateQueue = Promise.resolve();
let runtimeCache = null;
const inFlightDeliveries = new Set();
const runtimeRequests = new Map();

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

async function getScheduleSnapshot(state) {
  const alarms = await chrome.alarms.getAll();
  const alarmByName = new Map(alarms.map((alarm) => [alarm.name, alarm]));
  return Object.fromEntries(
    Object.values(state.conversations).map((conversation) => {
      const alarm = alarmByName.get(alarmName(conversation.id));
      const rawWhen = alarm?.scheduledTime ?? alarm?.when;
      const when = Number(rawWhen);
      return [
        conversation.id,
        {
          scheduled: Number.isFinite(when),
          nextRunAt: Number.isFinite(when) ? new Date(when).toISOString() : null
        }
      ];
    })
  );
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

function sanitizeRuntimeAgent(raw) {
  if (!raw || typeof raw !== "object") throw new Error("runtime agent must be an object");
  const repositoryId = stateModel.sanitizeRepositoryId(raw.repository_id);
  const repository = stateModel.sanitizeRepository(raw.repository);
  const agentBinding = stateModel.sanitizeAgentBinding(raw.agent_binding);
  if (!repositoryId || !repository || !agentBinding) {
    throw new Error("runtime agent requires repository_id, repository, and canonical agent_binding");
  }
  if (typeof raw.execution_enabled !== "boolean") {
    throw new Error("runtime execution_enabled must be a boolean");
  }
  return {
    repositoryId,
    repository,
    agentBinding,
    executionEnabled: raw.execution_enabled
  };
}

function validateRuntimeAgents(rawAgents) {
  if (!Array.isArray(rawAgents) || rawAgents.length === 0) {
    throw new Error("runtime agents must be a non-empty list");
  }
  const agents = rawAgents.map(sanitizeRuntimeAgent);
  const ids = new Set();
  const repositories = new Set();
  const bindings = new Set();
  for (const agent of agents) {
    const id = agent.repositoryId.toLowerCase();
    const repository = agent.repository.toLowerCase();
    if (ids.has(id)) throw new Error(`duplicate runtime repository_id: ${agent.repositoryId}`);
    if (repositories.has(repository)) throw new Error(`duplicate runtime repository: ${agent.repository}`);
    if (bindings.has(agent.agentBinding)) throw new Error(`duplicate runtime agent_binding: ${agent.agentBinding}`);
    ids.add(id);
    repositories.add(repository);
    bindings.add(agent.agentBinding);
  }
  return agents;
}

function validateRuntimeConfig(raw, settings) {
  if (!raw || typeof raw !== "object" || raw.schema_version !== 3) {
    throw new Error("runtime config must use schema_version=3");
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
    ),
    agents: validateRuntimeAgents(raw.agents)
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
    ),
    agents: []
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
  const key = JSON.stringify(settings);
  if (runtimeCache?.key === key && runtimeCache.expiresAt > Date.now()) return runtimeCache.value;
  if (runtimeRequests.has(key)) return runtimeRequests.get(key);
  const request = fetchRuntimeUncached(settings, key);
  runtimeRequests.set(key, request);
  try {
    return await request;
  } finally {
    runtimeRequests.delete(key);
  }
}

async function fetchRuntimeUncached(settings, key) {
  const fallback = fallbackRuntime(settings);
  const runtimeUrl = String(settings.runtimeUrl || "").trim();

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
    runtimeCache = { key, expiresAt: Date.now() + RUNTIME_CACHE_MS, value };
    return value;
  } catch (error) {
    console.warn("Local Agent Chat Bridge runtime unavailable:", error);
    const value = { ...fallback, source: "unavailable", runtimeError: String(error) };
    runtimeCache = { key, expiresAt: Date.now() + RUNTIME_CACHE_MS, value };
    return value;
  } finally {
    clearTimeout(timeout);
  }
}

async function loadRuntimeConfig(state, conversation = null) {
  const runtime = await fetchRuntime(state.settings);
  return applyConversationInterval(runtime, conversation);
}

function runtimeAgentForBinding(runtime, binding) {
  const canonical = stateModel.sanitizeAgentBinding(binding);
  if (!canonical) return null;
  return runtime.agents.find((agent) => agent.agentBinding === canonical) || null;
}

function runtimeAgentForConversation(runtime, conversation) {
  if (!stateModel.isBoundConversation(conversation)) return null;
  const agent = runtimeAgentForBinding(runtime, conversation.agentBinding);
  if (!agent) return null;
  if (agent.repositoryId !== conversation.repositoryId) return null;
  if (agent.repository.toLowerCase() !== conversation.repository.toLowerCase()) return null;
  return agent;
}

function resolveBindingInput(runtime, raw = {}) {
  const requestedBinding = stateModel.sanitizeAgentBinding(raw.agentBinding);
  const requestedId = stateModel.sanitizeRepositoryId(raw.repositoryId);
  let agent = requestedBinding ? runtimeAgentForBinding(runtime, requestedBinding) : null;
  if (!agent && requestedId) {
    agent = runtime.agents.find((item) => item.repositoryId === requestedId) || null;
  }
  if (!agent) throw new Error("Select a valid Local Agent repository binding.");
  if (requestedBinding && requestedBinding !== agent.agentBinding) {
    throw new Error("agent binding does not match selected repository");
  }
  if (requestedId && requestedId !== agent.repositoryId) {
    throw new Error("repository id does not match selected agent binding");
  }
  return agent;
}

function bindingEnvelope(conversation) {
  return `[LA_AGENT=${conversation.agentBinding}] [LA_REPO=${conversation.repositoryId}] [LA_REPOSITORY=${conversation.repository}] [LA_CHAT=${conversation.id}]`;
}

function bindingPolicy(conversation, runtimeAgent) {
  const executionPolicy = runtimeAgent?.executionEnabled === false
    ? "This binding is bridge/operator-only; do not create Local Agent project task files for it."
    : `Every Local Agent task JSON created by this conversation MUST contain exactly \"agent_binding\": \"${conversation.agentBinding}\".`;
  return `${bindingEnvelope(conversation)}\nHard binding is immutable for this wake. Work only on repository ${conversation.repository} (${conversation.repositoryId}). Never infer, substitute, inspect, queue, cancel, or execute work for another repository. ${executionPolicy} If the active goal appears to require another repository, pause instead of rebinding or guessing.`;
}

function buildBootstrapPrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  return `${bindingPolicy(conversation, agent)}\n${runtime.bootstrapPrompt}\nBridge controls are conversation-scoped. Continue only the active goal of this conversation. Prefer short final-line controls: [LAB:STOP], [LAB:PAUSE], [LAB:RESUME], [LAB:NEXT=30s], [LAB:NEXT=10m], [LAB:INTERVAL=30m], [LAB:INTERVAL=AUTO]. NEXT arms or re-arms this conversation and changes only its next wake, not the normal interval or global master switch.`;
}

function buildWakePrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  return `${bindingPolicy(conversation, agent)}\n${runtime.wakePrompt}`;
}

async function clearConversationAlarm(chatId, expectedGeneration = null) {
  await mutateState(async (state) => {
    const conversation = state.conversations[chatId];
    if (expectedGeneration !== null && conversation?.generation !== expectedGeneration) return state;
    await chrome.alarms.clear(alarmName(chatId));
    if (!conversation) return state;
    return stateModel.patchConversation(state, chatId, { nextRunAt: null }).state;
  });
}

async function scheduleAt(chatId, when, expectedGeneration = null) {
  const result = await mutateState(async (state) => {
    const conversation = state.conversations[chatId];
    if (!conversation || !state.settings.masterEnabled || !conversation.enabled ||
        !stateModel.isBoundConversation(conversation) || conversation.pendingDelivery) {
      await chrome.alarms.clear(alarmName(chatId));
      return { state, value: false };
    }
    if (expectedGeneration !== null && conversation.generation !== expectedGeneration) {
      return { state, value: false };
    }
    const safeWhen = Math.max(Date.now() + 1000, Number(when));
    if (!Number.isFinite(safeWhen)) throw new Error("invalid alarm deadline");
    await chrome.alarms.create(alarmName(chatId), { when: safeWhen });
    return { state: stateModel.patchConversation(state, chatId, {
      nextRunAt: new Date(safeWhen).toISOString()
    }).state, value: true };
  });
  return result.value;
}

async function scheduleAfterSeconds(chatId, seconds) {
  const delaySeconds = clampNumber(seconds, 600, protocol.MIN_NEXT_SECONDS, protocol.MAX_NEXT_SECONDS);
  return scheduleAt(chatId, Date.now() + delaySeconds * 1000);
}

async function scheduleAfterMinutes(chatId, minutes, expectedGeneration = null) {
  const delayMinutes = clampNumber(minutes, 10, MIN_INTERVAL_MINUTES, MAX_INTERVAL_MINUTES);
  return scheduleAt(chatId, Date.now() + delayMinutes * 60_000, expectedGeneration);
}

async function scheduleDefault(chatId, useBusyRetry = false, expectedGeneration = null) {
  const state = await getBridgeState();
  const conversation = state.conversations[chatId];
  if (!conversation || (expectedGeneration !== null && conversation.generation !== expectedGeneration)) return false;
  const runtime = await loadRuntimeConfig(state, conversation);
  return scheduleAfterMinutes(
    chatId,
    useBusyRetry ? runtime.busyRetryMinutes : runtime.intervalMinutes,
    conversation.generation
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
    await Promise.all(Object.keys(state.conversations).map((id) => clearConversationAlarm(id)));
    return;
  }

  for (const conversation of Object.values(state.conversations)) {
    if (conversation.pendingDelivery && !inFlightDeliveries.has(conversation.id)) {
      await updateConversationStatus(conversation.id, { enabled: false, lastStatus: "delivery_uncertain" });
      await clearConversationAlarm(conversation.id);
      continue;
    }
    if (!conversation.enabled || !stateModel.isBoundConversation(conversation)) {
      await clearConversationAlarm(conversation.id);
      continue;
    }
    const storedWhen = Date.parse(conversation.nextRunAt || "");
    if (Number.isFinite(storedWhen) && storedWhen > Date.now() + 1000) {
      await scheduleAt(conversation.id, storedWhen, conversation.generation);
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

async function probeContentScript(tabId, expectedUrl) {
  const timeoutMarker = Symbol("content-script-preflight-timeout");
  let timeout;
  try {
    const response = await Promise.race([
      chrome.tabs.sendMessage(tabId, {
        type: "bridge:capabilities",
        expectedUrl,
        protocolVersion: CONTENT_PROTOCOL_VERSION
      }, { frameId: 0 }),
      new Promise((resolve) => {
        timeout = setTimeout(() => resolve(timeoutMarker), CONTENT_PREFLIGHT_TIMEOUT_MS);
      })
    ]);
    if (response === timeoutMarker) {
      return { ok: false, reason: "content_script_unavailable" };
    }
    if (response === undefined || response?.protocolVersion !== CONTENT_PROTOCOL_VERSION) {
      return { ok: false, reason: "content_script_protocol_mismatch" };
    }
    if (!response.ok) {
      return { ok: false, reason: String(response.reason || "content_script_unavailable") };
    }
    return { ok: true, reason: "ready", protocolVersion: CONTENT_PROTOCOL_VERSION };
  } catch (error) {
    return { ok: false, reason: "content_script_unavailable", error: String(error) };
  } finally {
    clearTimeout(timeout);
  }
}

async function ensureContentScript(tab, expectedUrl) {
  const first = await probeContentScript(tab.id, expectedUrl);
  if (first.ok || first.reason !== "content_script_unavailable") return first;

  try {
    await chrome.scripting.executeScript({
      target: { tabId: tab.id, frameIds: [0] },
      files: ["control_protocol.js", "content.js"]
    });
  } catch (error) {
    return { ok: false, reason: "content_script_unavailable", error: String(error) };
  }

  const second = await probeContentScript(tab.id, expectedUrl);
  return second.ok ? { ...second, injected: true } : second;
}

function definitelyNoContentReceiver(error) {
  const text = String(error?.message || error || "");
  return /receiving end does not exist|could not establish connection/i.test(text);
}

async function updateConversationStatus(chatId, patch) {
  return mutateState((state) => {
    if (!state.conversations[chatId]) return state;
    return stateModel.patchConversation(state, chatId, patch).state;
  });
}

function conversationForSender(state, message, sender) {
  if (sender?.id !== chrome.runtime.id || sender?.frameId !== 0 || !sender?.tab?.id) return null;
  const senderUrl = normalizeConversationUrl(sender.url || "");
  const declaredUrl = normalizeConversationUrl(message.conversationUrl || "");
  if (!senderUrl || senderUrl !== declaredUrl) return null;
  const conversation = state.conversations[conversationId(declaredUrl)];
  return conversation?.url === declaredUrl ? conversation : null;
}

async function authorizeDelivery(message, sender) {
  const result = await mutateState((state) => {
    const conversation = conversationForSender(state, message, sender);
    const pending = conversation?.pendingDelivery;
    if (!pending || pending.id !== message.deliveryId || pending.tabId !== sender.tab.id ||
        pending.phase !== "prepared" || pending.expiresAt < Date.now() ||
        pending.generation !== conversation.generation ||
        pending.bindingRevision !== conversation.bindingRevision ||
        (!pending.manual && (!conversation.enabled || !state.settings.masterEnabled))) {
      return { state, value: { ok: false, reason: "delivery_cancelled" } };
    }
    pending.phase = "authorized";
    pending.assistantBaseline = String(message.assistantBaseline || "").slice(0, 500);
    return { state, value: { ok: true } };
  });
  return result.value;
}

async function controlContext(message, sender) {
  const state = await getBridgeState();
  const conversation = conversationForSender(state, message, sender);
  if (!stateModel.isBoundConversation(conversation) || conversation.bootstrapPending || conversation.pendingDelivery) {
    return { ok: false, reason: "control_not_ready" };
  }
  return { ok: true, bindingRevision: conversation.bindingRevision, assistantBaseline: conversation.assistantBaseline };
}

async function resolveDelivery(chatId, wasSent) {
  if (typeof wasSent !== "boolean") throw new Error("Resolve delivery with an explicit sent/not-sent decision.");
  const result = await mutateState((state) => {
    const conversation = state.conversations[chatId];
    if (!conversation?.pendingDelivery || inFlightDeliveries.has(chatId)) {
      throw new Error("No uncertain delivery to resolve, or the send is still in progress.");
    }
    if (wasSent) {
      conversation.bootstrapPending = false;
      conversation.assistantBaseline = conversation.pendingDelivery.assistantBaseline || "";
    }
    conversation.pendingDelivery = null;
    conversation.enabled = false;
    conversation.generation += 1;
    conversation.lastStatus = wasSent ? "delivery_confirmed_by_operator" : "unsent_confirmed_by_operator";
    return { state, conversation };
  });
  await clearConversationAlarm(chatId);
  return result.conversation;
}

async function applyAssistantControl(message, sender) {
  const parsed = parseAssistantControl(String(message.control?.marker || ""));
  if (!parsed) return { ok: false, reason: "control_invalid_marker" };
  const fingerprint = String(message.fingerprint || "");
  if (!/^[0-9a-f]{8}$/.test(fingerprint)) return { ok: false, reason: "control_invalid_fingerprint" };
  const result = await mutateState((state) => {
    const conversation = conversationForSender(state, message, sender);
    if (!conversation) return { state, value: { ok: false, reason: "control_wrong_conversation" } };
    if (!stateModel.isBoundConversation(conversation)) return { state, value: { ok: false, reason: "control_unbound_conversation" } };
    if (message.bindingRevision !== conversation.bindingRevision || conversation.bootstrapPending ||
        (conversation.assistantBaseline && message.assistantIdentity === conversation.assistantBaseline)) {
      return { state, value: { ok: false, reason: "control_stale_binding" } };
    }
    if (conversation.pendingDelivery) return { state, value: { ok: false, reason: "control_not_ready" } };
    if (conversation.lastControlFingerprint === fingerprint) {
      return { state, value: { ok: true, reason: "control_duplicate", duplicate: true } };
    }
    Object.assign(conversation, {
      lastControlFingerprint: fingerprint, lastControlAction: parsed.marker,
      lastControlAt: new Date().toISOString(), generation: conversation.generation + 1
    });
    const value = { ok: true, conversationId: conversation.id, generation: conversation.generation };
    if (parsed.action === "stop" || parsed.action === "pause") {
      conversation.enabled = false;
      conversation.nextRunAt = null;
      if (parsed.action === "stop") conversation.intervalOverrideMinutes = null;
      conversation.lastStatus = parsed.action === "stop" ? "stopped_by_assistant" : "paused_by_assistant";
      value.reason = parsed.action === "stop" ? "stopped" : "paused";
    } else if (parsed.action === "resume") {
      conversation.enabled = true;
      conversation.lastStatus = "resumed_by_assistant";
      value.reason = "resumed";
    } else if (parsed.action === "interval") {
      conversation.intervalOverrideMinutes = parsed.mode === "auto" ? null : parsed.minutes;
      conversation.lastStatus = parsed.mode === "auto" ? "interval_auto_by_assistant" : `interval_${parsed.minutes}_by_assistant`;
      value.reason = parsed.mode === "auto" ? "interval_auto" : "interval_fixed";
      if (parsed.mode === "fixed") value.minutes = parsed.minutes;
    } else if (parsed.action === "next") {
      conversation.enabled = true;
      conversation.lastStatus = `next_${parsed.seconds}s_by_assistant`;
      value.reason = state.settings.masterEnabled ? "next_scheduled" : "next_armed_master_disabled";
      value.armed = true;
      value.seconds = parsed.seconds;
    }
    return { state, value };
  });
  const value = result.value;
  if (!value.ok || value.duplicate) return value;
  if (parsed.action === "stop" || parsed.action === "pause") {
    await clearConversationAlarm(value.conversationId, value.generation);
  } else if (parsed.action === "next") {
    await scheduleAt(value.conversationId, Date.now() + parsed.seconds * 1000, value.generation);
  } else {
    await scheduleDefault(value.conversationId, parsed.action === "resume", value.generation);
  }
  return value;
}

async function runFeedbackCycle({ conversationId: chatId, manual = false } = {}) {
  if (inFlightDeliveries.has(chatId)) return { ok: false, reason: "delivery_in_progress" };
  inFlightDeliveries.add(chatId);
  try {
    return await deliverConversation(chatId, manual);
  } finally {
    inFlightDeliveries.delete(chatId);
  }
}

async function deliverConversation(chatId, manual) {
  const state = await getBridgeState();
  const conversation = state.conversations[chatId];
  if (!conversation) return { ok: false, reason: "conversation_not_found" };
  if (conversation.pendingDelivery) {
    await updateConversationStatus(chatId, { enabled: false, lastStatus: "delivery_uncertain" });
    await clearConversationAlarm(chatId);
    return { ok: false, reason: "delivery_uncertain" };
  }

  if (!stateModel.isBoundConversation(conversation)) {
    await updateConversationStatus(chatId, {
      enabled: false,
      lastStatus: "binding_required",
      nextRunAt: null
    });
    await clearConversationAlarm(chatId);
    return { ok: false, reason: "conversation_unbound" };
  }

  if ((!state.settings.masterEnabled || !conversation.enabled) && !manual) {
    await clearConversationAlarm(chatId);
    return { ok: false, reason: "disabled" };
  }

  const runtime = await loadRuntimeConfig(state, conversation);
  if (runtime.source === "unavailable") {
    await updateConversationStatus(chatId, { lastStatus: "runtime_unavailable", lastRuntimeSource: runtime.source });
    if (!manual) await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes, conversation.generation);
    return { ok: false, reason: "runtime_unavailable", runtime };
  }
  const runtimeAgent = runtimeAgentForConversation(runtime, conversation);
  if (!runtimeAgent) {
    await updateConversationStatus(chatId, {
      enabled: false,
      lastStatus: "binding_catalog_mismatch",
      nextRunAt: null
    });
    await clearConversationAlarm(chatId);
    return { ok: false, reason: "binding_catalog_mismatch", runtime };
  }

  const runAt = new Date().toISOString();
  const tab = await findConversationTab(conversation);

  if (!tab?.id) {
    await updateConversationStatus(chatId, {
      lastRunAt: runAt,
      lastStatus: "conversation_tab_missing",
      lastRuntimeSource: runtime.source
    });
    if (!manual) await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes, conversation.generation);
    return { ok: false, reason: "conversation_tab_missing", runtime };
  }

  if (conversation.preferredTabId !== tab.id) {
    await updateConversationStatus(chatId, { preferredTabId: tab.id });
  }

  const contentReady = await ensureContentScript(tab, conversation.url);
  if (!contentReady.ok) {
    const status = String(contentReady.reason || "content_script_unavailable");
    await updateConversationStatus(chatId, {
      lastRunAt: runAt,
      lastStatus: status,
      lastRuntimeSource: runtime.source
    });
    if (!manual) {
      await scheduleAfterMinutes(
        chatId,
        RETRY_REASONS.has(status) ? runtime.busyRetryMinutes : runtime.intervalMinutes,
        conversation.generation
      );
    }
    return {
      ...contentReady,
      runtime,
      status,
      conversationId: chatId,
      agentBinding: conversation.agentBinding,
      repositoryId: conversation.repositoryId,
      repository: conversation.repository,
      bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
    };
  }

  const prompt = conversation.bootstrapPending
    ? buildBootstrapPrompt(runtime, conversation)
    : buildWakePrompt(runtime, conversation);

  const deliveryId = crypto.randomUUID();
  const prepared = await mutateState((current) => {
    const latest = current.conversations[chatId];
    if (!latest || latest.generation !== conversation.generation ||
        latest.bindingRevision !== conversation.bindingRevision || latest.pendingDelivery ||
        (!manual && (!latest.enabled || !current.settings.masterEnabled))) {
      return { state: current, value: false };
    }
    latest.pendingDelivery = {
      id: deliveryId, tabId: tab.id, generation: latest.generation,
      bindingRevision: latest.bindingRevision, manual,
      phase: "prepared", expiresAt: Date.now() + 10_000
    };
    return { state: current, value: true };
  });
  if (!prepared.value) return { ok: false, reason: "delivery_cancelled" };

  let response;
  let deliveryTimeout;
  try {
    response = await Promise.race([chrome.tabs.sendMessage(tab.id, {
      type: "bridge:feedback",
      prompt,
      expectedUrl: conversation.url,
      deliveryId,
      bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake",
      agentBinding: conversation.agentBinding,
      repositoryId: conversation.repositoryId,
      repository: conversation.repository
    }, { frameId: 0 }), new Promise((resolve) => {
      deliveryTimeout = setTimeout(() => resolve({ ok: false, reason: "delivery_uncertain" }), 8000);
    })]);
  } catch (error) {
    response = definitelyNoContentReceiver(error)
      ? {
          ok: false,
          reason: "content_script_unavailable",
          protocolVersion: CONTENT_PROTOCOL_VERSION,
          error: String(error)
        }
      : { ok: false, reason: "delivery_uncertain", error: String(error) };
  } finally {
    clearTimeout(deliveryTimeout);
  }

  if (response?.reason !== "content_script_unavailable" &&
      (response?.protocolVersion !== CONTENT_PROTOCOL_VERSION || response?.reason === "unexpected_error")) {
    response = { ok: false, reason: "delivery_uncertain" };
  }
  const status = response?.ok ? "sent" : String(response?.reason || "delivery_uncertain");
  await mutateState((current) => {
    const latest = current.conversations[chatId];
    if (!latest || latest.pendingDelivery?.id !== deliveryId) return current;
    if (status === "delivery_uncertain") {
      latest.enabled = false;
      latest.lastStatus = status;
      latest.nextRunAt = null;
    } else {
      if (response?.ok) {
        latest.bootstrapPending = false;
        latest.assistantBaseline = latest.pendingDelivery.assistantBaseline || "";
      }
      latest.pendingDelivery = null;
      if (latest.generation === conversation.generation) {
        latest.lastRunAt = runAt;
        latest.lastStatus = status;
        latest.lastRuntimeSource = runtime.source;
      }
    }
    return current;
  });
  if (status === "delivery_uncertain") await clearConversationAlarm(chatId);

  if (!manual && status !== "delivery_uncertain") {
    await scheduleAfterMinutes(
      chatId,
      response?.ok || !RETRY_REASONS.has(status)
        ? runtime.intervalMinutes
        : runtime.busyRetryMinutes,
      conversation.generation
    );
  }

  return {
    ...response,
    runtime,
    status,
    conversationId: chatId,
    agentBinding: conversation.agentBinding,
    repositoryId: conversation.repositoryId,
    repository: conversation.repository,
    bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
  };
}

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
    ? runtimeAgentForConversation(runtime, existing)
    : resolveBindingInput(runtime, patch);
  if (!agent) throw new Error("Existing conversation binding is invalid; use explicit Rebind.");

  const result = await mutateState((state) => {
    const previous = state.conversations[id];
    const currentAgent = previous ? runtimeAgentForConversation(runtime, previous) : agent;
    if (!currentAgent || (previous && previous.url !== url)) {
      throw new Error("Conversation identity changed during update; reopen the popup.");
    }
    const upserted = stateModel.upsertConversation(state, {
      label: patch.label, enabled: previous ? previous.enabled : patch.enabled,
      preferredTabId: patch.preferredTabId,
      url,
      repositoryId: currentAgent.repositoryId,
      repository: currentAgent.repository,
      agentBinding: currentAgent.agentBinding,
      bindingRevision: previous?.bindingRevision || 1,
      bindingSetAt: previous?.bindingSetAt || new Date().toISOString(),
      bootstrapPending: previous ? previous.bootstrapPending : true
    });
    if (!stateModel.isBoundConversation(upserted.conversation)) {
      throw new Error("conversation binding is required");
    }
    return { state: upserted.state, conversation: upserted.conversation };
  });
  if (result.conversation?.enabled) await scheduleDefault(result.conversation.id, true);
  return result.conversation;
}

async function rebindConversation(chatId, patch) {
  const state = await getBridgeState();
  const previous = state.conversations[chatId];
  if (!previous) throw new Error("conversation not found");
  const runtime = await loadRuntimeConfig(state, previous);
  const agent = resolveBindingInput(runtime, patch);
  const result = await mutateState((nextState) => {
    const current = nextState.conversations[chatId];
    if (!current) throw new Error("conversation not found");
    if (inFlightDeliveries.has(chatId) || current.pendingDelivery) {
      throw new Error("Resolve the in-progress wake before rebinding this conversation.");
    }
    const updated = stateModel.patchConversation(nextState, chatId, {
      repositoryId: agent.repositoryId,
      repository: agent.repository,
      agentBinding: agent.agentBinding,
      bindingRevision: Math.max(0, current.bindingRevision || 0) + 1,
      bindingSetAt: new Date().toISOString(),
      generation: current.generation + 1,
      assistantBaseline: "",
      bootstrapPending: true,
      lastControlFingerprint: "",
      lastControlAction: "",
      lastControlAt: null,
      lastStatus: "rebound_by_operator",
      enabled: true
    });
    return { state: updated.state, conversation: updated.conversation };
  });
  await scheduleDefault(chatId, true);
  return result.conversation;
}

async function updateConversation(chatId, patch) {
  const result = await mutateState((state) => {
    const previous = state.conversations[chatId];
    if (!previous) throw new Error("conversation not found");
    const safePatch = {};
    const previousInterval = previous.intervalOverrideMinutes;
    const previousEnabled = previous.enabled;

    if ("enabled" in patch) safePatch.enabled = Boolean(patch.enabled);
    if ("label" in patch) safePatch.label = patch.label;
    if ("intervalOverrideMinutes" in patch) {
      safePatch.intervalOverrideMinutes = patch.intervalOverrideMinutes;
    }

    if (safePatch.enabled && !stateModel.isBoundConversation(previous)) {
      throw new Error("conversation must be explicitly bound before it can be enabled");
    }
    if (safePatch.enabled && previous.pendingDelivery) {
      throw new Error("Resolve uncertain wake delivery before enabling this conversation.");
    }
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
    await clearConversationAlarm(chatId);
  } else if (result.value?.enabledChanged) {
    await scheduleDefault(chatId, true);
  } else if (result.value?.pacingChanged) {
    await scheduleDefault(chatId);
  }
  return result.conversation;
}

async function deleteConversation(chatId) {
  const result = await mutateState(async (state) => {
    if (inFlightDeliveries.has(chatId) || state.conversations[chatId]?.pendingDelivery) {
      throw new Error("Resolve the in-progress wake before removing this conversation.");
    }
    await chrome.alarms.clear(alarmName(chatId));
    return stateModel.removeConversation(state, chatId);
  });
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
    if (state.settings.masterEnabled && conversation.enabled && stateModel.isBoundConversation(conversation)) {
      await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes);
    }
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  const contentHandlers = {
    "bridge:authorize-delivery": authorizeDelivery,
    "bridge:control-context": controlContext,
    "bridge:assistant-control": applyAssistantControl
  };
  if (Object.hasOwn(contentHandlers, message.type)) {
    contentHandlers[message.type](message, sender).then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  if (sender?.id !== chrome.runtime.id || sender?.url !== chrome.runtime.getURL("popup.html")) {
    sendResponse({ ok: false, reason: "operator_ui_required" });
    return false;
  }

  if (message.type === "bridge:resolve-delivery") {
    resolveDelivery(String(message.conversationId || ""), message.wasSent)
      .then((conversation) => sendResponse({ ok: true, conversation }))
      .catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "bridge:get-state") {
    (async () => {
      const state = await getBridgeState();
      const [runtime, schedules] = await Promise.all([
        loadRuntimeConfig(state),
        getScheduleSnapshot(state)
      ]);
      sendResponse({ state, runtime, schedules });
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

  if (message.type === "bridge:rebind-conversation") {
    rebindConversation(String(message.conversationId || ""), message.binding || {})
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

  return false;
});