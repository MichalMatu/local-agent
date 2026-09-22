const ASSISTANT_TRANSIENT_REPORT_KINDS = new Set([
  "connection_interrupted",
  "extended_thinking",
  "stalled"
]);

function normalizeAssistantTransientReport(message) {
  const kind = String(message?.kind || "");
  if (!ASSISTANT_TRANSIENT_REPORT_KINDS.has(kind)) return null;
  const signature = String(message?.signature || "").slice(0, 120);
  const userIdentity = String(message?.userIdentity || "").slice(0, 500);
  const userText = String(message?.userText || "").slice(0, 12000);
  if (!signature) return null;
  return {
    assistantTransientState: kind,
    assistantTransientSignature: signature,
    assistantTransientUserIdentity: userIdentity,
    assistantTransientUserText: userText,
    assistantGenerating: Boolean(message?.assistantGenerating),
    composerOccupied: Boolean(message?.composerOccupied)
  };
}

function assistantTransientConversationForSender(state, message, sender) {
  const conversation = conversationForSender(state, message, sender);
  if (!conversation) return { conversation: null, reason: "conversation_not_found" };
  if (
    Number.isInteger(conversation.preferredTabId) &&
    conversation.preferredTabId !== sender?.tab?.id
  ) {
    return { conversation: null, reason: "assistant_transient_wrong_tab" };
  }
  return { conversation, reason: null };
}

async function reportAssistantTransientState(message, sender) {
  const report = normalizeAssistantTransientReport(message);
  if (!report) return { ok: false, reason: "assistant_transient_invalid" };

  const state = await getBridgeState();
  const resolved = assistantTransientConversationForSender(state, message, sender);
  if (!resolved.conversation) return { ok: false, reason: resolved.reason };
  const conversation = resolved.conversation;
  if (!state.settings.masterEnabled || !conversation.enabled || !stateModel.isBoundConversation(conversation)) {
    return { ok: false, reason: "assistant_transient_disabled" };
  }
  if (inFlightDeliveries.has(conversation.id)) {
    return { ok: false, reason: "assistant_transient_delivery_in_progress" };
  }

  if (report.assistantTransientState === "extended_thinking") {
    await updateConversationStatus(
      conversation.id,
      { lastStatus: "assistant_extended_thinking" },
      conversation.generation
    );
    return {
      ok: true,
      reason: "assistant_extended_thinking",
      action: "wait",
      terminal: true
    };
  }

  const result = await recoverAssistantTransient(conversation, sender.tab, report);
  const status = String(result?.reason || "assistant_busy");
  await updateConversationStatus(
    conversation.id,
    { lastStatus: status },
    conversation.generation
  );
  return {
    ...result,
    ok: true,
    reason: status,
    terminal: [
      "assistant_connection_interrupted_unowned",
      "assistant_connection_reload_exhausted",
      "assistant_stalled_unowned",
      "assistant_stalled_after_reload",
      "assistant_tab_reload_failed"
    ].includes(status)
  };
}

async function clearAssistantTransientState(message, sender) {
  const state = await getBridgeState();
  const resolved = assistantTransientConversationForSender(state, message, sender);
  if (!resolved.conversation) return { ok: false, reason: resolved.reason };
  const cleared = await clearAssistantTransientRecovery(resolved.conversation.id);
  return {
    ok: true,
    reason: cleared ? "assistant_transient_cleared" : "assistant_transient_already_clear"
  };
}
