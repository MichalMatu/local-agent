const conversationFabricProtocol = globalThis.LocalAgentConversationFabricProtocol;
if (!conversationFabricProtocol) {
  throw new Error("Conversation Fabric protocol is unavailable in the service worker");
}

const CONVERSATION_FABRIC_CAMPAIGN_PREFIX = "conversation-fabric-campaign:";
const CONVERSATION_FABRIC_RESULT_PREFIX = "conversation-fabric-result:";
const CONVERSATION_FABRIC_RESULT_CHARS = 6_000;
const CONVERSATION_FABRIC_VAULT_RESULT_CHARS = 24_000;
const CONVERSATION_FABRIC_VAULT_HISTORY_LIMIT = 192;
const CONVERSATION_FABRIC_INSPECT_RECENT_LIMIT = 12;
const CONVERSATION_FABRIC_SUBMIT_RETRIES = 5;
const CONVERSATION_FABRIC_SUBMIT_RETRY_BASE_MS = 350;
const CONVERSATION_FABRIC_SUBMIT_RETRY_MAX_MS = 2_800;
const CONVERSATION_FABRIC_TIMEOUT_MS = 15 * 60 * 1000;
const CONVERSATION_FABRIC_HISTORY_LIMIT = 32;
const conversationFabricOperations = new Map();

function serializeConversationFabric(parentUrl, operation) {
  const previous = conversationFabricOperations.get(parentUrl) || Promise.resolve();
  const pending = previous.catch(() => undefined).then(operation);
  conversationFabricOperations.set(parentUrl, pending);
  return pending.finally(() => {
    if (conversationFabricOperations.get(parentUrl) === pending) conversationFabricOperations.delete(parentUrl);
  });
}

async function listConversationFabricCampaigns() {
  const stored = await chrome.storage.local.get(null);
  return Object.entries(stored).filter(([key, value]) =>
    key.startsWith(CONVERSATION_FABRIC_CAMPAIGN_PREFIX) && value?.schema_version === 1
  ).map(([, value]) => value);
}

const CONVERSATION_FABRIC_TRANSIENT_SPAWN_REASONS = new Set([
  "spawn_page_not_ready",
  "spawn_composer_not_found",
  "spawn_send_button_not_ready",
  "spawn_content_unavailable"
]);
const CONVERSATION_FABRIC_AMBIGUOUS_CHILD_STATE = "submission_ambiguous";
const CONVERSATION_FABRIC_AMBIGUOUS_HARD_FAILURE_REASONS = new Set([
  "spawn_claim_conflict",
  "spawn_child_identity_invalid",
  "spawn_intent_invalid"
]);
const CONVERSATION_FABRIC_EXPLICIT_RETRYABLE_FAILURE_REASONS = new Set([
  "operator_retired",
  "spawn_tab_unavailable",
  "spawn_page_not_ready",
  "spawn_composer_not_found",
  "spawn_send_button_not_ready",
  "spawn_content_unavailable",
  "spawn_interrupted_before_submission",
  "spawn_interrupted_after_tab_creation",
  "spawn_submission_ambiguous_timeout",
  "child_result_unavailable"
]);

function conversationFabricCampaignKey(campaignId) {
  if (!conversationFabricProtocol.CAMPAIGN_ID_RE.test(String(campaignId || ""))) {
    throw new Error("invalid Conversation Fabric campaign id");
  }
  return `${CONVERSATION_FABRIC_CAMPAIGN_PREFIX}${campaignId}`;
}

