/* Explicit operator-admitted, single-child private GitHub-first trial.
 *
 * GitHub is authoritative for immutable claim, browser ACK, and terminal result.
 * Only the existing MV3 worker may use private credentials. All child content
 * uses the existing scoped ChatGPT UI driver, never GitHub credentials.
 */
const privateFabricReader = globalThis.LocalAgentPrivateFabricTransport;
const privateFabricReceipts = globalThis.LocalAgentPrivateFabricReceipts;
const PRIVATE_FABRIC_RECORD_KEY = "privateFabricLiveTrialV1";
const PRIVATE_FABRIC_TOKEN_KEY = "privateFabricLiveTokenV1";
const PRIVATE_FABRIC_DRAFT_DISPATCH_KEY = "privateFabricDraftDispatchIdV1";
const PRIVATE_FABRIC_DISPATCH_RE = /^fabric-[0-9a-f]{32}$/;
const PRIVATE_FABRIC_TOKEN_RE = /^[A-Za-z0-9_-]{12,256}$/;
let privateFabricQueue = Promise.resolve();

function serializePrivateFabric(operation) {
  const result = privateFabricQueue.catch(() => undefined).then(operation);
  privateFabricQueue = result.catch(() => undefined);
  return result;
}

async function readPrivateFabricTrial() {
  const data = await chrome.storage.local.get(PRIVATE_FABRIC_RECORD_KEY);
  const record = data[PRIVATE_FABRIC_RECORD_KEY];
  return record && typeof record === "object" && !Array.isArray(record) ? record : null;
}

async function savePrivateFabricTrial(record) {
  await chrome.storage.local.set({ [PRIVATE_FABRIC_RECORD_KEY]: record });
  return record;
}

async function privateFabricToken() {
  const data = await chrome.storage.session.get(PRIVATE_FABRIC_TOKEN_KEY);
  return typeof data[PRIVATE_FABRIC_TOKEN_KEY] === "string"
    ? data[PRIVATE_FABRIC_TOKEN_KEY] : "";
}

async function privateFabricDraftStatus() {
  const [draft, token, trial] = await Promise.all([
    chrome.storage.local.get(PRIVATE_FABRIC_DRAFT_DISPATCH_KEY),
    privateFabricToken(),
    readPrivateFabricTrial()
  ]);
  return {
    ok: true,
    dispatchId: String(draft[PRIVATE_FABRIC_DRAFT_DISPATCH_KEY] || ""),
    tokenSaved: PRIVATE_FABRIC_TOKEN_RE.test(token),
    tokenLastFour: PRIVATE_FABRIC_TOKEN_RE.test(token) ? token.slice(-4) : "",
    trialPhase: trial?.phase || "disabled"
  };
}

async function operatorSavePrivateFabricDispatch(message) {
  const dispatchId = String(message?.dispatchId || "").trim();
  if (!PRIVATE_FABRIC_DISPATCH_RE.test(dispatchId)) {
    return { ok: false, reason: "invalid_private_dispatch_id" };
  }
  return serializePrivateFabric(async () => {
    const trial = await readPrivateFabricTrial();
    if (trial && trial.phase !== "retired" && trial.dispatch_id !== dispatchId) {
      return { ok: false, reason: "active_private_trial_dispatch_locked" };
    }
    await chrome.storage.local.set({ [PRIVATE_FABRIC_DRAFT_DISPATCH_KEY]: dispatchId });
    return privateFabricDraftStatus();
  });
}

async function operatorSavePrivateFabricToken(message) {
  const token = String(message?.writeToken || "").trim();
  if (!PRIVATE_FABRIC_TOKEN_RE.test(token)) {
    return { ok: false, reason: "invalid_private_repository_token" };
  }
  // The credential survives popup closure and MV3 worker suspension, not
  // browser shutdown or extension reload. Never copy it into local storage.
  await chrome.storage.session.set({ [PRIVATE_FABRIC_TOKEN_KEY]: token });
  return privateFabricDraftStatus();
}

async function operatorForgetPrivateFabricToken() {
  const trial = await readPrivateFabricTrial();
  if (trial && !["completed", "retired", "blocked", "claim_ambiguous"].includes(trial.phase)) {
    return { ok: false, reason: "active_private_trial_token_needed" };
  }
  await chrome.storage.session.remove(PRIVATE_FABRIC_TOKEN_KEY);
  return privateFabricDraftStatus();
}

