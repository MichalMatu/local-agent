from pathlib import Path

def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    assert old in text, path
    p.write_text(text.replace(old, new, 1))

replace_once(
    "chat_bridge/worker_github_control.js",
    """async function reconcileGithubConversationControlsOnce() {
  const state = await getBridgeState();
""",
    """async function recoverGithubControlledConversations(state, runtime) {
  const missing = (runtime.conversationControls || []).filter(
    (control) => !state.conversations?.[control.conversationId]
  );
  if (!missing.length) return { recovered: [], conflicts: [] };

  const wanted = new Set(missing.map((control) => control.conversationId));
  const tabs = await chrome.tabs.query({
    url: ["https://chatgpt.com/*", "https://chat.openai.com/*"]
  });
  const candidates = new Map();
  for (const tab of tabs) {
    if (!Number.isInteger(tab?.id)) continue;
    const url = normalizeConversationUrl(tab.url || "");
    if (!url) continue;
    const chatId = conversationId(url);
    if (!wanted.has(chatId)) continue;
    const matches = candidates.get(chatId) || [];
    matches.push({ tabId: tab.id, url, label: String(tab.title || "GitHub-managed conversation") });
    candidates.set(chatId, matches);
  }

  const recovered = [];
  const conflicts = [];
  for (const control of missing) {
    const matches = candidates.get(control.conversationId) || [];
    if (matches.length > 1) {
      conflicts.push({
        chatId: control.conversationId,
        controlGeneration: control.controlGeneration,
        reason: "conversation_recovery_ambiguous"
      });
      continue;
    }
    if (matches.length !== 1) continue;
    const candidate = matches[0];
    const mutation = await mutateState((currentState) => {
      if (currentState.conversations?.[control.conversationId]) {
        return { state: currentState, value: { recovered: false } };
      }
      const upserted = stateModel.upsertConversation(currentState, {
        url: candidate.url,
        label: candidate.label,
        enabled: control.enabled,
        preferredTabId: candidate.tabId,
        intervalOverrideMinutes: control.intervalMinutes,
        bootstrapPending: false,
        lastStatus: "github_control_recovered",
        lastRuntimeSource: runtime.source
      });
      const sameIdentity = upserted.conversation.id === control.conversationId;
      return {
        state: sameIdentity ? upserted.state : currentState,
        value: {
          recovered: sameIdentity,
          chatId: upserted.conversation.id,
          tabId: candidate.tabId
        }
      };
    });
    if (mutation.value?.recovered) {
      recovered.push({
        chatId: mutation.value.chatId,
        tabId: mutation.value.tabId,
        controlGeneration: control.controlGeneration
      });
    }
  }
  return { recovered, conflicts };
}

async function reconcileGithubConversationControlsOnce() {
  let state = await getBridgeState();
"""
)

replace_once(
    "chat_bridge/worker_github_control.js",
    """  const configured = runtime.conversationControls.length;
  const applied = await readAppliedGithubControls();
  const appliedNow = [];
  const conflicts = [];
""",
    """  const configured = runtime.conversationControls.length;
  const recovery = await recoverGithubControlledConversations(state, runtime);
  if (recovery.recovered.length) state = await getBridgeState();

  const applied = await readAppliedGithubControls();
  const appliedNow = [];
  const conflicts = [...recovery.conflicts];
"""
)

replace_once(
    "chat_bridge/worker_github_control.js",
    '  return { ok: true, reason: "reconciled", configured, applied: appliedNow, conflicts };\n',
    '''  return {
    ok: true,
    reason: "reconciled",
    configured,
    recovered: recovery.recovered,
    applied: appliedNow,
    conflicts
  };
'''
)

