function runtimeAgentForBinding(runtime, binding) {
  const canonical = stateModel.sanitizeAgentBinding(binding);
  return canonical ? runtime.agents.find((agent) => agent.agentBinding === canonical) || null : null;
}

function runtimeAgentForConversation(runtime, conversation) {
  if (!stateModel.isBoundConversation(conversation)) return null;
  const agent = runtimeAgentForBinding(runtime, conversation.agentBinding);
  if (!agent) return null;
  if (agent.repositoryId !== conversation.repositoryId) return null;
  if (agent.repository.toLowerCase() !== conversation.repository.toLowerCase()) return null;
  return agent;
}

function resolveBindingInput(runtime, raw = {}) {
  const requestedBinding = stateModel.sanitizeAgentBinding(raw.agentBinding);
  const requestedId = stateModel.sanitizeRepositoryId(raw.repositoryId);
  let agent = requestedBinding ? runtimeAgentForBinding(runtime, requestedBinding) : null;
  if (!agent && requestedId) {
    agent = runtime.agents.find((item) => item.repositoryId === requestedId) || null;
  }
  if (!agent) throw new Error("Select a valid Local Agent repository binding.");
  if (requestedBinding && requestedBinding !== agent.agentBinding) {
    throw new Error("agent binding does not match selected repository");
  }
  if (requestedId && requestedId !== agent.repositoryId) {
    throw new Error("repository id does not match selected agent binding");
  }
  return agent;
}

function bindingEnvelope(conversation) {
  return `[LA_AGENT=${conversation.agentBinding}] [LA_REPO=${conversation.repositoryId}] [LA_REPOSITORY=${conversation.repository}] [LA_CHAT=${conversation.id}]`;
}

function bindingPolicy(conversation, runtimeAgent) {
  const executionPolicy = runtimeAgent?.executionEnabled === false
    ? "Bridge/operator-only: do not create Local Agent project task files."
    : `Every Local Agent task JSON must use exactly \"agent_binding\": \"${conversation.agentBinding}\".`;
  return `${bindingEnvelope(conversation)}\nBound to ${conversation.repository} (${conversation.repositoryId}); never inspect, queue, cancel, execute, switch, or rebind another repository. ${executionPolicy} If another repository is required, use PAUSE.`;
}

function assistantControlMarker(markerName) {
  const entry = protocol.COMMAND_CATALOG.find((candidate) =>
    candidate.privilege === "assistant" &&
    (candidate.marker === markerName || candidate.marker.startsWith(`${markerName}=`))
  );
  if (!entry) throw new Error(`missing assistant command catalog entry: ${markerName}`);
  return `[LAB:${entry.marker}]`;
}

function assistantScheduleControlSummary() {
  return protocol.COMMAND_CATALOG
    .filter((entry) => entry.privilege === "assistant" && entry.category === "schedule")
    .map((entry) => `[LAB:${entry.marker}]`)
    .join(", ");
}

function eventWakePlannerPolicy() {
  const waitTask = assistantControlMarker("WAIT_TASK");
  return `For one exact queued/active Local Agent task use ${waitTask}: event-driven wake plus alarm fallback. Use NEXT only for time/external checks. A task_result_ready event is a wake hint only; read the exact terminal result.`;
}

function buildBootstrapPrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  const controls = assistantScheduleControlSummary();
  return `${bindingPolicy(conversation, agent)}\n${runtime.bootstrapPrompt}\n${eventWakePlannerPolicy()}\nSupported chat controls: ${controls}. Controls are conversation-scoped; Master and repository binding are operator-only.`;
}

function buildWakePrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  return `${bindingPolicy(conversation, agent)}\n${runtime.wakePrompt}\n${eventWakePlannerPolicy()}`;
}

function buildEventWakePrompt(runtime, conversation, pending) {
  if (conversation.bootstrapPending) {
    return `${buildBootstrapPrompt(runtime, conversation)}\n[LA_EVENT=task_result_ready]\n[LA_TASK=${pending.taskId}]\nWake hint only. Read the exact result before deciding the next action; continue the active goal in this bound repository.`;
  }
  const agent = runtimeAgentForConversation(runtime, conversation);
  return `${bindingPolicy(conversation, agent)}\n[LA_WAKE]\n[LA_EVENT=task_result_ready]\n[LA_TASK=${pending.taskId}]\nWake hint only. Read the exact result before deciding the next action; continue the active goal in this bound repository.`;
}
