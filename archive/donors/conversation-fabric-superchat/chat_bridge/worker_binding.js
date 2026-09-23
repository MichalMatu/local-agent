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
    ? "This binding is bridge/operator-only; do not create Local Agent project task files for it."
    : `Every Local Agent task JSON created by this conversation MUST contain exactly \"agent_binding\": \"${conversation.agentBinding}\".`;
  return `${bindingEnvelope(conversation)}\nHard binding is immutable for this wake. Work only on repository ${conversation.repository} (${conversation.repositoryId}). Never infer, substitute, inspect, queue, cancel, or execute work for another repository under the current binding. ${executionPolicy} If the active goal explicitly requires another registered repository, use [LAB:REBIND=<repository-id>] with the exact runtime-catalog repository id and wait for the fresh bootstrap before acting there; never guess a repository id from prose.`;
}

function buildBootstrapPrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  return `${bindingPolicy(conversation, agent)}\n${runtime.bootstrapPrompt}\nBridge controls are conversation-scoped. Continue only the active goal of this conversation. Prefer short final-line controls: [LAB:STOP], [LAB:PAUSE], [LAB:RESUME], [LAB:NEXT=30s], [LAB:NEXT=10m], [LAB:INTERVAL=30m], [LAB:INTERVAL=AUTO]. Exact binding controls are [LAB:ADD=<repository-id>] for an unconfigured chat, [LAB:REBIND=<repository-id>] for an explicit repository switch, and [LAB:REMOVE] to remove this chat. Conversation controls may overwrite this chat's pause/enabled state, wake timing, interval, and explicit repository binding. They must never change the global Master switch. NEXT arms or re-arms this conversation and changes only its next wake, not the normal interval or global master switch.`;
}

function buildWakePrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  return `${bindingPolicy(conversation, agent)}\n${runtime.wakePrompt}`;
}
