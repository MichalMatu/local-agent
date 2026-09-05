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
const CONTENT_PROTOCOL_VERSION = 3;
const CONTENT_PREFLIGHT_TIMEOUT_MS = 1500;
const DELIVERY_TIMEOUT_MS = 8000;
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
const runtimeRequests = new Map();
const inFlightDeliveries = new Set();
const activeDeliveries = new Map();

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
      const when = Number(alarm?.scheduledTime ?? alarm?.when);
      return [conversation.id, {
        scheduled: Number.isFinite(when),
        nextRunAt: Number.isFinite(when) ? new Date(when).toISOString() : null
      }];
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

