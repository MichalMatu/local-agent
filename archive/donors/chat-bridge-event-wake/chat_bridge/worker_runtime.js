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
  return { repositoryId, repository, agentBinding, executionEnabled: raw.execution_enabled };
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
  return {
    intervalMinutes: clampNumber(
      raw.interval_minutes,
      settings.fallbackIntervalMinutes,
      MIN_INTERVAL_MINUTES,
      MAX_INTERVAL_MINUTES
    ),
    busyRetryMinutes: clampNumber(raw.busy_retry_minutes, settings.fallbackBusyRetryMinutes, 1, 60),
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
