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
  return `Hard binding is immutable for this wake. Work only on repository ${conversation.repository} (${conversation.repositoryId}). Never infer, substitute, inspect, queue, cancel, or execute work for another repository under the current binding. ${executionPolicy} If the active goal explicitly requires another registered repository, use the explicit Bridge binding path with the exact runtime-catalog repository id and wait for the fresh bootstrap before acting there; never guess a repository id from prose.`;
}

function multirepoBindingPolicy(conversation, runtime) {
  return `Operator multirepo binding is immutable for this wake. This conversation may inspect, edit, queue, cancel, and execute work across any repository listed in the current runtime catalog without rebinding. The conversation binding identifies this operator workspace; it is not the target-repository binding for delegated work. Resolve every target from the runtime catalog and never guess repository ids or bindings. For Local Agent task JSON, use the exact agent_binding of the target repository, not ${conversation.agentBinding}, unless the target itself is ${conversation.repositoryId}. A target with execution=disabled may still be inspected or edited through direct GitHub operations, but no Local Agent task may be queued for that target. Normal work across catalog repositories must not rebind this conversation. Current runtime catalog: ${runtimeCatalogPolicy(runtime)}.`;
}

function bindingPolicy(conversation, runtimeAgent, runtime) {
  const policy = runtimeAgent?.plannerScope === "multirepo"
    ? multirepoBindingPolicy(conversation, runtime)
    : repositoryBindingPolicy(conversation, runtimeAgent);
  return `${bindingEnvelope(conversation)}\n${policy}`;
}

function githubScheduleControlPolicy(runtime, conversation) {
  const control = githubControlModel.findConversationControl(runtime, conversation.id);
  if (!control || !githubControlModel.controlMatchesConversation(control, conversation)) return "";
  return "This conversation's schedule control plane is GitHub-backed. For STATUS, PAUSE, RESUME, NEXT and INTERVAL, inspect or update this chat's exact conversation_controls record in chat_bridge/runtime.json on the chat-bridge-state branch through GitHub. Increment control_generation for every schedule mutation. Do not emit assistant LAB schedule markers for this managed chat; they are legacy no-ops. GitHub desired state must never change the global Master switch.";
}

function buildBootstrapPrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  const githubPolicy = githubScheduleControlPolicy(runtime, conversation);
  const legacyPolicy = "Bridge binding and maintenance controls remain explicit migration paths until their GitHub control-plane equivalents are implemented; never use them for normal schedule/status operations.";
  return `${bindingPolicy(conversation, agent, runtime)}\n${runtime.bootstrapPrompt}\n${githubPolicy || "Bridge schedule control is not GitHub-managed for this conversation; use the currently supported explicit Bridge controls."}\n${legacyPolicy}`;
}

function buildWakePrompt(runtime, conversation) {
  const agent = runtimeAgentForConversation(runtime, conversation);
  const githubPolicy = githubScheduleControlPolicy(runtime, conversation);
  return `${bindingPolicy(conversation, agent, runtime)}\n${runtime.wakePrompt}${githubPolicy ? `\n${githubPolicy}` : ""}`;
}
