async function sendConversationSpawnResultMessage(intent) {
  validateConversationSpawnBrowserIntent(intent, { requireTab: true });
  await requireConversationSpawnBootstrapDigest(intent);

  let tab;
  try {
    tab = await chrome.tabs.get(intent.tab_id);
  } catch (error) {
    return { ok: false, reason: "spawn_tab_unavailable", error: String(error) };
  }
  if (!tab?.id) return { ok: false, reason: "spawn_tab_unavailable" };
  const route = await validateConversationSpawnTabRoute(intent, tab);
  if (!route.ok || route.route !== "child") {
    return route.ok ? { ok: false, reason: "child_route_not_ready" } : route;
  }

  const message = {
    type: "bridge:spawn-result",
    protocolVersion: CONVERSATION_SPAWN_CONTENT_PROTOCOL_VERSION,
    transactionId: intent.transaction_id,
    childRequestDigest: intent.child_request_digest,
    bootstrapDigest: intent.bootstrap_digest
  };
  const deliver = async () => chrome.tabs.sendMessage(tab.id, message, { frameId: 0 });

  let response;
  try {
    response = await deliver();
  } catch (_error) {
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: [0] },
        files: ["control_protocol.js", "spawn_result_content.js"]
      });
      response = await deliver();
    } catch (error) {
      return { ok: false, reason: "child_result_unavailable", error: String(error) };
    }
  }
  if (response?.protocolVersion !== CONVERSATION_SPAWN_CONTENT_PROTOCOL_VERSION) {
    return { ok: false, reason: "spawn_content_protocol_mismatch" };
  }
  return response || { ok: false, reason: "child_result_unavailable" };
}

async function observeConversationSpawnResult(intent) {
  return sendConversationSpawnResultMessage(intent);
}

async function closeConversationSpawnTab(intent) {
  validateConversationSpawnBrowserIntent(intent, { requireTab: true });
  await requireConversationSpawnBootstrapDigest(intent);

  let tab;
  try {
    tab = await chrome.tabs.get(intent.tab_id);
  } catch (_error) {
    tab = null;
  }
  if (tab?.id) {
    if (!await conversationSpawnTabClaimMatches(intent.transaction_id, tab.id)) {
      return { ok: false, reason: "spawn_tab_claim_mismatch" };
    }
    try {
      await chrome.tabs.remove(tab.id);
    } catch (error) {
      return { ok: false, reason: "spawn_tab_close_failed", error: String(error) };
    }
  }

  await chrome.storage.session.remove([
    conversationSpawnTabClaimKey(intent.transaction_id),
    conversationSpawnProvisionalEvidenceKey(intent.transaction_id)
  ]);
  return { ok: true, reason: tab?.id ? "child_closed" : "child_already_closed" };
}