async function loadConversationFabricCampaign(campaignId) {
  const key = conversationFabricCampaignKey(campaignId);
  const stored = await chrome.storage.local.get(key);
  const value = stored?.[key];
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

async function saveConversationFabricCampaign(campaign, { allowDeliveryClaimMutation = false } = {}) {
  const key = conversationFabricCampaignKey(campaign.id);
  return serializeConversationFabric(key, async () => {
    const stored = await loadConversationFabricCampaign(campaign.id);
    // Cleanup/operator recovery can race with terminal delivery. Preserve the durable
    // at-most-once boundary unless the delivery-guard path explicitly owns claim mutation.
    if (stored?.state === campaign.state && stored.feedback_delivered) {
      campaign.feedback_delivered = true;
      campaign.feedback_delivered_at = campaign.feedback_delivered_at || stored.feedback_delivered_at;
    }
    if (!allowDeliveryClaimMutation) {
      if (stored?.feedback_delivery_claim?.id) {
        campaign.feedback_delivery_claim = stored.feedback_delivery_claim;
      } else {
        delete campaign.feedback_delivery_claim;
      }
      if (stored?.feedback_delivery_assumed === true) {
        campaign.feedback_delivery_assumed = true;
      } else {
        delete campaign.feedback_delivery_assumed;
      }
      if (stored?.feedback_delivery_assumed_at) {
        campaign.feedback_delivery_assumed_at = stored.feedback_delivery_assumed_at;
      } else {
        delete campaign.feedback_delivery_assumed_at;
      }
    }
    await chrome.storage.local.set({ [key]: campaign });
    return campaign;
  });
}

function conversationFabricVaultKey(campaignId, childId) {
  if (!conversationFabricProtocol.CAMPAIGN_ID_RE.test(String(campaignId || ""))) {
    throw new Error("invalid Conversation Fabric vault campaign id");
  }
  if (!conversationFabricProtocol.CHILD_ID_RE.test(String(childId || ""))) {
    throw new Error("invalid Conversation Fabric vault child id");
  }
  return `${CONVERSATION_FABRIC_RESULT_PREFIX}${campaignId}:${childId}`;
}

async function listConversationFabricVaultResults() {
  const stored = await chrome.storage.local.get(null);
  return Object.entries(stored).filter(([key, value]) =>
    key.startsWith(CONVERSATION_FABRIC_RESULT_PREFIX) && value?.schema_version === 1
  ).map(([, value]) => value);
}

async function loadConversationFabricVaultResult(campaignId, childId) {
  const key = conversationFabricVaultKey(campaignId, childId);
  const stored = await chrome.storage.local.get(key);
  const value = stored?.[key];
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

async function saveConversationFabricVaultResult(campaign, child, observed, { capturedAt = "" } = {}) {
  const fullText = String(observed?.assistantText || "");
  const assistantText = fullText.slice(0, CONVERSATION_FABRIC_VAULT_RESULT_CHARS);
  const key = conversationFabricVaultKey(campaign.id, child.id);
  const existing = await loadConversationFabricVaultResult(campaign.id, child.id);
  const storedCapturedAt = String(existing?.captured_at || capturedAt || new Date().toISOString());
  const record = {
    schema_version: 1,
    campaign_id: campaign.id,
    child_id: child.id,
    role: child.role,
    parent_conversation_url: campaign.parent_conversation_url,
    child_conversation_url: String(child.child_conversation_url || observed?.childConversationUrl || ""),
    assistant_identity: String(observed?.assistantIdentity || ""),
    captured_at: storedCapturedAt,
    assistant_text: assistantText,
    truncated: observed?.truncated === true || fullText.length > CONVERSATION_FABRIC_VAULT_RESULT_CHARS,
    campaign_text_truncated: fullText.length > CONVERSATION_FABRIC_RESULT_CHARS,
    text_sha256: await conversationSpawnSha256(assistantText)
  };
  await chrome.storage.local.set({ [key]: record });

  const all = (await listConversationFabricVaultResults())
    .sort((left, right) => String(right.captured_at || "").localeCompare(String(left.captured_at || "")));
  for (const old of all.slice(CONVERSATION_FABRIC_VAULT_HISTORY_LIMIT)) {
    await chrome.storage.local.remove(conversationFabricVaultKey(old.campaign_id, old.child_id));
  }
  return record;
}

function conversationFabricCampaignResultFromVault(vaulted) {
  const text = String(vaulted?.assistant_text || "");
  return {
    id: String(vaulted?.child_id || ""),
    role: String(vaulted?.role || ""),
    child_conversation_url: String(vaulted?.child_conversation_url || ""),
    assistant_identity: String(vaulted?.assistant_identity || ""),
    assistant_text: text.slice(0, CONVERSATION_FABRIC_RESULT_CHARS),
    truncated: vaulted?.truncated === true ||
      vaulted?.campaign_text_truncated === true ||
      text.length > CONVERSATION_FABRIC_RESULT_CHARS,
    captured_at: String(vaulted?.captured_at || ""),
    vault_sha256: String(vaulted?.text_sha256 || "")
  };
}

async function backfillConversationFabricCampaignResults(campaign) {
  let created = 0;
  for (const result of campaign?.results || []) {
    const child = (campaign.children || []).find((value) => value.id === result.id) || {
      id: result.id,
      role: result.role,
      child_conversation_url: result.child_conversation_url
    };
    if (!child?.id || await loadConversationFabricVaultResult(campaign.id, child.id)) continue;
    await saveConversationFabricVaultResult(campaign, child, {
      assistantText: String(result.assistant_text || ""),
      assistantIdentity: String(result.assistant_identity || ""),
      childConversationUrl: String(result.child_conversation_url || ""),
      truncated: result.truncated === true
    }, {
      capturedAt: String(result.captured_at || "")
    });
    created += 1;
  }
  return created;
}

async function hydrateConversationFabricResultsFromVault(campaign) {
  const vaulted = (await listConversationFabricVaultResults()).filter((result) =>
    result.campaign_id === campaign.id &&
    result.parent_conversation_url === campaign.parent_conversation_url
  );
  let changed = false;
  campaign.results = Array.isArray(campaign.results) ? campaign.results : [];
  for (const result of vaulted) {
    if (campaign.results.some((stored) => stored.id === result.child_id)) continue;
    const child = (campaign.children || []).find((value) => value.id === result.child_id);
    if (!child) continue;
    campaign.results.push(conversationFabricCampaignResultFromVault(result));
    child.result_captured = true;
    child.result_captured_at = String(result.captured_at || child.result_captured_at || "");
    changed = true;
  }
  if (changed) await saveConversationFabricCampaign(campaign);
  return changed;
}

function conversationFabricControlBlock(control) {
  return [
    "<<<LOCAL_AGENT_CF",
    JSON.stringify({
      schema_version: conversationFabricProtocol.SCHEMA_VERSION,
      ...control
    }),
    "LOCAL_AGENT_CF>>>"
  ].join("\n");
}

function conversationFabricCollectBlock(campaignId) {
  return conversationFabricControlBlock({ action: "collect", campaign_id: campaignId });
}

function conversationFabricInspectBlock(campaignId, childId = "") {
  return conversationFabricControlBlock({
    action: "inspect",
    campaign_id: campaignId,
    ...(childId ? { child_id: childId } : {})
  });
}

function conversationFabricRetireBlock(campaignId, childId) {
  return conversationFabricControlBlock({
    action: "retire",
    campaign_id: campaignId,
    child_id: childId
  });
}

function conversationFabricNextWakeInstruction(campaignId) {
  return [
    "Bridge collects child results on its existing GitHub control poll while this parent is enabled.",
    "Wait for result feedback. Do not invent child results or create another delegation for the same work.",
    "For a read-only status/result check, end a later parent reply with this exact inspect block:",
    conversationFabricInspectBlock(campaignId),
    "To force one bounded observation pass of already-submitted children, use collect instead:",
    conversationFabricCollectBlock(campaignId)
  ].join("\n\n");
}

function conversationFabricChildFailure(child) {
  const detail = child?.failure && typeof child.failure === "object" ? child.failure : {};
  const reason = String(detail.reason || child?.last_reason || "unknown");
  return {
    id: String(child?.id || ""),
    role: String(child?.role || ""),
    attempt: Number.isInteger(detail.attempt) ? detail.attempt : Number(child?.attempts || 0),
    reason,
    error: String(detail.error || child?.last_error || ""),
    retryable: detail.retryable === true || CONVERSATION_FABRIC_EXPLICIT_RETRYABLE_FAILURE_REASONS.has(reason)
  };
}

function conversationFabricFailedChildren(campaign) {
  const stored = Array.isArray(campaign?.failed_children) ? campaign.failed_children : [];
  if (stored.length) {
    return stored.map((failure) => {
      const reason = String(failure?.reason || "unknown");
      return {
        id: String(failure?.id || ""),
        role: String(failure?.role || ""),
        attempt: Number.isInteger(failure?.attempt) ? failure.attempt : 0,
        reason,
        error: String(failure?.error || ""),
        retryable: failure?.retryable === true ||
          CONVERSATION_FABRIC_EXPLICIT_RETRYABLE_FAILURE_REASONS.has(reason)
      };
    });
  }
  return (campaign?.children || [])
    .filter((child) => child?.state === "failed")
    .map(conversationFabricChildFailure);
}

function conversationFabricFailureSummary(failure) {
  const attempt = Number.isInteger(failure.attempt) && failure.attempt > 0
    ? ` after attempt ${failure.attempt}`
    : "";
  const retryable = failure.retryable ? " [retryable]" : "";
  const detail = failure.error ? ` (${failure.error})` : "";
  return `${failure.id || "unknown"}: ${failure.reason || "unknown"}${attempt}${retryable}${detail}`;
}

function conversationFabricPendingPrompt(campaign, pendingIds) {
  const failures = conversationFabricFailedChildren(campaign);
  const pendingChildren = pendingIds
    .map((id) => (campaign.children || []).find((child) => child.id === id))
    .filter(Boolean);
  const pendingStatus = pendingChildren.map((child) => conversationFabricChildStatusLine(child, campaign));
  const retireControls = pendingChildren.map((child) => [
    `If you intentionally decide child ${child.id} is stuck and should be abandoned, use this exact retire control. Do not retire a child you still want to wait for:`,
    conversationFabricRetireBlock(campaign.id, child.id)
  ].join("\n\n"));
  return [
    `Conversation Fabric campaign ${campaign.id} is still running in child tabs: ${pendingIds.join(", ")}.`,
    pendingStatus.length ? `Pending child diagnostics:\n${pendingStatus.join("\n")}` : "",
    failures.length
      ? `Child startup/observation failures already recorded: ${failures.map(conversationFabricFailureSummary).join("; ")}. These children will not be replayed automatically.`
      : "",
    ...retireControls,
    "Do not synthesize the delegated work yet unless the campaign becomes terminal.",
    conversationFabricNextWakeInstruction(campaign.id)
  ].filter(Boolean).join("\n\n");
}

function conversationFabricStartedPrompt(campaign) {
  const submitted = campaign.children.filter((child) => child.state === "submitted");
  const ambiguous = campaign.children.filter(
    (child) => child.state === CONVERSATION_FABRIC_AMBIGUOUS_CHILD_STATE
  );
  const admitted = [...submitted, ...ambiguous];
  const failures = conversationFabricFailedChildren(campaign);
  const ids = admitted.map((child) => child.id).join(", ");
  return [
    `Conversation Fabric started ${admitted.length}/${campaign.children.length} reasoning child tab(s) in this Chrome session${ids ? `: ${ids}` : "."}`,
    `Campaign id: ${campaign.id}.`,
    ambiguous.length
      ? `Route/identity confirmation is still pending for: ${ambiguous.map((child) => child.id).join(", ")}. Bridge will reconcile these existing tabs without replaying their bootstrap.`
      : "",
    failures.length
      ? `Child startup failures: ${failures.map(conversationFabricFailureSummary).join("; ")}. Continue with the children that started; failed children will be reported as missing coverage and will not be replayed automatically.`
      : "",
    "Do not synthesize the delegated work yet.",
    conversationFabricNextWakeInstruction(campaign.id)
  ].filter(Boolean).join("\n\n");
}

function conversationFabricCompletedPrompt(campaign) {
  const failures = conversationFabricFailedChildren(campaign);
  const retryableFailures = failures.filter((failure) => failure.retryable);
  const sections = campaign.results.map((result) => [
    `--- child ${result.id} (${result.role})${result.truncated ? " [truncated]" : ""} ---`,
    result.assistant_text
  ].join("\n"));
  const failedSections = failures.map((failure) => [
    `--- child ${failure.id} (${failure.role || "unknown"}) FAILED ---`,
    `reason=${failure.reason || "unknown"}`,
    failure.attempt ? `attempt=${failure.attempt}` : "",
    failure.error ? `error=${failure.error}` : ""
  ].filter(Boolean).join("\n"));
  return [
    failures.length
      ? `Conversation Fabric campaign ${campaign.id} completed with partial child failures.`
      : `Conversation Fabric campaign ${campaign.id} completed.`,
    campaign.cleanup_pending ? "Results are saved; some owned child tabs still require cleanup." : "Owned child tabs were closed after stable result capture.",
    ...sections,
    ...failedSections,
    retryableFailures.length
      ? `Retryable missing child coverage: ${retryableFailures.map((failure) => failure.id).join(", ")}. You may intentionally delegate that bounded work again in a new campaign with new child ids. Bridge will never replay it automatically.`
      : "",
    "Captured child work is retained in the Conversation Fabric Result Vault. Read-only recovery for this campaign:",
    conversationFabricInspectBlock(campaign.id),
    failures.length
      ? "Synthesize the final parent answer from the available results and explicitly report the missing child coverage. Do not invent or automatically replay failed child work."
      : "Synthesize the final parent answer now. Do not delegate machine execution to a child."
  ].filter(Boolean).join("\n\n");
}

function conversationFabricChildStatusLine(child, campaign) {
  const stored = (campaign.results || []).find((result) => result.id === child.id);
  const failure = child.state === "failed" ? conversationFabricChildFailure(child) : null;
  const parts = [
    `child=${child.id}`,
    `role=${child.role}`,
    `state=${child.state}`,
    stored || child.result_captured ? "result=captured" : "result=pending"
  ];
  if (child.child_conversation_url) parts.push(`url=${child.child_conversation_url}`);
  if (child.last_observation_reason) parts.push(`observation=${child.last_observation_reason}`);
  if (child.last_reason) parts.push(`reason=${child.last_reason}`);
  if (failure?.retryable) parts.push("retryable=true");
  return parts.join(" ");
}

function boundedConversationFabricInspectPrompt(text) {
  const source = String(text || "");
  return source.length > 30_000 ? `${source.slice(0, 30_000)}\n\n[inspect output truncated]` : source;
}

async function inspectConversationFabric(authority) {
  const campaignId = String(authority.control.campaign_id || "");
  const childId = String(authority.control.child_id || "");
  const campaigns = (await listConversationFabricCampaigns())
    .filter((campaign) => campaign.parent_conversation_url === authority.conversationUrl)
    .sort((left, right) => String(right.created_at || "").localeCompare(String(left.created_at || "")));
  const vault = (await listConversationFabricVaultResults())
    .filter((result) => result.parent_conversation_url === authority.conversationUrl)
    .sort((left, right) => String(right.captured_at || "").localeCompare(String(left.captured_at || "")));

  if (!campaignId) {
    const recent = campaigns.slice(0, CONVERSATION_FABRIC_INSPECT_RECENT_LIMIT);
    const known = new Set(recent.map((campaign) => campaign.id));
    const vaultOnly = [];
    for (const result of vault) {
      if (known.has(result.campaign_id) || vaultOnly.some((item) => item.campaign_id === result.campaign_id)) continue;
      vaultOnly.push(result);
      if (recent.length + vaultOnly.length >= CONVERSATION_FABRIC_INSPECT_RECENT_LIMIT) break;
    }
    const lines = recent.map((campaign) =>
      `${campaign.id} state=${campaign.state} created=${campaign.created_at} results=${(campaign.results || []).length}/${(campaign.children || []).length} failures=${conversationFabricFailedChildren(campaign).length}`
    );
    lines.push(...vaultOnly.map((result) =>
      `${result.campaign_id} state=vault-only captured=${result.captured_at} latest_child=${result.child_id}`
    ));
    return {
      ok: true,
      reason: "conversation_fabric_inspect",
      feedbackPrompt: boundedConversationFabricInspectPrompt([
        "Conversation Fabric recent campaigns/results:",
        lines.length ? lines.join("\n") : "No recent Conversation Fabric campaign or vaulted result is available for this parent.",
        "Use inspect with a campaign_id for child states and result metadata."
      ].join("\n\n"))
    };
  }

  const campaign = campaigns.find((value) => value.id === campaignId) || null;
  const campaignVault = vault.filter((result) => result.campaign_id === campaignId);
  if (!campaign && !campaignVault.length) {
    return { ok: false, reason: "conversation_fabric_campaign_missing" };
  }

  if (childId) {
    const vaulted = campaignVault.find((result) => result.child_id === childId) || null;
    const campaignResult = (campaign?.results || []).find((result) => result.id === childId) || null;
    const child = (campaign?.children || []).find((value) => value.id === childId) || null;
    if (!vaulted && !campaignResult && !child) {
      return { ok: false, reason: "conversation_fabric_child_missing" };
    }
    const text = String(vaulted?.assistant_text || campaignResult?.assistant_text || "");
    return {
      ok: true,
      reason: "conversation_fabric_inspect",
      campaignId,
      childId,
      feedbackPrompt: boundedConversationFabricInspectPrompt([
        `Conversation Fabric result inspection: campaign=${campaignId} child=${childId}`,
        child && campaign ? conversationFabricChildStatusLine(child, campaign) : "state=vault-only",
        vaulted
          ? `vault captured_at=${vaulted.captured_at} sha256=${vaulted.text_sha256} truncated=${vaulted.truncated} source=${vaulted.child_conversation_url}`
          : "vault=missing; showing campaign copy",
        text ? `--- recovered child result ---\n${text}` : "No captured result text is available for this child."
      ].join("\n\n"))
    };
  }

  const childLines = campaign
    ? (campaign.children || []).map((child) => conversationFabricChildStatusLine(child, campaign))
    : [];
  const vaultLines = campaignVault.map((result) =>
    `child=${result.child_id} captured=${result.captured_at} sha256=${result.text_sha256} chars=${String(result.assistant_text || "").length} truncated=${result.truncated} source=${result.child_conversation_url}`
  );
  const excerpts = campaignVault.map((result) => {
    const text = String(result.assistant_text || "");
    return `--- child ${result.child_id} vault excerpt ---\n${text.slice(0, 1200)}${text.length > 1200 ? "\n[use child-scoped inspect for more]" : ""}`;
  });
  return {
    ok: true,
    reason: "conversation_fabric_inspect",
    campaignId,
    feedbackPrompt: boundedConversationFabricInspectPrompt([
      `Conversation Fabric campaign inspection: ${campaignId}`,
      campaign ? `state=${campaign.state} created=${campaign.created_at} completed=${campaign.completed_at || ""} feedback_delivered=${campaign.feedback_delivered === true} cleanup_pending=${campaign.cleanup_pending === true}` : "campaign record pruned; Result Vault remains",
      childLines.length ? childLines.join("\n") : "No live campaign child records remain.",
      vaultLines.length ? `Vault records:\n${vaultLines.join("\n")}` : "No vaulted child results are available.",
      ...excerpts
    ].join("\n\n"))
  };
}

function validateConversationFabricMessage(message, sender) {
  if (
    sender?.id !== chrome.runtime.id ||
    sender?.frameId !== 0 ||
    !Number.isInteger(sender?.tab?.id)
  ) {
    throw new Error("Conversation Fabric control requires the top-frame Bridge content script");
  }
  const conversationUrl = normalizeConversationUrl(String(message?.conversationUrl || ""));
  const senderUrl = normalizeConversationUrl(String(sender.tab.url || ""));
  if (!conversationUrl || senderUrl !== conversationUrl) {
    throw new Error("Conversation Fabric control sender does not match the parent conversation");
  }
  if (message?.contentProtocolVersion !== CONTENT_PROTOCOL_VERSION) {
    throw new Error("Conversation Fabric content protocol mismatch");
  }
  const assistantIdentity = String(message?.assistantIdentity || "");
  if (!assistantIdentity || assistantIdentity.length > 256) {
    throw new Error("Conversation Fabric assistant identity is invalid");
  }
  const fingerprint = String(message?.fingerprint || "");
  if (!/^[0-9a-f]{8}$/.test(fingerprint)) {
    throw new Error("Conversation Fabric fingerprint is invalid");
  }
  const marker = message?.control?.marker;
  const candidate = marker === undefined
    ? message?.control
    : Object.fromEntries(Object.entries(message.control).filter(([key]) => key !== "marker"));
  const control = conversationFabricProtocol.validateControl(candidate);
  if (!control) throw new Error("Conversation Fabric control is invalid");
  return {
    conversationUrl,
    parentTabId: sender.tab.id,
    assistantIdentity,
    fingerprint,
    control
  };
}

async function conversationFabricManagedParent(authority) {
  const state = await getBridgeState();
  const parent = state.conversations?.[conversationId(authority.conversationUrl)] || null;
  if (!state.settings.masterEnabled || !parent?.enabled || parent.url !== authority.conversationUrl) return null;
  if (
    parent.preferredTabId !== null &&
    parent.preferredTabId !== undefined &&
    parent.preferredTabId !== authority.parentTabId
  ) {
    return null;
  }
  return parent;
}

async function conversationFabricCampaignId(authority) {
  const payload = JSON.stringify([
    authority.conversationUrl,
    authority.assistantIdentity,
    authority.fingerprint,
    authority.control.children || []
  ]);
  const digest = await conversationSpawnSha256(payload);
  return `cf-${digest.slice(0, 16)}`;
}

function conversationFabricBootstrapText(authority, campaignId, child) {
  return [
    "LOCAL AGENT BROWSER CHILD",
    `parent_conversation=${authority.conversationUrl}`,
    `campaign_id=${campaignId}`,
    `child_id=${child.id}`,
    `role=${child.role}`,
    "",
    "You are a reasoning-only child of one parent conversation.",
    "Do not create Local Agent tasks, run machine commands, mutate repositories, or make the final parent decision.",
    "Work only on the bounded task below and return a concise result with evidence useful to the parent.",
    "",
    "TASK",
    child.prompt
  ].join("\n");
}

async function conversationFabricIntent(authority, campaignId, child) {
  const bootstrapText = conversationFabricBootstrapText(authority, campaignId, child);
  const transactionDigest = await conversationSpawnSha256(`${campaignId}\n${child.id}`);
  const requestDigest = await conversationSpawnSha256(JSON.stringify([
    authority.conversationUrl,
    campaignId,
    child.id,
    child.role,
    child.prompt
  ]));
  const bootstrapDigest = await conversationSpawnSha256(bootstrapText);
  return {
    schema_version: CONVERSATION_SPAWN_BROWSER_SCHEMA_VERSION,
    transaction_id: `spawn-${transactionDigest}`,
    child_request_digest: `sha256:${requestDigest}`,
    bootstrap_digest: `sha256:${bootstrapDigest}`,
    bootstrap_text: bootstrapText,
    tab_id: null
  };
}

function conversationFabricSpawnError(message, reason, attempt = 0, error = "") {
  const failure = new Error(message);
  failure.reason = String(reason || "unknown");
  failure.attempt = Number.isInteger(attempt) ? attempt : 0;
  failure.detail = String(error || "");
  return failure;
}

function conversationFabricRetryDelay(attempt) {
  return Math.min(
    CONVERSATION_FABRIC_SUBMIT_RETRY_MAX_MS,
    CONVERSATION_FABRIC_SUBMIT_RETRY_BASE_MS * (2 ** Math.max(0, attempt - 1))
  );
}

async function submitConversationFabricChild(intent, checkpoint) {
  let created;
  try {
    created = await createConversationSpawnTab(intent);
  } catch (error) {
    throw conversationFabricSpawnError(
      `Conversation Fabric child tab creation failed: ${String(error)}`,
      "spawn_tab_creation_exception",
      0,
      String(error)
    );
  }
  if (!created?.ok || !Number.isInteger(created.tabId)) {
    throw conversationFabricSpawnError(
      `Conversation Fabric child tab creation failed: ${created?.reason || "unknown"}`,
      created?.reason || "spawn_tab_creation_failed",
      0,
      created?.error || ""
    );
  }

  const activeIntent = { ...intent, tab_id: created.tabId };
  await checkpoint(activeIntent, "tab_created", {
    attempts: 0,
    last_reason: "",
    last_error: ""
  });

  let lastReason = "";
  let lastError = "";
  for (let attempt = 1; attempt <= CONVERSATION_FABRIC_SUBMIT_RETRIES + 1; attempt += 1) {
    await checkpoint(activeIntent, "submitting", {
      attempts: attempt,
      last_reason: lastReason,
      last_error: lastError
    });

    let submitted;
    try {
      submitted = await submitConversationSpawnBootstrap(activeIntent);
    } catch (error) {
      throw conversationFabricSpawnError(
        `Conversation Fabric child submission threw: ${String(error)}`,
        "spawn_submit_exception",
        attempt,
        String(error)
      );
    }

    if (submitted?.ok && submitted.childConversationUrl) {
      return {
        intent: activeIntent,
        childConversationUrl: submitted.childConversationUrl,
        attempts: attempt
      };
    }

    if (submitted?.reason === "spawn_submission_ambiguous") {
      let reconciled;
      try {
        reconciled = await reconcileConversationSpawn(activeIntent);
      } catch (error) {
        return {
          intent: activeIntent,
          childConversationUrl: "",
          attempts: attempt,
          ambiguous: true,
          reason: "spawn_reconcile_exception",
          error: String(error)
        };
      }
      if (reconciled?.ok && reconciled.childConversationUrl) {
        return {
          intent: activeIntent,
          childConversationUrl: reconciled.childConversationUrl,
          attempts: attempt
        };
      }
      return {
        intent: activeIntent,
        childConversationUrl: "",
        attempts: attempt,
        ambiguous: true,
        reason: String(reconciled?.reason || submitted.reason),
        error: String(reconciled?.error || submitted?.error || "")
      };
    }

    lastReason = String(submitted?.reason || "unknown");
    lastError = String(submitted?.error || "");
    await checkpoint(activeIntent, "submitting", {
      attempts: attempt,
      last_reason: lastReason,
      last_error: lastError
    });

    if (!CONVERSATION_FABRIC_TRANSIENT_SPAWN_REASONS.has(lastReason)) {
      throw conversationFabricSpawnError(
        `Conversation Fabric child submission failed: ${lastReason}`,
        lastReason,
        attempt,
        lastError
      );
    }

    if (attempt <= CONVERSATION_FABRIC_SUBMIT_RETRIES) {
      await new Promise((resolve) => setTimeout(resolve, conversationFabricRetryDelay(attempt)));
    }
  }

  throw conversationFabricSpawnError(
    `Conversation Fabric child submission exceeded bounded retries: ${lastReason || "unknown"}`,
    lastReason || "spawn_retry_exhausted",
    CONVERSATION_FABRIC_SUBMIT_RETRIES + 1,
    lastError
  );
}

async function cleanupConversationFabricChildren(children) {
  let complete = true;
  for (const child of children) {
    if (!Number.isInteger(child?.intent?.tab_id)) continue;
    try {
      const result = await closeConversationSpawnTab(child.intent);
      if (!result?.ok) complete = false;
    } catch (_error) { complete = false; }
  }
  return complete;
}

async function delegateConversationFabric(authority) {
  const campaignId = await conversationFabricCampaignId(authority);
  const existing = await loadConversationFabricCampaign(campaignId);
  if (existing) {
    if (existing.parent_conversation_url !== authority.conversationUrl) {
      throw new Error("Conversation Fabric campaign ownership conflict");
    }
    if (!["running", "completed"].includes(existing.state)) {
      return { ok: false, reason: `conversation_fabric_${existing.state}`, campaignId };
    }
    if (existing.state === "completed" && existing.feedback_delivered) {
      return { ok: true, reason: "conversation_fabric_already_delivered", campaignId };
    }
    return {
      ok: true,
      reason: existing.state === "completed" ? "conversation_fabric_completed" : "conversation_fabric_started",
      campaignId,
      feedbackPrompt: existing.state === "completed"
        ? conversationFabricCompletedPrompt(existing)
        : conversationFabricStartedPrompt(existing)
    };
  }

  const campaigns = await listConversationFabricCampaigns();
  const active = campaigns.filter((value) => ["spawning", "running"].includes(value.state));
  if (active.some((value) => value.parent_conversation_url === authority.conversationUrl)) {
    return { ok: false, reason: "conversation_fabric_parent_busy" };
  }
  const occupied = campaigns.filter(value => ["spawning", "running"].includes(value.state) || value.cleanup_pending);
  if (
    occupied.reduce((count, value) => count + value.children.length, 0) +
    authority.control.children.length >
    conversationFabricProtocol.MAX_CHILDREN
  ) {
    return { ok: false, reason: "conversation_fabric_capacity" };
  }
  const history = campaigns.filter((value) =>
    !["spawning", "running"].includes(value.state) &&
    value.feedback_delivered &&
    !value.cleanup_pending
  ).sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)));
  for (const old of history.slice(CONVERSATION_FABRIC_HISTORY_LIMIT - 1)) {
    // Upgrade-safe migration: never prune a legacy campaign result until its
    // independently retained vault copy exists.
    await backfillConversationFabricCampaignResults(old);
    await chrome.storage.local.remove(conversationFabricCampaignKey(old.id));
  }
  if (
    campaigns.length -
    Math.max(0, history.length - CONVERSATION_FABRIC_HISTORY_LIMIT + 1) >=
    CONVERSATION_FABRIC_HISTORY_LIMIT + 4
  ) {
    return { ok: false, reason: "conversation_fabric_history_full" };
  }

  const campaign = {
    schema_version: conversationFabricProtocol.SCHEMA_VERSION,
    id: campaignId,
    state: "spawning",
    parent_conversation_url: authority.conversationUrl,
    parent_tab_id: authority.parentTabId,
    assistant_identity: authority.assistantIdentity,
    fingerprint: authority.fingerprint,
    created_at: new Date().toISOString(),
    children: [],
    results: [],
    failed_children: []
  };
  // Persist the complete requested child set before any tab creation or submit side
  // effect. If the worker restarts during an early child, later requested children
  // remain represented and can fail closed explicitly instead of disappearing.
  for (const child of authority.control.children) {
    const intent = await conversationFabricIntent(authority, campaignId, child);
    campaign.children.push({
      id: child.id,
      role: child.role,
      intent,
      state: "pending",
      child_conversation_url: "",
      attempts: 0,
      last_reason: "",
      last_error: ""
    });
  }
  await saveConversationFabricCampaign(campaign);

  for (const record of campaign.children) {
    const intent = record.intent;
    try {
      const spawned = await submitConversationFabricChild(intent, async (activeIntent, state, diagnostic = {}) => {
        record.intent = activeIntent;
        record.state = state;
        if (Number.isInteger(diagnostic.attempts)) record.attempts = diagnostic.attempts;
        if (typeof diagnostic.last_reason === "string") record.last_reason = diagnostic.last_reason;
        if (typeof diagnostic.last_error === "string") record.last_error = diagnostic.last_error;
        await saveConversationFabricCampaign(campaign);
      });
      record.intent = spawned.intent;
      record.state = spawned.ambiguous
        ? CONVERSATION_FABRIC_AMBIGUOUS_CHILD_STATE
        : "submitted";
      record.child_conversation_url = spawned.ambiguous ? "" : spawned.childConversationUrl;
      record.attempts = spawned.attempts;
      record.last_reason = spawned.ambiguous ? String(spawned.reason || "spawn_submission_ambiguous") : "";
      record.last_error = spawned.ambiguous ? String(spawned.error || "") : "";
      if (spawned.ambiguous) {
        record.ambiguity_started_at = new Date().toISOString();
      } else {
        delete record.ambiguity_started_at;
      }
      delete record.failure;
    } catch (error) {
      record.state = "failed";
      record.failure = {
        reason: String(error?.reason || "unknown"),
        attempt: Number.isInteger(error?.attempt) ? error.attempt : record.attempts,
        error: String(error?.detail || error?.message || error || "")
      };
      record.last_reason = record.failure.reason;
      record.last_error = record.failure.error;
      campaign.failed_children = campaign.children
        .filter((item) => item.state === "failed")
        .map(conversationFabricChildFailure);
    }
    await saveConversationFabricCampaign(campaign);
  }

  const submittedChildren = campaign.children.filter(
    (child) => child.state === "submitted" && child.child_conversation_url
  );
  const ambiguousChildren = campaign.children.filter(
    (child) => child.state === CONVERSATION_FABRIC_AMBIGUOUS_CHILD_STATE
  );
  campaign.failed_children = campaign.children
    .filter((child) => child.state === "failed")
    .map(conversationFabricChildFailure);

  if (!submittedChildren.length && !ambiguousChildren.length) {
    campaign.state = "failed";
    campaign.failure = campaign.failed_children.length
      ? `all_children_failed: ${campaign.failed_children.map(conversationFabricFailureSummary).join("; ")}`
      : "all_children_failed";
    campaign.feedback_delivered = false;
    await saveConversationFabricCampaign(campaign);
    campaign.cleanup_pending = !await cleanupConversationFabricChildren(campaign.children);
    await saveConversationFabricCampaign(campaign);
    return {
      ok: false,
      reason: "conversation_fabric_failed",
      campaignId,
      error: campaign.failure
    };
  }

  campaign.state = "running";
  campaign.partial_failure = campaign.failed_children.length > 0;
  await saveConversationFabricCampaign(campaign);
  return {
    ok: true,
    reason: "conversation_fabric_started",
    campaignId,
    children: campaign.children.map((child) => ({
      id: child.id,
      state: child.state,
      childConversationUrl: child.child_conversation_url,
      failure: child.state === "failed" ? conversationFabricChildFailure(child) : null
    })),
    feedbackPrompt: conversationFabricStartedPrompt(campaign)
  };
}

