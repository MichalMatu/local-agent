let runtimeFetchSequence = 0;
let runtimeCacheSequence = 0;

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
  const plannerScope = raw.planner_scope === undefined ? "repository" : String(raw.planner_scope).trim();
  if (!["repository", "multirepo"].includes(plannerScope)) {
    throw new Error("runtime planner_scope must be repository or multirepo");
  }
  if (plannerScope === "multirepo" && raw.execution_enabled === false) {
    throw new Error("runtime multirepo planner scope requires execution_enabled=true");
  }
  return {
    repositoryId,
    repository,
    agentBinding,
    executionEnabled: raw.execution_enabled,
    plannerScope
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
  const agents = validateRuntimeAgents(raw.agents);
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
    agents,
    conversationControls: githubControlModel.validateConversationControls(raw.conversation_controls, agents)
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
    agents: [],
    conversationControls: []
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

async function fetchRuntime(settings, { fresh = false } = {}) {
  const key = JSON.stringify(settings);
  if (!fresh && runtimeCache?.key === key && runtimeCache.expiresAt > Date.now()) return runtimeCache.value;
  if (!fresh && runtimeRequests.has(key)) return runtimeRequests.get(key);

  const sequence = ++runtimeFetchSequence;
  const request = fetchRuntimeUncached(settings, key, sequence);
  if (fresh) return request;

  runtimeRequests.set(key, request);
  try {
    return await request;
  } finally {
    if (runtimeRequests.get(key) === request) runtimeRequests.delete(key);
  }
}

function cacheRuntimeResult(key, sequence, value) {
  if (sequence < runtimeCacheSequence) return;
  runtimeCacheSequence = sequence;
  runtimeCache = { key, expiresAt: Date.now() + RUNTIME_CACHE_MS, value };
}

async function fetchRuntimeUncached(settings, key, sequence) {
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
    cacheRuntimeResult(key, sequence, value);
    return value;
  } catch (error) {
    console.warn("Local Agent Chat Bridge runtime unavailable:", error);
    const value = { ...fallback, source: "unavailable", runtimeError: String(error) };
    cacheRuntimeResult(key, sequence, value);
    return value;
  } finally {
    clearTimeout(timeout);
  }
}

async function loadRuntimeConfig(state, conversation = null) {
  return applyConversationInterval(await fetchRuntime(state.settings), conversation);
}
