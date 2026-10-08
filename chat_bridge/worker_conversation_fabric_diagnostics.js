/* Machine-only Conversation Fabric intake diagnostics.
 * Reports parser/admission stages without reading prompts, mutating parent chat,
 * or creating child/terminal lifecycle authority.
 */
const CONVERSATION_FABRIC_DIAGNOSTIC_KEY = "bridgeConversationFabricDiagnosticsV1";
const CONVERSATION_FABRIC_DIAGNOSTIC_LIMIT = 128;
const CONVERSATION_FABRIC_DIAGNOSTIC_REASONS = /^[a-z0-9][a-z0-9_:-]{0,79}$/;
const CONVERSATION_FABRIC_DIAGNOSTIC_EVENTS = new Set([
  "control_rejected",
  "control_worker_rejected",
  "control_accepted",
  "control_transport_failed"
]);

async function conversationFabricDiagnosticSnapshot() {
  const stored = await chrome.storage.local.get(CONVERSATION_FABRIC_DIAGNOSTIC_KEY);
  const records = stored[CONVERSATION_FABRIC_DIAGNOSTIC_KEY];
  return records && typeof records === "object" && !Array.isArray(records)
    ? records
    : {};
}

async function reportConversationFabricDiagnostic(message, sender) {
  const context = await conversationFabricDiagnosticContext(message, sender);
  if (!context?.ok) return context;

  const event = message?.event;
  const reason = message?.reason;
  if (
    !CONVERSATION_FABRIC_DIAGNOSTIC_EVENTS.has(event) ||
    typeof reason !== "string" ||
    !CONVERSATION_FABRIC_DIAGNOSTIC_REASONS.test(reason)
  ) {
    return { ok: false, reason: "conversation_fabric_diagnostic_payload_invalid" };
  }

  if (
    context.reason === "conversation_fabric_diagnostic_parent_disabled" &&
    (event !== "control_worker_rejected" ||
      reason !== "conversation_fabric_parent_not_managed")
  ) {
    // An inactive parent may expose only its admission rejection. Never
    // fabricate accepted/transport events while the admission gate is closed.
    return { ok: false, reason: "conversation_fabric_diagnostic_parent_disabled" };
  }

  const conversationUrl = normalizeConversationUrl(message.conversationUrl);
  const chatId = conversationId(conversationUrl);
  return serializeConversationFabric(CONVERSATION_FABRIC_DIAGNOSTIC_KEY, async () => {
    const current = await conversationFabricDiagnosticSnapshot();
    const previous = current[chatId];
    const latest = {
      event,
      reason,
      at: new Date().toISOString()
    };
    // Keep at most the most recent 128 managed conversation diagnostics.
    // A new control attempt never overwrites campaign/result/delivery evidence.
    const entries = Object.entries({ ...current, [chatId]: latest })
      .filter(([id, value]) => protocol.CHAT_ID_RE.test(id) &&
        value && typeof value === "object" &&
        CONVERSATION_FABRIC_DIAGNOSTIC_EVENTS.has(value.event) &&
        typeof value.reason === "string" &&
        CONVERSATION_FABRIC_DIAGNOSTIC_REASONS.test(value.reason))
      .sort((left, right) => String(right[1]?.at || "").localeCompare(String(left[1]?.at || "")))
      .slice(0, CONVERSATION_FABRIC_DIAGNOSTIC_LIMIT);
    await chrome.storage.local.set({
      [CONVERSATION_FABRIC_DIAGNOSTIC_KEY]: Object.fromEntries(entries)
    });
    return {
      ok: true,
      reason: "conversation_fabric_diagnostic_recorded",
      changed: previous?.event !== event || previous?.reason !== reason
    };
  });
}
