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
    const value = { ...validateRuntimeConfig(await response.json(), settings), source: "remote" };
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
  return applyConversationInterval(await fetchRuntime(state.settings), conversation);
}

function runtimeAgentForBinding(runtime, binding) {
  const canonical = stateModel.sanitizeAgentBinding(binding);
  return canonical ? runtime.agents.find((agent) => agent.agentBinding === canonical) || null : null;
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
        !stateModel.isBoundConversation(conversation)) {
      await chrome.alarms.clear(alarmName(chatId));
      return { state, value: false };
    }
    if (expectedGeneration !== null && conversation.generation !== expectedGeneration) {
      return { state, value: false };
    }
    const safeWhen = Math.max(Date.now() + 1000, Number(when));
    if (!Number.isFinite(safeWhen)) throw new Error("invalid alarm deadline");
    await chrome.alarms.create(alarmName(chatId), { when: safeWhen });
    return {
      state: stateModel.patchConversation(state, chatId, {
        nextRunAt: new Date(safeWhen).toISOString()
      }).state,
      value: true
    };
  });
  return result.value;
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
  const validAlarmNames = new Set(Object.keys(state.conversations).map((chatId) => alarmName(chatId)));
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

