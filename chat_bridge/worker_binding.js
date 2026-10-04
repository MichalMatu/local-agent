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

function resolveBindingInput(runtime, raw = {}) {
  const requestedBinding = stateModel.sanitizeAgentBinding(raw.agentBinding);
  const requestedId = stateModel.sanitizeRepositoryId(raw.repositoryId);
  let agent = requestedBinding ? runtimeAgentForBinding(runtime, requestedBinding) : null;
  if (!agent && requestedId) {
    agent = runtime.agents.find((item) => item.repositoryId === requestedId) || null;
  }
  if (!agent && !requestedBinding && !requestedId) return transportAgent(runtime);
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
  return `${bindingEnvelope(conversation)}\n${runtime.bootstrapPrompt}\n\n${conversationFabricParentInstructions()}`;
}

function buildWakePrompt(runtime, conversation) {
  return `${bindingEnvelope(conversation)}\n${runtime.wakePrompt}\n\nUse the LOCAL_AGENT_CF delegation protocol established at bootstrap when independent reasoning helps. Wait for actual child feedback before synthesis; do not repeat a pending delegation.`;
}

function conversationFabricParentInstructions() {
  return [
    "For independent reasoning jobs, delegate 1-4 bounded tasks to child chats in this Chrome session. Include all source context the children need in their prompts; they do not inherit this conversation.",
    "Children provide reasoning and evidence only. You remain responsible for synthesis and exact target-bound Local Agent execution.",
    "To delegate, end your assistant reply with the following plain-text block, replacing the example jobs. Do not wrap it in Markdown fences or add trailing prose:",
    "<<<LOCAL_AGENT_CF",
    JSON.stringify({ schema_version: 1, action: "delegate", children: [
      { id: "analysis", role: "research", prompt: "A bounded question with its relevant source context." },
      { id: "check", role: "verification", prompt: "An independent verification question with its relevant source context." }
    ] }),
    "LOCAL_AGENT_CF>>>",
    "Bridge returns the actual child results automatically through its existing control poll. Wait for that feedback before synthesizing. Never repeat a delegation merely because its children are still working."
  ].join("\n");
}
