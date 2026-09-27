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

function runtimeCatalogPolicy(runtime) {
  return runtime.agents
    .map((agent) => `${agent.repositoryId}=${agent.repository}@${agent.agentBinding};execution=${agent.executionEnabled ? "enabled" : "disabled"}`)
    .join(" | ");
}

function repositoryBindingPolicy(conversation, runtimeAgent) {
  const executionPolicy = runtimeAgent?.executionEnabled === false
    ? "This binding is bridge/operator-only; do not create Local Agent project task files for it."
    : `Every Local Agent task JSON created by this conversation MUST contain exactly \"agent_binding\": \"${conversation.agentBinding}\".`;
  return `Hard binding is immutable for this wake. Work only on repository ${conversation.repository} (${conversation.repositoryId}). Never infer, substitute, inspect, queue, cancel, or execute work for another repository under the current binding. ${executionPolicy} If the active goal explicitly requires another registered repository, use [LAB:REBIND=<repository-id>] with the exact runtime-catalog repository id and wait for the fresh bootstrap before acting there; never guess a repository id from prose.`;
}

function multirepoBindingPolicy(conversation, runtime) {
  return `Operator multirepo binding is immutable for this wake. This conversation may inspect, edit, queue, cancel, and execute work across any repository listed in the current runtime catalog without rebinding. The conversation binding identifies this operator workspace; it is not the target-repository binding for delegated work. Resolve every target from the runtime catalog and never guess repository ids or bindings. For Local Agent task JSON, use the exact agent_binding of the target repository, not ${conversation.agentBinding}, unless the target itself is ${conversation.repositoryId}. A target with execution=disabled may still be inspected or edited through direct GitHub operations, but no Local Agent task may be queued for that target. Normal work across catalog repositories must not use LAB:REBIND. Current runtime catalog: ${runtimeCatalogPolicy(runtime)}.`;
}

function bindingPolicy(conversation, runtimeAgent, runtime) {
  const policy = runtimeAgent?.plannerScope === "multirepo"
    ? multirepoBindingPolicy(conversation, runtime)
    : repositoryBindingPolicy(conversation, runtimeAgent);
  return `${bindingEnvelope(conversation)}\n${policy}`;
}

function buildBootstrapPrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  return `${bindingPolicy(conversation, agent, runtime)}\n${runtime.bootstrapPrompt}\nBridge controls are conversation-scoped. Continue only the active goal of this conversation. Prefer short final-line controls: [LAB:STOP], [LAB:PAUSE], [LAB:RESUME], [LAB:NEXT=30s], [LAB:NEXT=10m], [LAB:INTERVAL=30m], [LAB:INTERVAL=AUTO]. Exact binding controls are [LAB:ADD=<repository-id>] for an unconfigured chat, [LAB:REBIND=<repository-id>] for an explicit repository switch, and [LAB:REMOVE] to remove this chat. Conversation controls may overwrite this chat's pause/enabled state, wake timing, interval, and explicit repository binding. They must never change the global Master switch. NEXT arms or re-arms this conversation and changes only its next wake, not the normal interval or global master switch.`;
}

function buildWakePrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  return `${bindingPolicy(conversation, agent, runtime)}\n${runtime.wakePrompt}`;
}
