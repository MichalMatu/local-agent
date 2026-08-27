importScripts("control_protocol.js");

const protocol = globalThis.LocalAgentBridgeProtocol;
const {
  MIN_INTERVAL_MINUTES,
  MAX_INTERVAL_MINUTES,
  normalizeConversationUrl,
  parseAssistantControl
} = protocol;

const ALARM_NAME = "local-agent-chat-bridge";
const DEFAULT_RUNTIME_URL =
  "https://raw.githubusercontent.com/MichalMatu/local-agent/chat-bridge-state/chat_bridge/runtime.json";

const LOCAL_DEFAULTS = Object.freeze({
  enabled: false,
  conversationUrl: "",
  runtimeUrl: DEFAULT_RUNTIME_URL,
  fallbackIntervalMinutes: 10,
  fallbackBusyRetryMinutes: 1,
  fallbackPrompt:
    "Check local-agent progress for the active autonomous goal in this conversation. Use the latest GitHub status and result evidence. If local-agent is still running a task, do not queue another task. If the previous task finished and local-agent is idle, analyze its result and continue with the next necessary task. If the autonomous goal is complete, end your response with [LOCAL_AGENT_BRIDGE:STOP]. If progress requires the user to perform a manual action before automation can continue, end your response with [LOCAL_AGENT_BRIDGE:PAUSE]. Otherwise do not emit a bridge control marker.",
  intervalOverrideMinutes: null,
  lastStatus: "disabled",
  lastRunAt: null,
  nextRunAt: null,
  lastRuntimeSource: "fallback",
  lastControlFingerprint: "",
  lastControlAction: "",
  lastControlAt: null
});

function clampNumber(value, fallback, minimum, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number)) return fallback;
  return Math.min(maximum, Math.max(minimum, number));
}

async function getLocalState() {
  const stored = await chrome.storage.local.get(LOCAL_DEFAULTS);
  return { ...LOCAL_DEFAULTS, ...stored };
}

async function setLocalState(patch) {
  await chrome.storage.local.set(patch);
}

function validateRuntimeConfig(raw, fallback) {
  if (!raw || typeof raw !== "object" || raw.schema_version !== 1) {
    throw new Error("runtime config must use schema_version=1");
  }
  const prompt = typeof raw.prompt === "string" ? raw.prompt.trim() : "";
  if (!prompt) throw new Error("runtime prompt must be a non-empty string");
  if (prompt.length > 8000) throw new Error("runtime prompt exceeds 8000 characters");

  return {
    intervalMinutes: clampNumber(
      raw.interval_minutes,
      fallback.fallbackIntervalMinutes,
      MIN_INTERVAL_MINUTES,
      MAX_INTERVAL_MINUTES
    ),
    busyRetryMinutes: clampNumber(
      raw.busy_retry_minutes,
      fallback.fallbackBusyRetryMinutes,
      1,
      60
    ),
    prompt
  };
}

function applyIntervalOverride(runtime, localState) {
  if (localState.intervalOverrideMinutes === null) {
    return { ...runtime, intervalOverridden: false };
  }
  const minutes = clampNumber(
    localState.intervalOverrideMinutes,
    runtime.intervalMinutes,
    MIN_INTERVAL_MINUTES,
    MAX_INTERVAL_MINUTES
  );
  return { ...runtime, intervalMinutes: minutes, intervalOverridden: true };
}

async function loadRuntimeConfig(localState) {
  const fallback = {
    intervalMinutes: clampNumber(
      localState.fallbackIntervalMinutes,
      10,
      MIN_INTERVAL_MINUTES,
      MAX_INTERVAL_MINUTES
    ),
    busyRetryMinutes: clampNumber(localState.fallbackBusyRetryMinutes, 1, 1, 60),
    prompt: String(localState.fallbackPrompt || LOCAL_DEFAULTS.fallbackPrompt).trim()
  };

  const runtimeUrl = String(localState.runtimeUrl || "").trim();
  if (!runtimeUrl) {
    return applyIntervalOverride({ ...fallback, source: "fallback" }, localState);
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const separator = runtimeUrl.includes("?") ? "&" : "?";
    const response = await fetch(`${runtimeUrl}${separator}ts=${Date.now()}`, {
      cache: "no-store",
      signal: controller.signal
    });
    if (!response.ok) {
      throw new Error(`runtime fetch returned HTTP ${response.status}`);
    }
    const raw = await response.json();
    return applyIntervalOverride(
      { ...validateRuntimeConfig(raw, localState), source: "remote" },
      localState
    );
  } catch (error) {
    console.warn("Local Agent Chat Bridge runtime config fallback:", error);
    return applyIntervalOverride(
      { ...fallback, source: "fallback", runtimeError: String(error) },
      localState
    );
  } finally {
    clearTimeout(timeout);
  }
}