async function stableConversationFabricResult(child) {
  const first = await observeConversationSpawnResult(child.intent, CONVERSATION_FABRIC_RESULT_CHARS);
  if (!first?.ok || first.reason !== "child_result_ready") return first;
  await new Promise((resolve) => setTimeout(resolve, 700));
  const second = await observeConversationSpawnResult(child.intent, CONVERSATION_FABRIC_RESULT_CHARS);
  if (!second?.ok || second.reason !== "child_result_ready") return second;
  if (
    first.assistantIdentity !== second.assistantIdentity ||
    first.assistantText !== second.assistantText
  ) {
    return { ok: true, reason: "child_result_unstable" };
  }
  return second;
}

async function reconcileConversationFabricAmbiguousChild(child) {
  let reconciled;
  try {
    reconciled = await reconcileConversationSpawn(child.intent);
  } catch (error) {
    reconciled = {
      ok: false,
      reason: "spawn_reconcile_exception",
      error: String(error)
    };
  }

  if (reconciled?.ok && reconciled.childConversationUrl) {
    child.state = "submitted";
    child.child_conversation_url = reconciled.childConversationUrl;
    child.last_reason = "";
    child.last_error = "";
    child.recovered_submission_ambiguity = true;
    child.submission_recovered_at = new Date().toISOString();
    delete child.failure;
    return { ok: true, reason: "identity_discovered" };
  }

  // Result observation validates the child page's exact transaction/request/bootstrap
  // claim and canonical current child URL. It is therefore also the safe recovery path
  // when a worker restart cleared storage.session after the bootstrap was actually sent.
  let observed;
  try {
    observed = await observeConversationSpawnResult(child.intent, CONVERSATION_FABRIC_RESULT_CHARS);
  } catch (error) {
    observed = {
      ok: false,
      reason: "child_result_unavailable",
      error: String(error)
    };
  }
  if (observed?.ok && observed.childConversationUrl) {
    child.state = "submitted";
    child.child_conversation_url = observed.childConversationUrl;
    child.last_reason = "";
    child.last_error = "";
    child.recovered_submission_ambiguity = true;
    child.submission_recovered_at = new Date().toISOString();
    delete child.failure;
    return { ok: true, reason: "identity_discovered", observedReason: observed.reason };
  }

  const reason = String(observed?.reason || reconciled?.reason || "spawn_submission_ambiguous");
  const error = String(observed?.error || reconciled?.error || "");
  child.reconciliation_attempts = Number(child.reconciliation_attempts || 0) + 1;
  child.last_reason = reason;
  child.last_error = error;
  return {
    ok: false,
    pending: !CONVERSATION_FABRIC_AMBIGUOUS_HARD_FAILURE_REASONS.has(reason),
    reason,
    error
  };
}

