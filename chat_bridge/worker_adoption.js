const BRIDGE_ADOPTION_SCHEMA_VERSION = 1;
const BRIDGE_ADOPTION_FIELDS = new Set([
  "schema_version",
  "child_request_id",
  "child_request_digest",
  "child_conversation_url",
  "repository_id",
  "agent_binding",
  "bootstrap_digest"
]);
const BRIDGE_ADOPTION_ID_RE = /^[A-Za-z0-9._-]{1,200}$/;
const BRIDGE_ADOPTION_DIGEST_RE = /^sha256:[0-9a-f]{64}$/;

function validateBridgeAdoptionAuthority(authority) {
  if (!authority || typeof authority !== "object" || Array.isArray(authority)) {
    throw new Error("bridge adoption authority must be an object");
  }
  const keys = Object.keys(authority);
  const extra = keys.filter((key) => !BRIDGE_ADOPTION_FIELDS.has(key));
  if (extra.length) {
    throw new Error(`bridge adoption authority contains unsupported fields: ${extra.sort().join(",")}`);
  }
  const missing = Array.from(BRIDGE_ADOPTION_FIELDS).filter((key) => !Object.hasOwn(authority, key));
  if (missing.length) {
    throw new Error(`bridge adoption authority is missing fields: ${missing.sort().join(",")}`);
  }
  if (authority.schema_version !== BRIDGE_ADOPTION_SCHEMA_VERSION) {
    throw new Error(`bridge adoption schema_version must be ${BRIDGE_ADOPTION_SCHEMA_VERSION}`);
  }
  if (!BRIDGE_ADOPTION_ID_RE.test(String(authority.child_request_id || ""))) {
    throw new Error("bridge adoption child_request_id is invalid");
  }
  if (!BRIDGE_ADOPTION_DIGEST_RE.test(String(authority.child_request_digest || ""))) {
    throw new Error("bridge adoption child_request_digest is invalid");
  }
  if (!BRIDGE_ADOPTION_DIGEST_RE.test(String(authority.bootstrap_digest || ""))) {
    throw new Error("bridge adoption bootstrap_digest is invalid");
  }
  const url = normalizeConversationUrl(authority.child_conversation_url || "");
  if (!url || url !== authority.child_conversation_url) {
    throw new Error("bridge adoption child_conversation_url must be canonical");
  }
  const repositoryId = stateModel.sanitizeRepositoryId(authority.repository_id);
  const agentBinding = stateModel.sanitizeAgentBinding(authority.agent_binding);
  if (!repositoryId || repositoryId !== authority.repository_id) {
    throw new Error("bridge adoption repository_id is invalid");
  }
  if (!agentBinding || agentBinding !== authority.agent_binding) {
    throw new Error("bridge adoption agent_binding is invalid");
  }
  return {
    childRequestId: authority.child_request_id,
    childRequestDigest: authority.child_request_digest,
    childConversationUrl: url,
    repositoryId,
    agentBinding,
    bootstrapDigest: authority.bootstrap_digest
  };
}

function requireAdoptionCompatibleConversation(conversation, expectedAgent) {
  if (!conversation) return;
  if (!stateModel.isBoundConversation(conversation)) {
    throw new Error("registered child URL already exists as an unbound Bridge conversation");
  }
  if (conversation.repositoryId !== expectedAgent.repositoryId) {
    throw new Error("registered child URL already exists with a different repository binding");
  }
  if (conversation.agentBinding !== expectedAgent.agentBinding) {
    throw new Error("registered child URL already exists with a different agent binding");
  }
  if (conversation.repository.toLowerCase() !== expectedAgent.repository.toLowerCase()) {
    throw new Error("registered child URL already exists with a different repository identity");
  }
  if (conversation.bootstrapPending) {
    throw new Error("registered child URL still has a pending Bridge bootstrap");
  }
}

async function adoptRegisteredConversation(authority) {
  const validated = validateBridgeAdoptionAuthority(authority);
  const currentState = await getBridgeState();
  const runtime = await loadRuntimeConfig(currentState);
  if (runtime.source === "unavailable") {
    throw new Error("runtime unavailable during registered child adoption");
  }
  const agent = runtimeAgentForBinding(runtime, validated.agentBinding);
  if (!agent || agent.repositoryId !== validated.repositoryId) {
    throw new Error("registered child adoption does not match runtime binding catalog");
  }

  const id = conversationId(validated.childConversationUrl);
  const existing = currentState.conversations[id];
  requireAdoptionCompatibleConversation(existing, agent);
  if (existing) return existing;

  const result = await mutateState((state) => {
    const concurrent = state.conversations[id];
    requireAdoptionCompatibleConversation(concurrent, agent);
    if (concurrent) return { state, conversation: concurrent, value: { created: false } };

    const upserted = stateModel.upsertConversation(state, {
      url: validated.childConversationUrl,
      label: `Conversation Fabric ${validated.childRequestId}`,
      enabled: true,
      preferredTabId: null,
      repositoryId: agent.repositoryId,
      repository: agent.repository,
      agentBinding: agent.agentBinding,
      bindingRevision: 1,
      bindingSetAt: new Date().toISOString(),
      assistantBaseline: "",
      bootstrapPending: false,
      lastStatus: "adopted_registered_child"
    });
    if (!stateModel.isBoundConversation(upserted.conversation)) {
      throw new Error("registered child adoption produced an unbound conversation");
    }
    if (upserted.conversation.bootstrapPending) {
      throw new Error("registered child adoption must not schedule a second bootstrap");
    }
    return {
      state: upserted.state,
      conversation: upserted.conversation,
      value: { created: true }
    };
  });

  if (result.value?.created) {
    await clearAssistantErrorRecovery(result.conversation.id);
    await clearAssistantTransientRecovery(result.conversation.id);
  }
  if (result.conversation.enabled) {
    await scheduleDefault(
      result.conversation.id,
      true,
      result.conversation.generation
    );
  }
  return result.conversation;
}