async function privateFabricManagedParent(parentUrl) {
  const state = await getBridgeState();
  if (!state.settings.masterEnabled) return false;
  const chatId = conversationId(parentUrl);
  const parent = state.conversations?.[chatId];
  if (!parent || !parent.enabled || parent.url !== parentUrl) return false;
  if (parent.preferredTabId) {
    let tab;
    try { tab = await chrome.tabs.get(parent.preferredTabId); }
    catch (_error) { return false; }
    if (normalizeConversationUrl(tab?.url || "") !== parentUrl) return false;
  }
  const runtime = await fetchRuntime(state.settings, { fresh: true });
  if (runtime.source !== "remote") return false;
  const control = githubControlModel.findConversationControl(runtime, chatId);
  return Boolean(
    control?.enabled &&
    githubControlModel.controlMatchesConversation(control, parent)
  );
}

async function privateFabricBlockLegacyDelegate(message) {
  if (message?.control?.action !== "delegate") return false;
  const target = normalizeConversationUrl(String(message?.conversationUrl || ""));
  if (!target) return false;
  const trial = await readPrivateFabricTrial();
  return trial?.parent_url === target && trial.phase !== "retired";
}

// This layer is loaded AFTER the legacy controller but BEFORE worker_events.js.
// A fenced parent cannot enter the old DOM delegate path in this worker.
const legacyPrivateFabricDelegateHandler = applyConversationFabricControl;
applyConversationFabricControl = async function applyParentFencedFabricControl(message, sender) {
  if (await privateFabricBlockLegacyDelegate(message)) {
    return { ok: false, reason: "github_first_parent_fenced" };
  }
  return legacyPrivateFabricDelegateHandler(message, sender);
};

function privateFabricTrialSummary(record) {
  if (!record) return { active: false, phase: "disabled" };
  return {
    active: record.phase !== "retired",
    phase: record.phase,
    dispatchId: record.dispatch_id,
    childRequestId: record.child_request_id,
    childConversationUrl: record.child_url || "",
    resultPath: record.result_path || "",
    reason: record.reason || ""
  };
}

async function statusPrivateFabricTrial() {
  return { ok: true, ...privateFabricTrialSummary(await readPrivateFabricTrial()) };
}

async function privateFabricRecoverSubmission(record) {
  // No browser Send in recovery. This is safe for unknown/ambiguous first Send.
  let result;
  try { result = await reconcileConversationSpawn(record.intent); }
  catch (_error) { return record; }
  if (result?.ok && result.childConversationUrl) {
    record.child_url = result.childConversationUrl;
    record.phase = "ack_pending";
    await savePrivateFabricTrial(record);
  }
  return record;
}

