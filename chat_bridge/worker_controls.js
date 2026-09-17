const ASSISTANT_BINDING_DEDUPE_KEY = "bridgeAssistantBindingControlDedupe";
const ASSISTANT_BINDING_DEDUPE_LIMIT = 64;

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

function validControlFingerprint(message) {
  const fingerprint = String(message.fingerprint || "");
  return /^[0-9a-f]{8}$/.test(fingerprint) ? fingerprint : "";
}

function assistantControlUrl(message, sender) {
  if (sender?.id !== chrome.runtime.id || sender?.frameId !== 0 || !sender?.tab?.id) return "";
  const senderUrl = normalizeConversationUrl(sender.url || sender.tab.url || "");
  const declaredUrl = normalizeConversationUrl(message.conversationUrl || "");
  return senderUrl && senderUrl === declaredUrl ? declaredUrl : "";
}

async function readAssistantBindingDedupe() {
  const stored = await chrome.storage.local.get(ASSISTANT_BINDING_DEDUPE_KEY);
  const raw = stored[ASSISTANT_BINDING_DEDUPE_KEY];
  return raw && typeof raw === "object" ? raw : {};
}

async function writeAssistantBindingDedupe(chatId, fingerprint) {
  const current = await readAssistantBindingDedupe();
  current[chatId] = { fingerprint, at: Date.now() };
  const entries = Object.entries(current).sort((a, b) => Number(b[1]?.at || 0) - Number(a[1]?.at || 0));
  await chrome.storage.local.set({
    [ASSISTANT_BINDING_DEDUPE_KEY]: Object.fromEntries(entries.slice(0, ASSISTANT_BINDING_DEDUPE_LIMIT))
  });
}

async function applyAssistantBindingControl(parsed, message, sender) {
  const fingerprint = validControlFingerprint(message);
  if (!fingerprint) return { ok: false, reason: "control_invalid_fingerprint" };
  const url = assistantControlUrl(message, sender);
  if (!url) return { ok: false, reason: "control_wrong_conversation" };
  const chatId = conversationId(url);
  const dedupe = await readAssistantBindingDedupe();
  if (dedupe[chatId]?.fingerprint === fingerprint) {
    return { ok: true, reason: "control_duplicate", duplicate: true };
  }

  const state = await getBridgeState();
  const current = state.conversations[chatId] || null;
  let conversation = current;

  if (parsed.command === "add") {
    if (current && current.repositoryId !== parsed.repositoryId) {
      return { ok: false, reason: "assistant_chat_already_bound" };
    }
    if (!current) {
      conversation = await upsertConversation({
        url,
        label: String(message.chatLabel || "ChatGPT conversation"),
        repositoryId: parsed.repositoryId,
        enabled: true,
        preferredTabId: sender.tab.id,
        assistantBaseline: String(message.assistantIdentity || "")
      });
    }
  } else if (parsed.command === "rebind") {
    if (!current) return { ok: false, reason: "assistant_chat_not_configured" };
    if (current.repositoryId !== parsed.repositoryId) {
      conversation = await rebindConversation(chatId, { repositoryId: parsed.repositoryId });
    }
  } else if (parsed.command === "remove") {
    if (current) await deleteConversation(chatId);
    conversation = null;
  } else {
    return { ok: false, reason: "assistant_binding_unknown_command" };
  }

  await writeAssistantBindingDedupe(chatId, fingerprint);
  return {
    ok: true,
    reason: `assistant_${parsed.command}`,
    conversationId: chatId,
    conversation
  };
}

async function rememberMaintenanceControl(message, sender, parsed) {
  const fingerprint = validControlFingerprint(message);
  if (!fingerprint) return { ok: false, reason: "control_invalid_fingerprint" };
  const result = await mutateState((state) => {
    const conversation = conversationForSender(state, message, sender);
    if (!conversation || !stateModel.isBoundConversation(conversation)) {
      return { state, value: { ok: false, reason: "control_unbound_conversation" } };
    }
    // Bridge-local maintenance must remain usable while a binding bootstrap is pending.
    // It does not change repository identity, so ordinary binding-revision freshness is irrelevant.
    if (conversation.assistantBaseline && message.assistantIdentity === conversation.assistantBaseline) {
      return { state, value: { ok: false, reason: "control_stale_binding" } };
    }
    if (conversation.lastControlFingerprint === fingerprint) {
      return { state, value: { ok: true, reason: "control_duplicate", duplicate: true } };
    }
    conversation.lastControlFingerprint = fingerprint;
    conversation.lastControlAction = parsed.marker;
    conversation.lastControlAt = new Date().toISOString();
    conversation.lastStatus = `${parsed.command}_by_assistant`;
    return {
      state,
      value: {
        ok: true,
        conversationId: conversation.id,
        bindingRevision: conversation.bindingRevision
      }
    };
  });
  return result.value;
}

async function applyAssistantControl(message, sender) {
  const parsed = parseAssistantControl(String(message.control?.marker || ""));
  if (!parsed) return { ok: false, reason: "control_invalid_marker" };
  const fingerprint = validControlFingerprint(message);
  if (!fingerprint) return { ok: false, reason: "control_invalid_fingerprint" };

  const bindingCommands = new Set(["add", "remove", "rebind"]);
  if (parsed.action === "inspect" && bindingCommands.has(parsed.command)) {
    return applyAssistantBindingControl(parsed, message, sender);
  }

  const maintenanceCommands = new Set(["reload_content", "reload_bridge"]);
  if (parsed.action === "inspect" && maintenanceCommands.has(parsed.command)) {
    const remembered = await rememberMaintenanceControl(message, sender, parsed);
    if (!remembered.ok || remembered.duplicate) return remembered;
    const result = await labAssistantMaintenance(parsed, message, sender);
    if (result.reloadBridge) {
      setTimeout(() => chrome.runtime.reload(), 100);
    }
    return result;
  }

  if (parsed.action === "inspect") {
    return labInspectionFeedback(parsed, message, sender);
  }

  // Compatibility for already-injected protocol objects from pre-v7 content.
  if (parsed.action === "maintenance") {
    const remembered = await rememberMaintenanceControl(message, sender, parsed);
    if (!remembered.ok || remembered.duplicate) return remembered;
    const result = await labAssistantMaintenance(parsed, message, sender);
    if (result.reloadBridge) {
      setTimeout(() => chrome.runtime.reload(), 100);
    }
    return result;
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
