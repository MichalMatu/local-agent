async function findConversationTab(conversation) {
  const tabs = await chrome.tabs.query({ url: ["https://chatgpt.com/*", "https://chat.openai.com/*"] });
  const matches = tabs.filter((tab) => normalizeConversationUrl(tab.url || "") === conversation.url);
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
    if (response === timeoutMarker) return { ok: false, reason: "content_script_unavailable" };
    if (response === undefined || response?.protocolVersion !== CONTENT_PROTOCOL_VERSION) {
      return { ok: false, reason: "content_script_protocol_mismatch" };
    }
    if (!response.ok) {
      return { ok: false, reason: String(response.reason || "content_script_unavailable") };
    }
    return {
      ok: true,
      reason: "ready",
      protocolVersion: CONTENT_PROTOCOL_VERSION,
      assistantIdentity: String(response.assistantIdentity || "")
    };
  } catch (error) {
    return { ok: false, reason: "content_script_unavailable", error: String(error) };
  } finally {
    clearTimeout(timeout);
  }
}

async function probeExhaustionGuard(tabId, expectedUrl) {
  let timeout;
  const timeoutMarker = Symbol("exhaustion-guard-preflight-timeout");
  try {
    const response = await Promise.race([
      chrome.tabs.sendMessage(tabId, {
        type: "bridge:exhaustion-capabilities",
        expectedUrl,
        guardVersion: EXHAUSTION_GUARD_VERSION
      }, { frameId: 0 }),
      new Promise((resolve) => {
        timeout = setTimeout(() => resolve(timeoutMarker), CONTENT_PREFLIGHT_TIMEOUT_MS);
      })
    ]);
    if (response === timeoutMarker || response?.guardVersion !== EXHAUSTION_GUARD_VERSION) {
      return { ok: false, reason: "exhaustion_guard_unavailable" };
    }
    return response?.ok
      ? { ok: true, reason: "ready", guardVersion: EXHAUSTION_GUARD_VERSION }
      : { ok: false, reason: String(response?.reason || "exhaustion_guard_unavailable") };
  } catch (_error) {
    return { ok: false, reason: "exhaustion_guard_unavailable" };
  } finally {
    clearTimeout(timeout);
  }
}

async function ensureContentScript(tab, expectedUrl) {
  let content = await probeContentScript(tab.id, expectedUrl);
  if (
    !content.ok &&
    (content.reason === "content_script_unavailable" || content.reason === "content_script_protocol_mismatch")
  ) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: [0] },
        files: ["control_protocol.js", "content_retry.js", "content.js"]
      });
    } catch (error) {
      return { ok: false, reason: "content_script_unavailable", error: String(error) };
    }
    content = await probeContentScript(tab.id, expectedUrl);
  }
  if (!content.ok) return content;

  let guard = await probeExhaustionGuard(tab.id, expectedUrl);
  if (!guard.ok && guard.reason === "exhaustion_guard_unavailable") {
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: [0] },
        files: ["control_protocol.js", "dom_contract.js", "exhaustion_guard.js"]
      });
    } catch (error) {
      return { ok: false, reason: "exhaustion_guard_unavailable", error: String(error) };
    }
    guard = await probeExhaustionGuard(tab.id, expectedUrl);
  }
  if (!guard.ok) return guard;
  return { ...content, exhaustionGuardVersion: guard.guardVersion };
}

function contentProbeReason(result) {
  return result?.ok ? "ready" : String(result?.reason || "content_script_unavailable");
}

async function refreshConfiguredContentScripts() {
  const state = await getBridgeState();
  const configured = Object.values(state.conversations || {}).filter((conversation) =>
    stateModel.isBoundConversation(conversation)
  );
  if (!configured.length) return { checked: 0, ready: 0, refreshed: 0, failed: 0 };

  const tabs = await chrome.tabs.query({ url: ["https://chatgpt.com/*", "https://chat.openai.com/*"] });
  const tabsByUrl = new Map();
  for (const tab of tabs) {
    const url = normalizeConversationUrl(tab.url || "");
    if (!tab.id || !url) continue;
    const matches = tabsByUrl.get(url) || [];
    matches.push(tab);
    tabsByUrl.set(url, matches);
  }

  let checked = 0;
  let ready = 0;
  let refreshed = 0;
  let failed = 0;
  for (const conversation of configured) {
    const matches = tabsByUrl.get(conversation.url) || [];
    const preferred = conversation.preferredTabId !== null
      ? matches.find((tab) => tab.id === conversation.preferredTabId)
      : null;
    const tab = preferred || matches[0] || null;
    if (!tab?.id) continue;

    checked += 1;
    const before = contentProbeReason(await probeContentScript(tab.id, conversation.url));
    if (before === "ready") {
      ready += 1;
      continue;
    }
    if (!["content_script_unavailable", "content_script_protocol_mismatch"].includes(before)) {
      failed += 1;
      continue;
    }
    const result = await ensureContentScript(tab, conversation.url);
    if (result.ok) refreshed += 1;
    else failed += 1;
  }
  return { checked, ready, refreshed, failed };
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

async function reportConversationExhausted(message, sender) {
  const state = await getBridgeState();
  const conversation = conversationForSender(state, message, sender);
  if (!conversation) return { ok: false, reason: "conversation_not_found" };
  const generation = conversation.generation;
  await mutateState((current) => {
    const latest = current.conversations[conversation.id];
    if (!latest || latest.generation !== generation || latest.url !== conversation.url) return current;
    return stateModel.patchConversation(current, conversation.id, {
      enabled: false,
      generation: latest.generation + 1,
      lastStatus: "conversation_exhausted",
      lastRunAt: new Date().toISOString(),
      nextRunAt: null
    }).state;
  });
  await clearConversationAlarm(conversation.id);
  return { ok: true, reason: "conversation_exhausted" };
}

async function authorizeDelivery(message, sender) {
  const state = await getBridgeState();
  const conversation = conversationForSender(state, message, sender);
  const active = conversation ? activeDeliveries.get(conversation.id) : null;
  if (!conversation || !active || active.id !== message.deliveryId || active.tabId !== sender.tab.id ||
      active.generation !== conversation.generation || active.bindingRevision !== conversation.bindingRevision ||
      (!active.manual && (!conversation.enabled || !state.settings.masterEnabled))) {
    return { ok: false, reason: "delivery_cancelled" };
  }
  active.assistantBaseline = String(message.assistantBaseline || "").slice(0, 500);
  return { ok: true };
}