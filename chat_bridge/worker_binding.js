function runtimeAgentForBinding(runtime, binding) {
  const canonical = stateModel.sanitizeAgentBinding(binding);
  return canonical ? runtime.agents.find((agent) => agent.agentBinding === canonical) || null : null;
}

function transportAgent(runtime) {
  const agents = runtime?.agents || [];
  return agents.find((agent) => agent.plannerScope === "multirepo") ||
    agents.find((agent) => agent.executionEnabled) ||
    agents[0] || null;
}

function runtimeAgentForConversation(runtime, conversation) {
  if (!conversation) return null;
  const legacy = runtimeAgentForBinding(runtime, conversation.agentBinding);
  if (
    legacy &&
    legacy.repositoryId === conversation.repositoryId &&
    legacy.repository.toLowerCase() === String(conversation.repository || "").toLowerCase()
  ) {
    return legacy;
  }
  return transportAgent(runtime);
}

function resolveBindingInput(runtime, raw = {}) {
  const requestedBinding = stateModel.sanitizeAgentBinding(raw.agentBinding);
  const requestedId = stateModel.sanitizeRepositoryId(raw.repositoryId);
  let agent = requestedBinding ? runtimeAgentForBinding(runtime, requestedBinding) : null;
  if (!agent && requestedId) {
    agent = runtime.agents.find((item) => item.repositoryId === requestedId) || null;
  }
  if (!agent && !requestedBinding && !requestedId) agent = transportAgent(runtime);
  if (!agent) throw new Error("No Local Agent transport workspace is available.");
  if (requestedBinding && requestedBinding !== agent.agentBinding) {
    throw new Error("agent binding does not match selected repository");
  }
  if (requestedId && requestedId !== agent.repositoryId) {
    throw new Error("repository id does not match selected agent binding");
  }
  return agent;
}

function bindingEnvelope(conversation) {
  return `[LA_CHAT=${conversation.id}]`;
}

function buildBootstrapPrompt(runtime, conversation) {
  return `${bindingEnvelope(conversation)}\n${runtime.bootstrapPrompt}`;
}

function buildWakePrompt(runtime, conversation) {
  return `${bindingEnvelope(conversation)}\n${runtime.wakePrompt}`;
}
