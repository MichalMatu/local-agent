const attentionWakeContexts = new Map();
const baseApplyAssistantControl = applyAssistantControl;
const baseBuildBootstrapPrompt = buildBootstrapPrompt;
const baseBuildWakePrompt = buildWakePrompt;
const baseRunFeedbackCycle = runFeedbackCycle;
const baseSaveGlobalSettings = saveGlobalSettings;
const baseRebindConversation = rebindConversation;
const baseUpdateConversation = updateConversation;
const baseDeleteConversation = deleteConversation;

function eventWakePlannerPolicy() {
  return "For one exact queued or active Local Agent task use [LAB:WAIT_TASK=<task-id>]. A task_result_ready event is a wake hint only: read the exact terminal result before deciding the next action. Keep NEXT for genuine time-based or external rechecks.";
}

function decorateAttentionPrompt(prompt, conversation) {
  const pending = attentionWakeContexts.get(conversation.id) || null;
  const policy = eventWakePlannerPolicy();
  if (!pending) return `${prompt}\n${policy}`;
  return `${prompt}\n${policy}\n[LA_EVENT=task_result_ready]\n[LA_TASK=${pending.taskId}]\nWake hint only. Read the exact terminal result before deciding the next action; continue only the active goal in this bound repository.`;
}

buildBootstrapPrompt = function attentionBootstrapPrompt(runtime, conversation) {
  return decorateAttentionPrompt(baseBuildBootstrapPrompt(runtime, conversation), conversation);
};

buildWakePrompt = function attentionWakePrompt(runtime, conversation) {
  return decorateAttentionPrompt(baseBuildWakePrompt(runtime, conversation), conversation);
};

runFeedbackCycle = async function attentionFeedbackCycle(options = {}) {
  const chatId = String(options.conversationId || "");
  const pending = chatId ? await pendingEventWake(chatId) : null;
  if (pending) attentionWakeContexts.set(chatId, pending);
  try {
    const result = await baseRunFeedbackCycle(options);
    if (!pending) return result;

    if (result?.ok) {
      const latest = await pendingEventWake(chatId);
      if (latest?.eventId === pending.eventId) {
        await consumePendingEventWake(chatId, pending.eventId);
      }
      await reconcileNativeEventTransport();
    }
    return {
      ...result,
      eventWake: { eventId: pending.eventId, taskId: pending.taskId }
    };
  } finally {
    const active = attentionWakeContexts.get(chatId);
    if (active?.eventId === pending?.eventId) attentionWakeContexts.delete(chatId);
  }
};

applyAssistantControl = async function attentionAssistantControl(message, sender) {
  const parsed = parseAssistantControl(String(message.control?.marker || ""));
  const result = await baseApplyAssistantControl(message, sender);
  if (!parsed || !result?.ok || result.duplicate) return result;

  if (parsed.action === "wait_task") {
    const state = await getBridgeState();
    let conversation = state.conversations[result.conversationId] || null;
    if (conversation && !conversation.enabled) {
      conversation = await baseUpdateConversation(result.conversationId, { enabled: true });
    }
    const generation = conversation?.generation ?? result.generation;
    const watch = await registerTaskWatch(conversation, parsed.taskId);
    if (!watch?.ok) {
      await updateConversationStatus(result.conversationId, {
        lastStatus: String(watch?.reason || "task_watch_failed")
      }, generation);
      await reconcileNativeEventTransport();
      return {
        ...result,
        ...watch,
        ok: false,
        generation,
        taskId: parsed.taskId,
        fallbackScheduled: true
      };
    }

    await updateConversationStatus(result.conversationId, {
      lastStatus: `waiting_task:${parsed.taskId}`
    }, generation);
    if (watch.matchedRecentEvent) {
      await scheduleAt(result.conversationId, Date.now() + 1000, generation);
    }
    await reconcileNativeEventTransport();
    return {
      ...result,
      ...watch,
      generation,
      reason: watch.matchedRecentEvent ? "task_result_already_ready" : "waiting_task",
      taskId: parsed.taskId
    };
  }

  if (parsed.action === "stop") {
    await clearTaskWatch(result.conversationId);
  } else if (parsed.action === "inspect" && ["rebind", "remove"].includes(parsed.command)) {
    await clearTaskWatch(result.conversationId);
  }

  if (
    ["stop", "pause", "resume", "next", "interval"].includes(parsed.action) ||
    (parsed.action === "inspect" && ["add", "rebind", "remove"].includes(parsed.command))
  ) {
    await reconcileNativeEventTransport();
  }
  return result;
};

saveGlobalSettings = async function attentionSaveGlobalSettings(patch) {
  const state = await baseSaveGlobalSettings(patch);
  await reconcileNativeEventTransport();
  return state;
};

rebindConversation = async function attentionRebindConversation(chatId, patch) {
  const conversation = await baseRebindConversation(chatId, patch);
  await clearTaskWatch(chatId);
  await reconcileNativeEventTransport();
  return conversation;
};

updateConversation = async function attentionUpdateConversation(chatId, patch) {
  const conversation = await baseUpdateConversation(chatId, patch);
  await reconcileNativeEventTransport();
  return conversation;
};

deleteConversation = async function attentionDeleteConversation(chatId) {
  const state = await baseDeleteConversation(chatId);
  await clearTaskWatch(chatId);
  await reconcileNativeEventTransport();
  return state;
};

initializeNativeEventTransport();