replace_once(
    "chat_bridge/worker_events.js",
    """  if (alarm.name === GITHUB_CONTROL_ALARM_NAME) {
    reconcileGithubConversationControls().then(() => pollConversationFabricCampaigns()).catch((error) => console.error(error));
    return;
  }
""",
    """  if (alarm.name === GITHUB_CONTROL_ALARM_NAME) {
    reconcileGithubConversationControls()
      .then(() => refreshConfiguredContentScripts().catch((error) => console.error(error)))
      .then(() => pollConversationFabricCampaigns())
      .catch((error) => console.error(error));
    return;
  }
"""
)

replace_once(
    "chat_bridge/github_control_hardening.test.js",
    """(async () => {
  // Concurrent reconciliation of one remote generation is serialized and applies once.
""",
    """(async () => {
  // A GitHub-controlled open conversation can recover from a cold/missing local Bridge record.
  {
    let control = null;
    const h = harnessWithControl(() => control);
    await new Promise((resolve) => setTimeout(resolve, 0));
    control = controlRecord();
    const result = await h.evaluate("reconcileGithubConversationControls()");
    const conversation = h.storage.bridgeState.conversations[chatId];
    assert.ok(conversation);
    assert.equal(conversation.url, url);
    assert.equal(conversation.preferredTabId, 11);
    assert.equal(conversation.bootstrapPending, false);
    assert.equal(result.recovered.length, 1);
    assert.equal(result.applied.length, 1);
  }

  // Recovery fails closed if the same controlled conversation is open twice.
  {
    let control = null;
    const h = harnessWithControl(() => control);
    h.tabs.push({ id: 44, url, title: "Duplicate Project A" });
    await new Promise((resolve) => setTimeout(resolve, 0));
    control = controlRecord();
    const result = await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(h.storage.bridgeState?.conversations?.[chatId], undefined);
    assert.equal(result.recovered.length, 0);
    assert.equal(result.applied.length, 0);
    assert.equal(result.conflicts[0].reason, "conversation_recovery_ambiguous");
  }

  // Concurrent reconciliation of one remote generation is serialized and applies once.
"""
)

replace_once(
    "chat_bridge/service_worker_races.test.js",
    """  // A missing content script is re-injected before delivery.
""",
    """  // GitHub cold-parent recovery plus content refresh restores a missing receiver.
  {
    const protocol = require("./control_protocol.js");
    const url = "https://chatgpt.com/c/a";
    const chatId = protocol.conversationId(url);
    let control = null;
    let probes = 0;
    const h = createHarness({
      fetch: async () => ({
        ok: true,
        async json() {
          return {
            schema_version: 3,
            interval_minutes: 10,
            busy_retry_minutes: 1,
            bootstrap_prompt: "BOOTSTRAP",
            wake_prompt: "WAKE",
            agents: h.runtimeAgents,
            conversation_controls: control ? [control] : []
          };
        }
      }),
      contentScriptProbe: async ({ injectedScripts }) => {
        probes += 1;
        const injected = injectedScripts.some((entry) =>
          Array.isArray(entry.files) && entry.files.includes("content.js")
        );
        if (!injected) throw new Error("Could not establish connection. Receiving end does not exist.");
        return {
          ok: true,
          reason: "ready",
          protocolVersion: h.CONTENT_PROTOCOL_VERSION,
          assistantIdentity: "fresh-assistant"
        };
      }
    });
    await new Promise((resolve) => setTimeout(resolve, 0));
    control = {
      conversation_id: chatId,
      control_generation: 1,
      enabled: true,
      interval_minutes: 5,
      next_wake_at: null,
      updated_at: new Date().toISOString()
    };
    const result = await h.evaluate(
      "(async () => { const reconcile = await reconcileGithubConversationControls(); const refresh = await refreshConfiguredContentScripts(); return { reconcile, refresh }; })()"
    );
    assert.equal(result.reconcile.recovered.length, 1);
    assert.equal(result.refresh.refreshed, 1);
    assert.equal(h.storage.bridgeState.conversations[chatId].preferredTabId, 11);
    assert.equal(normalContentInjections(h).length, 1);
    assert.ok(probes >= 2);
  }

  // A missing content script is re-injected before delivery.
"""
)