async function collectConversationFabric(authority) {
  const campaign = await loadConversationFabricCampaign(authority.control.campaign_id);
  if (!campaign) {
    return { ok: false, reason: "conversation_fabric_campaign_missing" };
  }
  if (campaign.parent_conversation_url !== authority.conversationUrl) {
    return { ok: false, reason: "conversation_fabric_parent_mismatch" };
  }
  // A crash may happen after the independent vault write but before the campaign copy.
  // Restore that durable result before any observation or cleanup decision.
  await hydrateConversationFabricResultsFromVault(campaign);
  if (campaign.state === "completed") {
    if (campaign.feedback_delivered) {
      return { ok: true, reason: "conversation_fabric_already_delivered", campaignId: campaign.id };
    }
    return {
      ok: true,
      reason: "conversation_fabric_completed",
      campaignId: campaign.id,
      feedbackPrompt: conversationFabricCompletedPrompt(campaign)
    };
  }

  const recoverableObservation = campaign.state === "failed" && campaign.children.length > 0 &&
    campaign.children.every(child => child.state === "submitted" && child.child_conversation_url);
  if (campaign.state !== "running" && !recoverableObservation) {
    return { ok: false, reason: `conversation_fabric_${campaign.state || "invalid"}` };
  }

  const results = Array.isArray(campaign.results) ? [...campaign.results] : [];
  const pending = [];
  const failedChildren = conversationFabricFailedChildren(campaign);
  for (const child of campaign.children) {
    if (child.state === "failed") continue;
    if (results.some((result) => result.id === child.id)) continue;
    if (child.state === CONVERSATION_FABRIC_AMBIGUOUS_CHILD_STATE) {
      const recovered = await reconcileConversationFabricAmbiguousChild(child);
      if (!recovered.ok) {
        if (recovered.pending) {
          pending.push(child.id);
          continue;
        }
        const failure = {
          id: child.id,
          role: child.role,
          attempt: Number(child.attempts || 0),
          reason: recovered.reason,
          error: recovered.error
        };
        child.state = "failed";
        child.failure = failure;
        failedChildren.push(conversationFabricChildFailure(child));
        continue;
      }
    }
    if (child.state !== "submitted" || !child.child_conversation_url) {
      const failure = {
        id: child.id,
        role: child.role,
        attempt: Number(child.attempts || 0),
        reason: `invalid_child_state_${child.state || "unknown"}`,
        error: ""
      };
      child.state = "failed";
      child.failure = failure;
      failedChildren.push(conversationFabricChildFailure(child));
      continue;
    }

    const observed = await stableConversationFabricResult(child);
    if (observed?.ok && observed.reason === "child_result_ready") {
      const vaulted = await saveConversationFabricVaultResult(campaign, child, observed);
      results.push({
        id: child.id,
        role: child.role,
        child_conversation_url: child.child_conversation_url,
        assistant_identity: String(observed.assistantIdentity || ""),
        assistant_text: String(observed.assistantText || "").slice(0, CONVERSATION_FABRIC_RESULT_CHARS),
        truncated: observed.truncated === true ||
          String(observed.assistantText || "").length > CONVERSATION_FABRIC_RESULT_CHARS,
        captured_at: vaulted.captured_at,
        vault_sha256: vaulted.text_sha256
      });
      child.result_captured = true;
      child.result_captured_at = vaulted.captured_at;
      continue;
    }
    if (
      observed?.ok &&
      ["child_generating", "child_result_missing", "child_result_unstable"].includes(observed.reason)
    ) {
      pending.push(child.id);
      continue;
    }

    const failure = {
      id: child.id,
      role: child.role,
      attempt: Number(child.attempts || 0),
      reason: String(observed?.reason || "conversation_fabric_child_observation_failed"),
      error: String(observed?.error || "")
    };
    child.state = "failed";
    child.failure = failure;
    failedChildren.push(conversationFabricChildFailure(child));
  }

  campaign.failed_children = failedChildren;
  if (pending.length) {
    await saveConversationFabricCampaign(campaign);
    return {
      ok: true,
      reason: "conversation_fabric_pending",
      campaignId: campaign.id,
      pending,
      feedbackPrompt: conversationFabricPendingPrompt(campaign, pending)
    };
  }

  campaign.results = results;
  campaign.feedback_delivered = false;
  if (recoverableObservation) campaign.recovered_observation = true;
  campaign.partial_failure = failedChildren.length > 0;
  campaign.state = "completed";
  campaign.completed_at = new Date().toISOString();
  // Save captured results before closing any tab so interruption cannot destroy evidence.
  campaign.cleanup_pending = true;
  await saveConversationFabricCampaign(campaign);
  campaign.cleanup_pending = !await cleanupConversationFabricChildren(campaign.children);
  await saveConversationFabricCampaign(campaign);
  return {
    ok: true,
    reason: "conversation_fabric_completed",
    campaignId: campaign.id,
    feedbackPrompt: conversationFabricCompletedPrompt(campaign)
  };
}