async function clearAlarm() {
  await chrome.alarms.clear(ALARM_NAME);
  await setLocalState({ nextRunAt: null });
}

async function scheduleAfter(minutes) {
  const delayMinutes = clampNumber(
    minutes,
    10,
    MIN_INTERVAL_MINUTES,
    MAX_INTERVAL_MINUTES
  );
  const when = Date.now() + delayMinutes * 60_000;
  chrome.alarms.create(ALARM_NAME, { when });
  await setLocalState({ nextRunAt: new Date(when).toISOString() });
}

async function scheduleIfEnabled(delayMinutes = null) {
  const state = await getLocalState();
  if (!state.enabled) {
    await clearAlarm();
    return;
  }
  const runtime = await loadRuntimeConfig(state);
  await scheduleAfter(delayMinutes ?? runtime.intervalMinutes);
}

async function findConversationTab(conversationUrl) {
  const normalizedTarget = normalizeConversationUrl(conversationUrl);
  if (!normalizedTarget) return null;

  const tabs = await chrome.tabs.query({
    url: ["https://chatgpt.com/*", "https://chat.openai.com/*"]
  });
  return (
    tabs.find((tab) => normalizeConversationUrl(tab.url || "") === normalizedTarget) ||
    null
  );
}

async function applyAssistantControl(message, sender) {
  const state = await getLocalState();
  const targetUrl = normalizeConversationUrl(state.conversationUrl);
  const senderUrl = normalizeConversationUrl(sender?.tab?.url || sender?.url || "");
  const declaredUrl = normalizeConversationUrl(message.conversationUrl || "");

  if (!targetUrl || senderUrl !== targetUrl || declaredUrl !== targetUrl) {
    return { ok: false, reason: "control_wrong_conversation" };
  }

  const fingerprint = String(message.fingerprint || "");
  if (!/^[0-9a-f]{8}$/.test(fingerprint)) {
    return { ok: false, reason: "control_invalid_fingerprint" };
  }
  if (state.lastControlFingerprint === fingerprint) {
    return { ok: true, reason: "control_duplicate", duplicate: true };
  }

  const parsed = parseAssistantControl(String(message.control?.marker || ""));
  if (!parsed) {
    return { ok: false, reason: "control_invalid_marker" };
  }

  const controlAt = new Date().toISOString();
  const common = {
    lastControlFingerprint: fingerprint,
    lastControlAction: parsed.marker,
    lastControlAt: controlAt
  };

  if (parsed.action === "stop") {
    await setLocalState({
      ...common,
      enabled: false,
      intervalOverrideMinutes: null,
      lastStatus: "stopped_by_assistant"
    });
    await clearAlarm();
    return { ok: true, reason: "stopped" };
  }

  if (parsed.action === "pause") {
    await setLocalState({
      ...common,
      enabled: false,
      lastStatus: "paused_by_assistant"
    });
    await clearAlarm();
    return { ok: true, reason: "paused" };
  }

  if (parsed.action === "resume") {
    await setLocalState({
      ...common,
      enabled: true,
      lastStatus: "resumed_by_assistant"
    });
    const updated = await getLocalState();
    const runtime = await loadRuntimeConfig(updated);
    await scheduleAfter(runtime.busyRetryMinutes);
    return { ok: true, reason: "resumed" };
  }

  if (parsed.action === "interval" && parsed.mode === "auto") {
    await setLocalState({
      ...common,
      intervalOverrideMinutes: null,
      lastStatus: "interval_auto_by_assistant"
    });
    const updated = await getLocalState();
    if (updated.enabled) {
      const runtime = await loadRuntimeConfig(updated);
      await scheduleAfter(runtime.intervalMinutes);
    }
    return { ok: true, reason: "interval_auto" };
  }

  if (parsed.action === "interval" && parsed.mode === "fixed") {
    await setLocalState({
      ...common,
      intervalOverrideMinutes: parsed.minutes,
      lastStatus: `interval_${parsed.minutes}_by_assistant`
    });
    const updated = await getLocalState();
    if (updated.enabled) await scheduleAfter(parsed.minutes);
    return { ok: true, reason: "interval_fixed", minutes: parsed.minutes };
  }

  return { ok: false, reason: "control_unsupported" };
}

