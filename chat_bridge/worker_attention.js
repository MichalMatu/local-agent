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
  return "For one exact queued or active Local Agent task use [LAB:WAIT_TASK=<task-id>]. For durable Conversation Fabric child completions use [LAB:WAIT_WORKFLOW=<workflow-id>] in the exact parent chat. Native events are wake hints only: read the authoritative task result or compact workflow/terminal ledger before deciding the next action. Keep NEXT for genuine time-based or external rechecks.";
}

function attentionContextForPrompt(conversation) {
  return attentionWakeContexts.get(conversation.id) || null;
}

function decorateAttentionPrompt(prompt, conversation) {
  const context = attentionContextForPrompt(conversation);
  const policy = eventWakePlannerPolicy();
  if (!context) return `${prompt}\n${policy}`;
  const pending = context.pending;
  if (context.kind === "task") {
    return `${prompt}\n${policy}\n[LA_EVENT=task_result_ready]\n[LA_TASK=${pending.taskId}]\nWake hint only. Read the exact terminal result before deciding the next action; continue only the active goal in this bound repository.`;
  }
  return `${prompt}\n${policy}\n[LA_EVENT=child_terminal_ready]\n[LA_WORKFLOW=${pending.workflowId}]\n[LA_WORKFLOW_NODE=${pending.workflowNodeId}]\n[LA_CHILD_REQUEST=${pending.childRequestId}]\n[LA_CHILD_OUTCOME=${pending.outcome}]\n[LA_CHILD_TERMINAL_DIGEST=${pending.terminalDigest}]\nWake hint only. Re-read the compact durable parent ledger and exact child terminal record before synthesis or scheduling; do not treat this notification as evidence.`;
}

buildBootstrapPrompt = function attentionBootstrapPrompt(runtime, conversation) {
  return decorateAttentionPrompt(baseBuildBootstrapPrompt(runtime, conversation), conversation);
};

buildWakePrompt = function attentionWakePrompt(runtime, conversation) {
  return decorateAttentionPrompt(baseBuildWakePrompt(runtime, conversation), conversation);
};

async function nextAttentionWake(chatId) {
  const [task, workflow] = await Promise.all([
    pendingEventWake(chatId),
    pendingWorkflowAttention(chatId)
  ]);
  if (!task) return workflow ? { kind: "workflow", pending: workflow } : null;
  if (!workflow) return { kind: "task", pending: task };
  const taskAt = Date.parse(task.receivedAt);
  const workflowAt = Date.parse(workflow.receivedAt);
  if (workflowAt < taskAt || (workflowAt === taskAt && workflow.eventId < task.eventId)) {
    return { kind: "workflow", pending: workflow };
  }
  return { kind: "task", pending: task };
}

runFeedbackCycle = async function attentionFeedbackCycle(options = {}) {
  const chatId = String(options.conversationId || "");
  const context = chatId ? await nextAttentionWake(chatId) : null;
  if (context) attentionWakeContexts.set(chatId, context);
  try {
    const result = await baseRunFeedbackCycle(options);
    if (!context) return result;

    const pending = context.pending;
    if (result?.ok) {
      if (context.kind === "task") {
        const latest = await pendingEventWake(chatId);
        if (latest?.eventId === pending.eventId) {
          await consumePendingEventWake(chatId, pending.eventId);
        }
      } else {
        const latest = await pendingWorkflowAttention(chatId);
        if (latest?.eventId === pending.eventId) {
          await consumePendingWorkflowAttention(pending.eventId);
        }
      }
      await reconcileNativeEventTransport();
    }
    return {
      ...result,
      eventWake: context.kind === "task"
        ? { eventId: pending.eventId, taskId: pending.taskId }
        : {
            eventId: pending.eventId,
            workflowId: pending.workflowId,
            workflowNodeId: pending.workflowNodeId,
            childRequestId: pending.childRequestId,
            outcome: pending.outcome,
            terminalDigest: pending.terminalDigest
          }
    };
  } finally {
    const active = attentionWakeContexts.get(chatId);
    if (active?.kind === context?.kind && active?.pending?.eventId === context?.pending?.eventId) {
      attentionWakeContexts.delete(chatId);
    }
  }
};

async function enabledConversationForAttention(result) {
  const state = await getBridgeState();
  let conversation = state.conversations[result.conversationId] || null;
  if (conversation && !conversation.enabled) {
    conversation = await baseUpdateConversation(result.conversationId, { enabled: true });
  }
  return conversation;
}

applyAssistantControl = async function attentionAssistantControl(message, sender) {
  const parsed = parseAssistantControl(String(message.control?.marker || ""));
  const result = await baseApplyAssistantControl(message, sender);
  if (!parsed || !result?.ok || result.duplicate) return result;

  if (parsed.action === "wait_task") {
    const conversation = await enabledConversationForAttention(result);
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

  if (parsed.action === "wait_workflow") {
    const conversation = await enabledConversationForAttention(result);
    const generation = conversation?.generation ?? result.generation;
    const watch = await registerWorkflowWatch(conversation, parsed.workflowId);
    if (!watch?.ok) {
      await updateConversationStatus(result.conversationId, {
        lastStatus: String(watch?.reason || "workflow_watch_failed")
      }, generation);
      await reconcileNativeEventTransport();
      return {
        ...result,
        ...watch,
        ok: false,
        generation,
        workflowId: parsed.workflowId,
        fallbackScheduled: true
      };
    }
    await updateConversationStatus(result.conversationId, {
      lastStatus: `waiting_workflow:${parsed.workflowId}`
    }, generation);
    if (watch.matchedRecentEvents > 0) {
      await scheduleAt(result.conversationId, Date.now() + 1000, generation);
    }
    await reconcileNativeEventTransport();
    return {
      ...result,
      ...watch,
      generation,
      reason: watch.matchedRecentEvents > 0 ? "workflow_attention_already_ready" : "waiting_workflow",
      workflowId: parsed.workflowId
    };
  }

  if (parsed.action === "stop") {
    await Promise.all([
      clearTaskWatch(result.conversationId),
      clearWorkflowWatch(result.conversationId)
    ]);
  } else if (parsed.action === "inspect" && ["rebind", "remove"].includes(parsed.command)) {
    await Promise.all([
      clearTaskWatch(result.conversationId),
      clearWorkflowWatch(result.conversationId)
    ]);
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
  await Promise.all([clearTaskWatch(chatId), clearWorkflowWatch(chatId)]);
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
  await Promise.all([clearTaskWatch(chatId), clearWorkflowWatch(chatId)]);
  await reconcileNativeEventTransport();
  return state;
};

initializeNativeEventTransport();