async function retireConversationFabricChild(authority) {
  const campaign = await loadConversationFabricCampaign(authority.control.campaign_id);
  if (!campaign) return { ok: false, reason: "conversation_fabric_campaign_missing" };
  if (campaign.parent_conversation_url !== authority.conversationUrl) {
    return { ok: false, reason: "conversation_fabric_parent_mismatch" };
  }
  const child = (campaign.children || []).find((value) => value.id === authority.control.child_id);
  if (!child) return { ok: false, reason: "conversation_fabric_child_missing" };

  // Recover a vault-only checkpoint before touching the tab. This closes the crash
  // window where result durability succeeded but the campaign copy was not yet saved.
  await hydrateConversationFabricResultsFromVault(campaign);
  let campaignResult = (campaign.results || []).find((result) => result.id === child.id) || null;
  let vaulted = await loadConversationFabricVaultResult(campaign.id, child.id);
  if (campaignResult && !vaulted) {
    await backfillConversationFabricCampaignResults(campaign);
    vaulted = await loadConversationFabricVaultResult(campaign.id, child.id);
  }

  if (Number.isInteger(child?.intent?.tab_id)) {
    // Re-prove the page's exact transaction/request/bootstrap/current-route identity
    // immediately before close. A stale storage.session tab mapping is not sufficient.
    const ownership = await stableConversationFabricResult(child);
    if (ownership?.reason === "spawn_tab_unavailable") {
      // The operator/browser already closed the tab. Clear only transient ownership
      // metadata; do not touch the tab id again because it could later be repurposed.
      await forgetConversationSpawnTab(child.intent);
    } else {
      if (
        !ownership?.ok ||
        !ownership.childConversationUrl ||
        (child.child_conversation_url && ownership.childConversationUrl !== child.child_conversation_url)
      ) {
        return {
          ok: false,
          reason: "conversation_fabric_retire_ownership_unproven",
          campaignId: campaign.id,
          childId: child.id,
          error: String(ownership?.reason || ownership?.error || "exact child page identity could not be proven")
        };
      }
      if (!child.child_conversation_url) {
        child.child_conversation_url = ownership.childConversationUrl;
        child.state = "submitted";
      }
      if (ownership.reason === "child_result_ready" && !campaignResult) {
        vaulted = await saveConversationFabricVaultResult(campaign, child, ownership);
        campaignResult = {
          id: child.id,
          role: child.role,
          child_conversation_url: child.child_conversation_url,
          assistant_identity: String(ownership.assistantIdentity || ""),
          assistant_text: String(ownership.assistantText || "").slice(0, CONVERSATION_FABRIC_RESULT_CHARS),
          truncated: ownership.truncated === true ||
            String(ownership.assistantText || "").length > CONVERSATION_FABRIC_RESULT_CHARS,
          captured_at: vaulted.captured_at,
          vault_sha256: vaulted.text_sha256
        };
        campaign.results.push(campaignResult);
        child.result_captured = true;
        child.result_captured_at = vaulted.captured_at;
        await saveConversationFabricCampaign(campaign);
      }

      let closed;
      try {
        closed = await closeConversationSpawnTab(child.intent);
      } catch (error) {
        closed = { ok: false, reason: "spawn_tab_close_failed", error: String(error) };
      }
      if (!closed?.ok) {
        return {
          ok: false,
          reason: "conversation_fabric_retire_ownership_unproven",
          campaignId: campaign.id,
          childId: child.id,
          error: String(closed?.reason || closed?.error || "unable to close exact owned child tab")
        };
      }
    }
  }

  child.operator_retired = true;
  child.operator_retired_at = new Date().toISOString();
  child.last_observation_reason = "operator_retired";
  if (campaignResult || vaulted) {
    child.result_captured = true;
    child.result_captured_at = String(campaignResult?.captured_at || vaulted?.captured_at || child.result_captured_at || "");
    child.retired_after_result = true;
    child.state = "submitted";
    child.last_reason = "";
    child.last_error = "";
    delete child.failure;
  } else {
    child.state = "failed";
    child.failure = {
      id: child.id,
      role: child.role,
      attempt: Number(child.attempts || 0),
      reason: "operator_retired",
      error: "operator explicitly retired this child; replacement requires a new explicit delegation",
      retryable: true
    };
    child.last_reason = child.failure.reason;
    child.last_error = child.failure.error;
  }
  campaign.failed_children = (campaign.children || [])
    .filter((value) => value.state === "failed")
    .map(conversationFabricChildFailure);
  campaign.partial_failure = campaign.failed_children.length > 0;
  await saveConversationFabricCampaign(campaign);

  if (["running", "spawning"].includes(campaign.state)) {
    try {
      await collectConversationFabric({
        ...authority,
        control: { schema_version: conversationFabricProtocol.SCHEMA_VERSION, action: "collect", campaign_id: campaign.id }
      });
    } catch (_error) {}
  }

  const inspected = await inspectConversationFabric({
    ...authority,
    control: { schema_version: conversationFabricProtocol.SCHEMA_VERSION, action: "inspect", campaign_id: campaign.id }
  });
  return {
    ok: true,
    reason: "conversation_fabric_child_retired",
    campaignId: campaign.id,
    childId: child.id,
    hadCapturedResult: Boolean(campaignResult || vaulted),
    feedbackPrompt: [
      `Conversation Fabric child ${child.id} was explicitly retired. Its bootstrap was not replayed.`,
      campaignResult || vaulted
        ? "A captured result was preserved in the Result Vault."
        : "No captured result existed; this child is retryable missing coverage. Wait for the campaign's terminal feedback before intentionally reassigning that bounded work in a new delegation with a new child id.",
      inspected.feedbackPrompt || ""
    ].filter(Boolean).join("\n\n")
  };
}