async function privateFabricAdvance(record, token) {
  if (["completed", "retired", "blocked", "claim_ambiguous"].includes(record.phase)) {
    return record;
  }
  if (!await privateFabricManagedParent(record.parent_url)) {
    // A disabled or changed parent cannot generate new UI effects.
    return record;
  }
  if (record.phase === "preparing") {
    const claim = await privateFabricReceipts.claimBrowserChild({
      enabled: true, writeToken: token, dispatch: record.dispatch,
      childRequestId: record.child_request_id, ownerId: record.owner_id
    });
    if (claim.status === "ambiguous") {
      record.phase = "claim_ambiguous";
      record.reason = "claim_write_uncertain";
      return savePrivateFabricTrial(record);
    }
    record.phase = "claimed";
    await savePrivateFabricTrial(record);
  }
  if (record.phase === "claimed") {
    const created = await createConversationSpawnTab(record.intent);
    if (!created?.ok || !Number.isInteger(created.tabId)) {
      record.phase = "blocked";
      record.reason = "child_tab_not_confirmed";
      return savePrivateFabricTrial(record);
    }
    record.intent = { ...record.intent, tab_id: created.tabId };
    record.phase = "tab_ready";
    await savePrivateFabricTrial(record);
  }
  if (record.phase === "tab_ready") {
    // This is a read-only browser readiness check. The original tab, immutable
    // transaction and staged intent already exist, but Send is not yet armed.
    // Slow ChatGPT loading may be retried safely only BEFORE this boundary.
    let readiness;
    try { readiness = await ensureConversationSpawnContent(record.intent.tab_id); }
    catch (_error) {
      record.reason = "pre_submit_content_unavailable";
      return savePrivateFabricTrial(record);
    }
    if (!readiness?.ok || readiness.route !== "fresh" ||
        readiness.readiness?.ok !== true) {
      const code = String(readiness?.readiness?.reason || readiness?.reason || "not_ready");
      // Never carry a page-origin string or private prompt into diagnostics.
      const known = new Set([
        "spawn_composer_not_found", "spawn_page_not_ready",
        "spawn_assistant_busy", "spawn_composer_not_empty",
        "spawn_content_unavailable", "spawn_content_protocol_mismatch",
        "spawn_unexpected_route", "spawn_ready"
      ]);
      record.reason = "pre_submit_" + (known.has(code) ? code : "not_ready");
      return savePrivateFabricTrial(record);
    }
    record.reason = "";
    // Persist the unknown-send fence BEFORE calling any UI Submit.
    // After interruption, reconciliation NEVER attempts another Submit.
    record.phase = "submission_unknown";
    await savePrivateFabricTrial(record);
    let submitted;
    try { submitted = await submitConversationSpawnBootstrap(record.intent); }
    catch (_error) { submitted = null; }
    if (submitted?.ok && submitted.childConversationUrl) {
      record.child_url = submitted.childConversationUrl;
      record.phase = "ack_pending";
      await savePrivateFabricTrial(record);
    } else {
      // Preserve a bounded failure code without ever exposing private bootstrap.
      const failure = String(submitted?.reason || "");
      const safeCodes = new Set([
        "spawn_composer_not_found", "spawn_page_not_ready",
        "spawn_send_button_not_ready", "spawn_composer_write_failed",
        "spawn_composer_changed", "spawn_content_unavailable",
        "spawn_content_protocol_mismatch", "spawn_submission_ambiguous",
        "spawn_v2_claim_exists", "spawn_unexpected_route"
      ]);
      record.reason = "send_uncertain_reconciliation_only" +
        (safeCodes.has(failure) ? ":" + failure : "");
      await savePrivateFabricTrial(record);
    }
  }
  if (record.phase === "submission_unknown") {
    await privateFabricRecoverSubmission(record);
  }
  if (record.phase === "ack_pending") {
    const ack = await privateFabricReceipts.publishBrowserAck({
      enabled: true, writeToken: token, dispatch: record.dispatch,
      childRequestId: record.child_request_id,
      childConversationUrl: record.child_url
    });
    if (ack.status !== "ambiguous") {
      record.phase = "running";
      record.reason = "";
      await savePrivateFabricTrial(record);
    }
  }
  if (record.phase === "running") {
    const child = { intent: record.intent };
    let observed;
    try { observed = await stableConversationFabricResult(child); }
    catch (_error) { return record; }
    if (observed?.ok && observed.reason === "child_result_ready" &&
        observed.childConversationUrl === record.child_url) {
      record.assistant_identity = String(observed.assistantIdentity || "");
      record.assistant_text = String(observed.assistantText || "").slice(0, 6000);
      record.phase = "result_pending";
      await savePrivateFabricTrial(record);
    }
  }
  if (record.phase === "result_pending") {
    const result = await privateFabricReceipts.publishBrowserResult({
      enabled: true, writeToken: token,
      dispatch: record.dispatch, childRequestId: record.child_request_id,
      childConversationUrl: record.child_url,
      assistantIdentity: record.assistant_identity,
      assistantText: record.assistant_text
    });
    if (result.status !== "ambiguous") {
      record.result_path = result.path;
      record.phase = "completed";
      record.reason = "";
      await savePrivateFabricTrial(record);
      await chrome.storage.session.remove(PRIVATE_FABRIC_TOKEN_KEY);
    }
  }
  return record;
}

