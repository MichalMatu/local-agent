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