async function applyConversationFabricControl(message, sender) {
  let authority;
  try {
    authority = validateConversationFabricMessage(message, sender);
  } catch (error) {
    return { ok: false, reason: "conversation_fabric_control_invalid", error: String(error) };
  }
  try {
    const parent = await conversationFabricManagedParent(authority);
    if (!parent) {
      return { ok: false, reason: "conversation_fabric_parent_not_managed" };
    }
    if (authority.control.action === "delegate") {
      return await serializeConversationFabric(
        authority.conversationUrl,
        () => serializeConversationFabric(
          "delegation-admission",
          () => delegateConversationFabric(authority)
        )
      );
    }
    if (authority.control.action === "collect") {
      return await serializeConversationFabric(
        authority.conversationUrl,
        () => collectConversationFabric(authority)
      );
    }
    if (authority.control.action === "inspect") {
      return await serializeConversationFabric(
        authority.conversationUrl,
        () => inspectConversationFabric(authority)
      );
    }
    if (authority.control.action === "retire") {
      return await serializeConversationFabric(
        authority.conversationUrl,
        () => retireConversationFabricChild(authority)
      );
    }
    return { ok: false, reason: "conversation_fabric_action_unsupported" };
  } catch (error) {
    return { ok: false, reason: "conversation_fabric_failed", error: String(error) };
  }
}

