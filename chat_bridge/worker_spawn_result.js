const CONVERSATION_SPAWN_RESULT_PROTOCOL_VERSION = 2;
// The legacy angle-bracket marker stays readable for already-submitted children.
// New campaigns use an ASCII-only footer to avoid losing the marker to
// ChatGPT's rich-text rendering before the result reaches the DOM.
const CONVERSATION_SPAWN_COMPLETION_MARKER_RE =
  /^(?:<<<LOCAL_AGENT_CF_CHILD_COMPLETE:[0-9a-f]{8}:[A-Za-z0-9._-]{1,64}:[0-9a-f]{8}>>>|LOCAL_AGENT_CF_CHILD_COMPLETE:[0-9a-f]{8}:[A-Za-z0-9._-]{1,64}:[0-9a-f]{8})$/gm;

function conversationSpawnCompletionMarker(intent) {
  const matches = Array.from(
    String(intent?.bootstrap_text || "").matchAll(CONVERSATION_SPAWN_COMPLETION_MARKER_RE),
    (match) => match[0]
  );
  return matches.length === 1 ? matches[0] : "";
}

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
  const childUrl = normalizeConversationUrl(tab.url || "");
  if (!childUrl) return { ok: false, reason: "child_route_not_ready" };

  const completionMarker = conversationSpawnCompletionMarker(intent);
  if (!completionMarker) {
    // Campaigns created by an older Bridge did not carry an explicit completion
    // proof. Fail closed by leaving the child pending until the bounded campaign
    // timeout rather than reintroducing heuristic terminal detection.
    return {
      ok: true,
      reason: "child_generating",
      childConversationUrl: childUrl
    };
  }

  const message = {
    type: "bridge:spawn-result",
    protocolVersion: CONVERSATION_SPAWN_RESULT_PROTOCOL_VERSION,
    transactionId: intent.transaction_id,
    childRequestDigest: intent.child_request_digest,
    bootstrapDigest: intent.bootstrap_digest,
    completionMarker
  };
  const deliver = async () => {
    await requireLegacyConversationSpawnEffectAllowed();
    return chrome.tabs.sendMessage(tab.id, message, { frameId: 0 });
  };

  let response;
  try {
    response = await deliver();
  } catch (_error) { response = null; }
  if (response?.protocolVersion !== CONVERSATION_SPAWN_RESULT_PROTOCOL_VERSION) {
    try {
      await requireLegacyConversationSpawnEffectAllowed();
      await chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: [0] },
        files: ["control_protocol.js", "spawn_result_content.js"]
      });
      response = await deliver();
    } catch (error) {
      return { ok: false, reason: "child_result_unavailable", error: String(error) };
    }
  }
  if (response?.protocolVersion !== CONVERSATION_SPAWN_RESULT_PROTOCOL_VERSION) {
    return { ok: false, reason: "spawn_content_protocol_mismatch" };
  }
  if (response?.ok) {
    if (response.childConversationUrl !== childUrl) return { ok: false, reason: "spawn_child_identity_invalid" };
    // Extension reload clears storage.session. Recover only from the tab's exact
    // transaction/request/bootstrap claim, validated by the child content controller.
    await rememberConversationSpawnTab(intent.transaction_id, tab.id);
  }
  return response || { ok: false, reason: "child_result_unavailable" };
}

async function observeConversationSpawnResult(intent) {
  return sendConversationSpawnResultMessage(intent);
}

async function forgetConversationSpawnTab(intent) {
  validateConversationSpawnBrowserIntent(intent, { requireTab: true });
  await requireConversationSpawnBootstrapDigest(intent);
  await chrome.storage.session.remove([
    conversationSpawnTabClaimKey(intent.transaction_id),
    conversationSpawnProvisionalEvidenceKey(intent.transaction_id)
  ]);
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
      const owned = await sendConversationSpawnResultMessage(intent);
      if (!owned?.ok) return { ok: false, reason: "spawn_tab_claim_mismatch" };
    }
    try {
      await requireLegacyConversationSpawnEffectAllowed();
      await chrome.tabs.remove(tab.id);
    } catch (error) {
      return { ok: false, reason: "spawn_tab_close_failed", error: String(error) };
    }
  }

  await forgetConversationSpawnTab(intent);
  return { ok: true, reason: tab?.id ? "child_closed" : "child_already_closed" };
}