async function runFeedbackCycle({ manual = false } = {}) {
  const state = await getLocalState();
  if (!state.enabled && !manual) {
    await clearAlarm();
    return { ok: false, reason: "disabled" };
  }

  const runtime = await loadRuntimeConfig(state);
  const runAt = new Date().toISOString();
  const targetUrl = normalizeConversationUrl(state.conversationUrl);

  if (!targetUrl) {
    await setLocalState({
      lastRunAt: runAt,
      lastStatus: "conversation_not_configured",
      lastRuntimeSource: runtime.source
    });
    if (!manual) await scheduleAfter(runtime.intervalMinutes);
    return { ok: false, reason: "conversation_not_configured", runtime };
  }

  const tab = await findConversationTab(targetUrl);
  if (!tab?.id) {
    await setLocalState({
      lastRunAt: runAt,
      lastStatus: "conversation_tab_missing",
      lastRuntimeSource: runtime.source
    });
    if (!manual) await scheduleAfter(runtime.busyRetryMinutes);
    return { ok: false, reason: "conversation_tab_missing", runtime };
  }

  let response;
  try {
    response = await chrome.tabs.sendMessage(tab.id, {
      type: "bridge:feedback",
      prompt: runtime.prompt,
      expectedUrl: targetUrl
    });
  } catch (error) {
    response = { ok: false, reason: "content_script_unavailable", error: String(error) };
  }

  const status = response?.ok ? "sent" : String(response?.reason || "unknown_failure");
  await setLocalState({
    lastRunAt: runAt,
    lastStatus: status,
    lastRuntimeSource: runtime.source
  });

  if (!manual) {
    const retryReasons = new Set([
      "assistant_busy",
      "composer_not_empty",
      "composer_not_found",
      "content_script_unavailable",
      "send_button_not_ready"
    ]);
    await scheduleAfter(
      response?.ok || !retryReasons.has(status)
        ? runtime.intervalMinutes
        : runtime.busyRetryMinutes
    );
  }

  return { ...response, runtime, status };
}

chrome.runtime.onInstalled.addListener(async () => {
  const existing = await chrome.storage.local.get(null);
  const initial = {};
  for (const [key, value] of Object.entries(LOCAL_DEFAULTS)) {
    if (!(key in existing)) initial[key] = value;
  }
  if (Object.keys(initial).length) await chrome.storage.local.set(initial);
  await scheduleIfEnabled();
});

chrome.runtime.onStartup.addListener(() => {
  scheduleIfEnabled().catch((error) => console.error(error));
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name !== ALARM_NAME) return;
  runFeedbackCycle().catch(async (error) => {
    console.error(error);
    const state = await getLocalState();
    const runtime = await loadRuntimeConfig(state);
    await setLocalState({
      lastRunAt: new Date().toISOString(),
      lastStatus: `worker_error:${String(error)}`,
      lastRuntimeSource: runtime.source
    });
    if (state.enabled) await scheduleAfter(runtime.busyRetryMinutes);
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || typeof message !== "object") return false;

  if (message.type === "bridge:get-state") {
    (async () => {
      const state = await getLocalState();
      const runtime = await loadRuntimeConfig(state);
      sendResponse({ state, runtime });
    })().catch((error) => sendResponse({ error: String(error) }));
    return true;
  }

  if (message.type === "bridge:save-settings") {
    (async () => {
      const patch = message.settings || {};
      const safePatch = {
        enabled: Boolean(patch.enabled),
        conversationUrl: normalizeConversationUrl(patch.conversationUrl || ""),
        runtimeUrl: String(patch.runtimeUrl || DEFAULT_RUNTIME_URL).trim(),
        fallbackIntervalMinutes: clampNumber(
          patch.fallbackIntervalMinutes,
          10,
          MIN_INTERVAL_MINUTES,
          MAX_INTERVAL_MINUTES
        ),
        fallbackBusyRetryMinutes: clampNumber(patch.fallbackBusyRetryMinutes, 1, 1, 60),
        fallbackPrompt: String(patch.fallbackPrompt || LOCAL_DEFAULTS.fallbackPrompt).trim()
      };
      await setLocalState(safePatch);
      await scheduleIfEnabled();
      sendResponse({ ok: true });
    })().catch((error) => sendResponse({ ok: false, error: String(error) }));
    return true;
  }

  if (message.type === "bridge:run-now") {
    runFeedbackCycle({ manual: true })
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