async function operatorStartPrivateFabricTrial(message) {
  // Only worker_events.js exposes this method to the verified extension popup.
  const rawId = String(message?.dispatchId || "").trim();
  const rawToken = String(message?.writeToken || "").trim();
  return serializePrivateFabric(async () => {
    const stored = await chrome.storage.local.get(PRIVATE_FABRIC_DRAFT_DISPATCH_KEY);
    const dispatchId = rawId || String(stored[PRIVATE_FABRIC_DRAFT_DISPATCH_KEY] || "");
    const token = rawToken || await privateFabricToken();
    if (!PRIVATE_FABRIC_DISPATCH_RE.test(dispatchId) ||
        !PRIVATE_FABRIC_TOKEN_RE.test(token)) {
      return { ok: false, reason: "invalid_private_dispatch_launch" };
    }
    const prior = await readPrivateFabricTrial();
    if (prior && prior.phase !== "retired" && prior.dispatch_id !== dispatchId) {
      return { ok: false, reason: "another_private_trial_requires_reconciliation",
        ...privateFabricTrialSummary(prior) };
    }
    if (prior && prior.phase !== "retired") {
      await chrome.storage.session.set({ [PRIVATE_FABRIC_TOKEN_KEY]: token });
      await privateFabricAdvance(prior, token);
      return { ok: true, ...privateFabricTrialSummary(await readPrivateFabricTrial()) };
    }
    const snapshot = await privateFabricReader.readPrivateDispatchSnapshot({
      enabled: true, readToken: token, expectedId: dispatchId,
      projectId: "local-agent", workflowId: "workflow-001"
    });
    const dispatch = snapshot.dispatch;
    if (dispatch.children.length !== 1 ||
        !await privateFabricManagedParent(dispatch.parent_conversation_url)) {
      return { ok: false, reason: "private_dispatch_parent_or_child_not_authorized" };
    }
    const legacy = await listConversationFabricCampaigns();
    if (legacy.some(item =>
      item.parent_conversation_url === dispatch.parent_conversation_url &&
      (["running", "spawning"].includes(item.state) ||
       item.cleanup_pending || item.feedback_delivery_assumed ||
       (item.feedback_delivery_claim?.state &&
        item.feedback_delivery_claim.state !== "confirmed")))) {
      return { ok: false, reason: "legacy_parent_has_unresolved_campaign" };
    }
    const child = dispatch.children[0];
    const intent = githubFabricDispatchModel.toConversationSpawnIntent(child);
    await requireConversationSpawnBootstrapDigest(intent);
    // Explicit operator intent + local parent fence persist BEFORE claim/tab/Send.
    const record = {
      version: 1, phase: "preparing", reason: "",
      dispatch_id: dispatch.id,
      source_head_sha: snapshot.source_head_sha,
      parent_url: dispatch.parent_conversation_url,
      child_request_id: child.request_id,
      owner_id: crypto.randomUUID().replace(/-/g, "").toLowerCase(),
      child_url: "", result_path: "",
      intent, dispatch
    };
    await savePrivateFabricTrial(record);
    await chrome.storage.session.set({ [PRIVATE_FABRIC_TOKEN_KEY]: token });
    await privateFabricAdvance(record, token);
    return { ok: true, ...privateFabricTrialSummary(await readPrivateFabricTrial()) };
  });
}

async function pollPrivateFabricTrial() {
  return serializePrivateFabric(async () => {
    const record = await readPrivateFabricTrial();
    if (!record || ["completed", "retired", "blocked", "claim_ambiguous"].includes(record.phase)) {
      return privateFabricTrialSummary(record);
    }
    const token = await privateFabricToken();
    if (!token) return { ...privateFabricTrialSummary(record), reason: "private_token_not_in_session" };
    try { await privateFabricAdvance(record, token); }
    catch (_error) {
      // Never log token-bearing request or private prompt.
      return { ...privateFabricTrialSummary(record), reason: "private_transport_needs_reconciliation" };
    }
    return privateFabricTrialSummary(await readPrivateFabricTrial());
  });
}

async function retirePrivateFabricTrial() {
  return serializePrivateFabric(async () => {
    const record = await readPrivateFabricTrial();
    if (!record || record.phase !== "completed") {
      return { ok: false, reason: "only_confirmed_completed_trial_can_rollback" };
    }
    record.phase = "retired";
    await savePrivateFabricTrial(record);
    await chrome.storage.session.remove(PRIVATE_FABRIC_TOKEN_KEY);
    return { ok: true, ...privateFabricTrialSummary(record) };
  });
}
