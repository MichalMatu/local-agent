async function controlContext(message, sender) {
  const state = await getBridgeState();
  const conversation = conversationForSender(state, message, sender);
  if (!stateModel.isBoundConversation(conversation)) {
    return { ok: false, reason: "control_not_ready" };
  }
  return {
    ok: true,
    bindingRevision: conversation.bindingRevision,
    assistantBaseline: conversation.assistantBaseline,
    bootstrapPending: conversation.bootstrapPending
  };
}

async function applyAssistantControl(message, sender) {
  const parsed = parseAssistantControl(String(message.control?.marker || ""));
  if (!parsed) return { ok: false, reason: "control_invalid_marker" };
  const fingerprint = String(message.fingerprint || "");
  if (!/^[0-9a-f]{8}$/.test(fingerprint)) {
    return { ok: false, reason: "control_invalid_fingerprint" };
  }

  const result = await mutateState((state) => {
    const conversation = conversationForSender(state, message, sender);
    if (!conversation) return { state, value: { ok: false, reason: "control_wrong_conversation" } };
    if (!stateModel.isBoundConversation(conversation)) {
      return { state, value: { ok: false, reason: "control_unbound_conversation" } };
    }
    const freshBindingControlsAllowed = conversation.bootstrapPending && conversation.bindingRevision === 1;
    if (message.bindingRevision !== conversation.bindingRevision ||
        (conversation.bootstrapPending && !freshBindingControlsAllowed) ||
        (conversation.assistantBaseline && message.assistantIdentity === conversation.assistantBaseline)) {
      return { state, value: { ok: false, reason: "control_stale_binding" } };
    }
    if (conversation.lastControlFingerprint === fingerprint) {
      return { state, value: { ok: true, reason: "control_duplicate", duplicate: true } };
    }

    Object.assign(conversation, {
      lastControlFingerprint: fingerprint,
      lastControlAction: parsed.marker,
      lastControlAt: new Date().toISOString(),
      generation: conversation.generation + 1
    });
    const value = { ok: true, conversationId: conversation.id, generation: conversation.generation };

    if (parsed.action === "stop" || parsed.action === "pause") {
      conversation.enabled = false;
      conversation.nextRunAt = null;
      if (parsed.action === "stop") conversation.intervalOverrideMinutes = null;
      conversation.lastStatus = parsed.action === "stop" ? "stopped_by_assistant" : "paused_by_assistant";
      value.reason = parsed.action === "stop" ? "stopped" : "paused";
    } else if (parsed.action === "resume") {
      conversation.enabled = true;
      conversation.lastStatus = "resumed_by_assistant";
      value.reason = "resumed";
    } else if (parsed.action === "interval") {
      conversation.intervalOverrideMinutes = parsed.mode === "auto" ? null : parsed.minutes;
      conversation.lastStatus = parsed.mode === "auto"
        ? "interval_auto_by_assistant"
        : `interval_${parsed.minutes}_by_assistant`;
      value.reason = parsed.mode === "auto" ? "interval_auto" : "interval_fixed";
      if (parsed.mode === "fixed") value.minutes = parsed.minutes;
    } else if (parsed.action === "next") {
      conversation.enabled = true;
      conversation.lastStatus = `next_${parsed.seconds}s_by_assistant`;
      value.reason = state.settings.masterEnabled ? "next_scheduled" : "next_armed_master_disabled";
      value.armed = true;
      value.seconds = parsed.seconds;
    }
    return { state, value };
  });

  const value = result.value;
  if (!value.ok || value.duplicate) return value;
  if (parsed.action === "stop" || parsed.action === "pause") {
    await clearConversationAlarm(value.conversationId, value.generation);
  } else if (parsed.action === "next") {
    await scheduleAt(value.conversationId, Date.now() + parsed.seconds * 1000, value.generation);
  } else {
    await scheduleDefault(value.conversationId, parsed.action === "resume", value.generation);
  }
  return value;
}
