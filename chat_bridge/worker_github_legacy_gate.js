const legacyAssistantControlHandler = applyAssistantControl;
const legacyOperatorControlHandler = applyOperatorLabControl;

function githubManagedControlResult(authority) {
  return {
    ok: true,
    reason: "github_control_managed",
    managed: true,
    controlGeneration: authority.controlGeneration,
    bindingRevision: authority.bindingRevision,
    authoritySource: authority.source
  };
}

async function githubAuthorityForControlMessage(message, sender) {
  const senderUrl = normalizeConversationUrl(sender?.url || sender?.tab?.url || "");
  const declaredUrl = normalizeConversationUrl(message?.conversationUrl || "");
  if (!senderUrl || senderUrl !== declaredUrl) return null;
  const state = await getBridgeState();
  const conversation = state.conversations[conversationId(declaredUrl)] || null;
  if (!conversation) return null;
  return githubScheduleAuthority(conversation, state);
}

applyAssistantControl = async function applyGithubAwareAssistantControl(message, sender) {
  const parsed = parseAssistantControl(String(message?.control?.marker || ""));
  const scheduleActions = new Set(["stop", "pause", "resume", "interval", "next"]);
  if (parsed && scheduleActions.has(parsed.action)) {
    const authority = await githubAuthorityForControlMessage(message, sender);
    if (authority) return githubManagedControlResult(authority);
  }
  return legacyAssistantControlHandler(message, sender);
};

applyOperatorLabControl = async function applyGithubAwareOperatorControl(message, sender) {
  const parsed = parseOperatorControl(String(message?.control?.marker || ""));
  const scheduleCommands = new Set(["enable", "disable", "interval"]);
  if (parsed && scheduleCommands.has(parsed.command)) {
    const authority = await githubAuthorityForControlMessage(message, sender);
    if (authority) return githubManagedControlResult(authority);
  }
  return legacyOperatorControlHandler(message, sender);
};
