const conversationFabricProtocol = globalThis.LocalAgentConversationFabricProtocol;
if (!conversationFabricProtocol) {
  throw new Error("Conversation Fabric protocol is unavailable in the service worker");
}

const CONVERSATION_FABRIC_CAMPAIGN_PREFIX = "conversation-fabric-campaign:";
const CONVERSATION_FABRIC_RESULT_CHARS = 6_000;
const CONVERSATION_FABRIC_COLLECT_DELAY_SECONDS = 30;
const CONVERSATION_FABRIC_SUBMIT_RETRIES = 5;
const CONVERSATION_FABRIC_TRANSIENT_SPAWN_REASONS = new Set([
  "spawn_page_not_ready",
  "spawn_composer_not_found",
  "spawn_send_button_not_ready",
  "spawn_content_unavailable"
]);

function conversationFabricCampaignKey(campaignId) {
  if (!conversationFabricProtocol.CAMPAIGN_ID_RE.test(String(campaignId || ""))) {
    throw new Error("invalid Conversation Fabric campaign id");
  }
  return `${CONVERSATION_FABRIC_CAMPAIGN_PREFIX}${campaignId}`;
}

async function loadConversationFabricCampaign(campaignId) {
  const key = conversationFabricCampaignKey(campaignId);
  const stored = await chrome.storage.session.get(key);
  const value = stored?.[key];
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

async function saveConversationFabricCampaign(campaign) {
  const key = conversationFabricCampaignKey(campaign.id);
  await chrome.storage.session.set({ [key]: campaign });
  return campaign;
}

function conversationFabricCollectBlock(campaignId) {
  return [
    "<<<LOCAL_AGENT_CF",
    JSON.stringify({
      schema_version: conversationFabricProtocol.SCHEMA_VERSION,
      action: "collect",
      campaign_id: campaignId
    }),
    "LOCAL_AGENT_CF>>>"
  ].join("\n");
}

function conversationFabricPendingPrompt(campaign, pendingIds) {
  return [
    `Conversation Fabric campaign ${campaign.id} is still running in child tabs: ${pendingIds.join(", ")}.`,
    "Do not synthesize the delegated work yet.",
    `End this reply with [LAB:NEXT=${CONVERSATION_FABRIC_COLLECT_DELAY_SECONDS}s].`,
    "On the next wake, end the reply with this exact Conversation Fabric collect block:",
    conversationFabricCollectBlock(campaign.id)
  ].join("\n\n");
}

function conversationFabricStartedPrompt(campaign) {
  const ids = campaign.children.map((child) => child.id).join(", ");
  return [
    `Conversation Fabric started ${campaign.children.length} reasoning child tab(s) in this Chrome session: ${ids}.`,
    `Campaign id: ${campaign.id}.`,
    "Do not synthesize the delegated work yet.",
    `End this reply with [LAB:NEXT=${CONVERSATION_FABRIC_COLLECT_DELAY_SECONDS}s].`,
    "On the next wake, end the reply with this exact Conversation Fabric collect block:",
    conversationFabricCollectBlock(campaign.id)
  ].join("\n\n");
}

function conversationFabricCompletedPrompt(campaign) {
  const sections = campaign.results.map((result) => [
    `--- child ${result.id} (${result.role}) ---`,
    result.assistant_text
  ].join("\n"));
  return [
    `Conversation Fabric campaign ${campaign.id} completed.`,
    "All owned child tabs were closed after stable result capture.",
    ...sections,
    "Synthesize the final parent answer now. Do not delegate machine execution to a child."
  ].join("\n\n");
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
  const senderUrl = normalizeConversationUrl(String(sender?.tab?.url || sender?.url || ""));
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

async function submitConversationFabricChild(intent) {
  let activeIntent = null;
  try {
    const created = await createConversationSpawnTab(intent);
    if (!created?.ok || !Number.isInteger(created.tabId)) {
      throw new Error(`Conversation Fabric child tab creation failed: ${created?.reason || "unknown"}`);
    }
    activeIntent = { ...intent, tab_id: created.tabId };
    for (let attempt = 0; attempt <= CONVERSATION_FABRIC_SUBMIT_RETRIES; attempt += 1) {
      const submitted = await submitConversationSpawnBootstrap(activeIntent);
      if (submitted?.ok && submitted.childConversationUrl) {
        return { intent: activeIntent, childConversationUrl: submitted.childConversationUrl };
      }
      if (submitted?.reason === "spawn_submission_ambiguous") {
        const reconciled = await reconcileConversationSpawn(activeIntent);
        if (reconciled?.ok && reconciled.childConversationUrl) {
          return { intent: activeIntent, childConversationUrl: reconciled.childConversationUrl };
        }
        throw new Error(`Conversation Fabric child submission is ambiguous: ${reconciled?.reason || submitted.reason}`);
      }
      if (!CONVERSATION_FABRIC_TRANSIENT_SPAWN_REASONS.has(String(submitted?.reason || ""))) {
        throw new Error(`Conversation Fabric child submission failed: ${submitted?.reason || "unknown"}`);
      }
      if (attempt < CONVERSATION_FABRIC_SUBMIT_RETRIES) {
        await new Promise((resolve) => setTimeout(resolve, 350));
      }
    }
    throw new Error("Conversation Fabric child submission exceeded bounded retries");
  } catch (error) {
    if (activeIntent !== null) {
      try { await closeConversationSpawnTab(activeIntent); } catch (_error) {}
    }
    throw error;
  }
}

async function cleanupConversationFabricChildren(children) {
  for (const child of children) {
    if (!child?.intent) continue;
    try {
      await closeConversationSpawnTab(child.intent);
    } catch (_error) {}
  }
}

async function delegateConversationFabric(authority) {
  const campaignId = await conversationFabricCampaignId(authority);
  const existing = await loadConversationFabricCampaign(campaignId);
  if (existing) {
    if (existing.parent_conversation_url !== authority.conversationUrl) {
      throw new Error("Conversation Fabric campaign ownership conflict");
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
    results: []
  };
  await saveConversationFabricCampaign(campaign);

  try {
    for (const child of authority.control.children) {
      const intent = await conversationFabricIntent(authority, campaignId, child);
      const spawned = await submitConversationFabricChild(intent);
      campaign.children.push({
        id: child.id,
        role: child.role,
        intent: spawned.intent,
        child_conversation_url: spawned.childConversationUrl
      });
      await saveConversationFabricCampaign(campaign);
    }
  } catch (error) {
    await cleanupConversationFabricChildren(campaign.children);
    campaign.state = "failed";
    campaign.failure = String(error);
    await saveConversationFabricCampaign(campaign);
    throw error;
  }

  campaign.state = "running";
  await saveConversationFabricCampaign(campaign);
  return {
    ok: true,
    reason: "conversation_fabric_started",
    campaignId,
    children: campaign.children.map((child) => ({ id: child.id, childConversationUrl: child.child_conversation_url })),
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

async function collectConversationFabric(authority) {
  const campaign = await loadConversationFabricCampaign(authority.control.campaign_id);
  if (!campaign) {
    return { ok: false, reason: "conversation_fabric_campaign_missing" };
  }
  if (campaign.parent_conversation_url !== authority.conversationUrl) {
    return { ok: false, reason: "conversation_fabric_parent_mismatch" };
  }
  if (campaign.state === "completed") {
    return {
      ok: true,
      reason: "conversation_fabric_completed",
      campaignId: campaign.id,
      feedbackPrompt: conversationFabricCompletedPrompt(campaign)
    };
  }
  if (campaign.state !== "running") {
    return { ok: false, reason: `conversation_fabric_${campaign.state || "invalid"}` };
  }

  const results = [];
  const pending = [];
  for (const child of campaign.children) {
    const observed = await stableConversationFabricResult(child);
    if (observed?.ok && observed.reason === "child_result_ready") {
      results.push({
        id: child.id,
        role: child.role,
        child_conversation_url: child.child_conversation_url,
        assistant_identity: String(observed.assistantIdentity || ""),
        assistant_text: String(observed.assistantText || "").slice(0, CONVERSATION_FABRIC_RESULT_CHARS),
        truncated: observed.truncated === true
      });
      continue;
    }
    if (observed?.ok && ["child_generating", "child_result_missing", "child_result_unstable"].includes(observed.reason)) {
      pending.push(child.id);
      continue;
    }
    return {
      ok: false,
      reason: observed?.reason || "conversation_fabric_child_observation_failed"
    };
  }

  if (pending.length) {
    return {
      ok: true,
      reason: "conversation_fabric_pending",
      campaignId: campaign.id,
      pending,
      feedbackPrompt: conversationFabricPendingPrompt(campaign, pending)
    };
  }

  campaign.results = results;
  campaign.state = "completed";
  campaign.completed_at = new Date().toISOString();
  await cleanupConversationFabricChildren(campaign.children);
  await saveConversationFabricCampaign(campaign);
  return {
    ok: true,
    reason: "conversation_fabric_completed",
    campaignId: campaign.id,
    feedbackPrompt: conversationFabricCompletedPrompt(campaign)
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
    if (authority.control.action === "delegate") {
      return await delegateConversationFabric(authority);
    }
    if (authority.control.action === "collect") {
      return await collectConversationFabric(authority);
    }
    return { ok: false, reason: "conversation_fabric_action_unsupported" };
  } catch (error) {
    return { ok: false, reason: "conversation_fabric_failed", error: String(error) };
  }
}

async function refreshConversationFabricContentScripts() {
  const tabs = await chrome.tabs.query({
    url: ["https://chatgpt.com/*", "https://chat.openai.com/*"]
  });
  let refreshed = 0;
  for (const tab of tabs) {
    if (!Number.isInteger(tab?.id)) continue;
    try {
      await chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: [0] },
        files: [
          "control_protocol.js",
          "conversation_fabric_protocol.js",
          "content_retry.js",
          "spawn_result_content.js",
          "conversation_fabric_content.js"
        ]
      });
      refreshed += 1;
    } catch (_error) {}
  }
  return { refreshed };
}

refreshConversationFabricContentScripts().catch((error) => console.error(error));
