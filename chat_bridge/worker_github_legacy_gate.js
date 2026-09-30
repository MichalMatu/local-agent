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
  const url = labSenderUrl(message, sender);
  if (!url) return null;
  const state = await getBridgeState();
  const conversation = state.conversations[conversationId(url)] || null;
  if (!conversation) return null;
  return githubScheduleAuthority(conversation, state);
}

applyAssistantControl = async function applyGithubAwareAssistantControl(message, sender) {
  const parsed = parseAssistantControl(String(message?.control?.marker || ""));
  const scheduleActions = new Set(["stop", "pause", "resume", "interval", "next"]);
  if (parsed && scheduleActions.has(parsed.action) && validControlFingerprint(message)) {
    const authority = await githubAuthorityForControlMessage(message, sender);
    if (authority) return githubManagedControlResult(authority);
  }
  return legacyAssistantControlHandler(message, sender);
};

applyOperatorLabControl = async function applyGithubAwareOperatorControl(message, sender) {
  const parsed = parseOperatorControl(String(message?.control?.marker || ""));
  const scheduleCommands = new Set(["enable", "disable", "interval"]);
  const fingerprint = String(message?.fingerprint || "");
  if (parsed && scheduleCommands.has(parsed.command) && /^[0-9a-f]{8}$/.test(fingerprint)) {
    const authority = await githubAuthorityForControlMessage(message, sender);
    if (authority) return githubManagedControlResult(authority);
  }
  return legacyOperatorControlHandler(message, sender);
};
