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

function runtimeCatalogPolicy(runtime) {
  return (runtime?.agents || [])
    .map((agent) => `${agent.repositoryId}=${agent.repository}@${agent.agentBinding};execution=${agent.executionEnabled ? "enabled" : "disabled"}`)
    .join(" | ");
}

function bindingPolicy(conversation, _runtimeAgent, runtime) {
  const catalog = runtimeCatalogPolicy(runtime);
  return `${bindingEnvelope(conversation)}\nThis Chat Bridge conversation is a transport/scheduling channel, not a repository execution binding. Repository reasoning scope comes from the active user goal and durable Conversation Fabric request and may include multiple repositories, including donor and target repositories, without rebinding the chat. Never treat Bridge metadata as execution authority. Before creating any Local Agent task, resolve the actual target repository from the runtime catalog and use that target's exact canonical agent_binding; never reuse the transport workspace binding as a shortcut. Repositories with execution=disabled may be reasoned about or inspected through allowed GitHub operations but must not receive executable .agent/tasks. Current runtime catalog: ${catalog}.`;
}

function githubScheduleControlPolicy(runtime, conversation) {
  const control = githubControlModel.findConversationControl(runtime, conversation.id);
  if (!control || !githubControlModel.controlMatchesConversation(control, conversation)) return "";
  return "This conversation's schedule control plane is GitHub-backed. For STATUS, PAUSE, RESUME, NEXT and INTERVAL, inspect or update this chat's conversation_controls record in chat_bridge/runtime.json on the chat-bridge-state branch through GitHub. Increment control_generation for every schedule mutation. Repository binding fields are not schedule authority. Do not emit assistant LAB schedule markers for this managed chat; they are legacy no-ops. GitHub desired state must never change the global Master switch.";
}

function buildBootstrapPrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  const githubPolicy = githubScheduleControlPolicy(runtime, conversation);
  const legacyPolicy = "Legacy Bridge add/rebind markers are compatibility-only and must not be used to change repository scope. Bridge conversation controls must never change the global Master switch.";
  return `${bindingPolicy(conversation, agent, runtime)}\n${runtime.bootstrapPrompt}\n${githubPolicy || "Bridge schedule control is not GitHub-managed for this conversation; use the currently supported explicit pacing controls."}\n${legacyPolicy}`;
}

function buildWakePrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  const githubPolicy = githubScheduleControlPolicy(runtime, conversation);
  return `${bindingPolicy(conversation, agent, runtime)}\n${runtime.wakePrompt}${githubPolicy ? `\n${githubPolicy}` : ""}`;
}