async function conversationFabricFeedbackForParent(parentUrl) {
  const campaigns = await listConversationFabricCampaigns();
  const campaign = campaigns.find((value) => value.parent_conversation_url === parentUrl &&
    ["completed", "failed"].includes(value.state) && !value.feedback_delivered);
  if (!campaign) return null;
  return {
    campaign,
    prompt: campaign.state === "completed" ? conversationFabricCompletedPrompt(campaign) :
      [
        `Conversation Fabric campaign ${campaign.id} failed: ${campaign.failure || "interrupted"}.`,
        "Captured child work remains recoverable from the Result Vault with an explicit inspect control.",
        "Retryable missing child coverage may be intentionally delegated again with new child ids after this terminal feedback. Do not invent or automatically replay this delegation."
      ].join("\n\n")
  };
}

async function acknowledgeConversationFabricFeedback(message, sender) {
  try {
    const authority = validateConversationFabricMessage(message, sender);
    if (!await conversationFabricManagedParent(authority)) {
      return { ok: false, reason: "conversation_fabric_parent_not_managed" };
    }
    const campaign = await loadConversationFabricCampaign(message.campaignId);
    if (!campaign || campaign.parent_conversation_url !== authority.conversationUrl) {
      return { ok: false, reason: "conversation_fabric_parent_mismatch" };
    }
    if (authority.control.action === "collect" && ["completed", "failed"].includes(campaign.state)) {
      campaign.feedback_delivered = true;
      await saveConversationFabricCampaign(campaign);
    }
    return { ok: true, reason: "conversation_fabric_feedback_acknowledged" };
  } catch (error) {
    return { ok: false, reason: "conversation_fabric_feedback_invalid", error: String(error) };
  }
}

