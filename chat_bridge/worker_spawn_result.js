async function observeConversationSpawnResult(intent) {
  const response = await sendConversationSpawnContentMessage(intent, "bridge:spawn-result");
  if (!response || typeof response !== "object") {
    return { ok: false, reason: "child_result_unavailable" };
  }
  return response;
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