async function pollConversationFabricCampaigns() {
  const state = await getBridgeState();
  if (!state.settings.masterEnabled) return;
  const campaigns = await listConversationFabricCampaigns();
  for (const campaign of campaigns) {
    if (campaign.feedback_delivered || conversationFabricOperations.has(campaign.parent_conversation_url)) continue;
    const parent = state.conversations[conversationId(campaign.parent_conversation_url)];
    if (!parent?.enabled) continue;
    await serializeConversationFabric(campaign.parent_conversation_url, async () => {
      const current = await loadConversationFabricCampaign(campaign.id);
      if (!current || current.feedback_delivered) return;
      if (
        current.state === "spawning" ||
        (current.state === "running" &&
          Date.now() - Date.parse(current.created_at) > CONVERSATION_FABRIC_TIMEOUT_MS)
      ) {
        current.state = "failed";
        current.failure = current.children.some((child) => child.state === "submitting")
          ? "spawn_interrupted_submission_ambiguous"
          : "campaign_interrupted_or_timed_out";
        await saveConversationFabricCampaign(current);
      }
      const recoverableClaims = current.state === "failed" &&
        current.failure === "spawn_tab_claim_mismatch" &&
        current.children.every(child => child.state === "submitted" && child.child_conversation_url);
      if (current.state === "running" || recoverableClaims) {
        const result = await collectConversationFabric({
          conversationUrl: parent.url,
          control: { campaign_id: current.id }
        });
        if (!result.ok) {
          current.state = "failed";
          current.failure = result.reason;
          await saveConversationFabricCampaign(current);
        }
      }
      const finished = await loadConversationFabricCampaign(current.id);
      if (finished?.cleanup_pending || finished?.state === "failed") {
        finished.cleanup_pending = !await cleanupConversationFabricChildren(finished.children);
        await saveConversationFabricCampaign(finished);
      }
      if (["completed", "failed"].includes(finished?.state)) {
        await runFeedbackCycle({ conversationId: parent.id });
      }
    });
  }
}
