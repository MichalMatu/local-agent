const protocol = globalThis.LocalAgentBridgeProtocol;

const elements = {
  masterEnabled: document.querySelector("#masterEnabled"),
  currentTitle: document.querySelector("#currentTitle"),
  currentUrl: document.querySelector("#currentUrl"),
  addCurrent: document.querySelector("#addCurrent"),
  operatorOverall: document.querySelector("#operatorOverall"),
  operatorVersions: document.querySelector("#operatorVersions"),
  operatorRuntime: document.querySelector("#operatorRuntime"),
  operatorGoal: document.querySelector("#operatorGoal"),
  operatorCampaign: document.querySelector("#operatorCampaign"),
  operatorFeedback: document.querySelector("#operatorFeedback"),
  operatorDedupe: document.querySelector("#operatorDedupe"),
  conversationList: document.querySelector("#conversationList"),
  conversationCount: document.querySelector("#conversationCount"),
  runtimeUrl: document.querySelector("#runtimeUrl"),
  fallbackInterval: document.querySelector("#fallbackInterval"),
  fallbackRetry: document.querySelector("#fallbackRetry"),
  fallbackWakePrompt: document.querySelector("#fallbackWakePrompt"),
  fallbackBootstrapPrompt: document.querySelector("#fallbackBootstrapPrompt"),
  saveGlobal: document.querySelector("#saveGlobal"),
  runtimeSource: document.querySelector("#runtimeSource"),
  runtimeInterval: document.querySelector("#runtimeInterval"),
  message: document.querySelector("#message")
};

let latestState = null;
let latestRuntime = null;
let currentTab = null;
let countdownTimer = null;
let messageTimer = null;

function showMessage(text) {
  elements.message.textContent = text;
  clearTimeout(messageTimer);
  if (text && !String(text).startsWith("Error:")) {
    messageTimer = setTimeout(() => {
      if (elements.message.textContent === text) elements.message.textContent = "";
    }, 3200);
  }
}

function formatRemaining(milliseconds) {
  const totalSeconds = Math.max(0, Math.ceil(Number(milliseconds) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function updateNextWakeElement(element) {
  if (element.dataset.masterEnabled !== "true") {
    element.textContent = "Master off";
    return;
  }
  if (element.dataset.conversationEnabled !== "true") {
    element.textContent = "Paused";
    return;
  }
  const when = Date.parse(element.dataset.nextRunAt || "");
  if (!Number.isFinite(when)) {
    element.textContent = "Not scheduled";
    return;
  }
  const remaining = when - Date.now();
  element.textContent = remaining <= 0 ? "Due now" : `Next ${formatRemaining(remaining)}`;
  element.title = new Date(when).toLocaleString();
}

function restartCountdownTimer() {
  if (countdownTimer !== null) clearInterval(countdownTimer);
  const update = () => document.querySelectorAll("[data-next-run-at]").forEach(updateNextWakeElement);
  update();
  countdownTimer = setInterval(update, 1000);
}

function chatLabelFromTitle(title) {
  const cleaned = String(title || "").replace(/\s*[|–—-]\s*ChatGPT\s*$/i, "").trim();
  if (!cleaned || /^ChatGPT$/i.test(cleaned)) return "ChatGPT conversation";
  return cleaned.slice(0, 120);
}

async function request(message) {
  return chrome.runtime.sendMessage(message);
}

async function getCurrentChatTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const normalizedUrl = protocol.normalizeConversationUrl(tab?.url || "");
  return tab?.id && normalizedUrl ? { ...tab, normalizedUrl } : null;
}

async function injectContentScript(tabId, expectedUrl) {
  const response = await request({
    type: "bridge:ensure-tab-content",
    tabId,
    expectedUrl
  });
  if (!response?.ok) {
    throw new Error(response?.reason || response?.error || "Bridge content script did not become ready.");
  }
  return response;
}

function makeButton(text, className = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.textContent = text;
  if (className) button.className = className;
  return button;
}

function makeMeta(text, className = "") {
  const span = document.createElement("span");
  span.textContent = text;
  if (className) span.className = className;
  return span;
}

function managedControlForConversation(runtime, conversation) {
  return (runtime?.conversationControls || []).find((control) =>
    control.conversationId === conversation.id
  ) || null;
}

async function updateConversation(conversationId, patch) {
  const response = await request({ type: "bridge:update-conversation", conversationId, patch });
  if (!response?.ok) throw new Error(response?.error || "update failed");
  return response.conversation;
}

function renderConversation(conversation, settings, schedule, runtime, ownership = null) {
  const managedControl = managedControlForConversation(runtime, conversation);
  const githubManaged = Boolean(managedControl || ownership?.managed);
  const displayEnabled = managedControl ? managedControl.enabled : conversation.enabled;
  const displayInterval = managedControl ? managedControl.intervalMinutes : conversation.intervalOverrideMinutes;

  const card = document.createElement("article");
  card.className = "conversation-card";
  if (!displayEnabled) card.classList.add("is-paused");

  const header = document.createElement("div");
  header.className = "card-header";
  const titleBlock = document.createElement("div");
  titleBlock.className = "card-title-block";
  const titleLine = document.createElement("div");
  titleLine.className = "card-title-line";
  const title = makeMeta(conversation.label || conversation.id, "card-title");
  title.title = conversation.label || conversation.id;
  const repo = makeMeta("transport", "repo-badge");
  titleLine.append(title, repo);
  if (githubManaged) {
    const authority = makeMeta("GitHub managed", "repo-badge");
    const generation = managedControl?.controlGeneration || ownership?.controlGeneration || "?";
    const source = managedControl ? "remote" : (ownership?.source || "cached");
    authority.title = `GitHub desired state generation ${generation} (${source})`;
    titleLine.append(authority);
  }
  titleBlock.append(titleLine);

  const enableLabel = document.createElement("label");
  enableLabel.className = "switch-control enable-switch";
  enableLabel.title = githubManaged
    ? "Schedule state is managed by GitHub desired state."
    : "Enable or pause scheduled wakes.";
  const enabled = document.createElement("input");
  enabled.type = "checkbox";
  enabled.checked = Boolean(displayEnabled);
  enabled.disabled = githubManaged;
  enabled.setAttribute("aria-label", `Enable ${conversation.label || conversation.id}`);
  const switchTrack = document.createElement("span");
  switchTrack.className = "switch-track";
  switchTrack.setAttribute("aria-hidden", "true");
  const switchThumb = document.createElement("span");
  switchThumb.className = "switch-thumb";
  switchTrack.append(switchThumb);
  enableLabel.append(enabled, switchTrack);
  header.append(titleBlock, enableLabel);

  const meta = document.createElement("div");
  meta.className = "card-meta";
  const status = makeMeta(conversation.lastStatus || "ready", "status-text");
  status.title = `Last status: ${conversation.lastStatus || "ready"}`;
  const next = makeMeta("", "next-wake");
  next.dataset.nextRunAt = schedule?.nextRunAt || "";
  next.dataset.masterEnabled = settings.masterEnabled ? "true" : "false";
  next.dataset.conversationEnabled = displayEnabled ? "true" : "false";
  updateNextWakeElement(next);
  meta.append(status, next);

  const controls = document.createElement("div");
  controls.className = "card-controls";
  const wakeField = document.createElement("label");
  wakeField.className = "wake-field";
  const wakeLabel = makeMeta(githubManaged ? "GitHub interval" : "Wake every", "field-label");
  const wakeInputWrap = document.createElement("div");
  wakeInputWrap.className = "wake-input-wrap";
  const intervalInput = document.createElement("input");
  intervalInput.type = "number";
  intervalInput.min = "1";
  intervalInput.max = "1440";
  intervalInput.placeholder = String(runtime?.intervalMinutes || settings.fallbackIntervalMinutes || 10);
  intervalInput.value = displayInterval === null ? "" : String(displayInterval);
  intervalInput.disabled = githubManaged;
  intervalInput.title = githubManaged
    ? "Schedule interval is managed by GitHub desired state."
    : `Leave empty to use global default (${runtime?.intervalMinutes || settings.fallbackIntervalMinutes || 10} min).`;
  const unit = makeMeta("min");
  wakeInputWrap.append(intervalInput, unit);
  wakeField.append(wakeLabel, wakeInputWrap);

  const run = makeButton("Run now", "run-button");
  const remove = makeButton("Remove", "remove-button");
  controls.append(wakeField, run, remove);

  enabled.addEventListener("change", async () => {
    if (githubManaged) return;
    try {
      await updateConversation(conversation.id, { enabled: enabled.checked });
      showMessage(enabled.checked ? "Scheduling enabled." : "Scheduling paused.");
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
      await refresh();
    }
  });

  const saveInterval = async () => {
    if (githubManaged) return;
    try {
      const raw = intervalInput.value.trim();
      const nextValue = raw ? Number(raw) : null;
      if (raw && (!Number.isFinite(nextValue) || nextValue < 1 || nextValue > 1440)) {
        throw new Error("Wake time must be between 1 and 1440 minutes.");
      }
      if (nextValue === conversation.intervalOverrideMinutes) return;
      await updateConversation(conversation.id, { intervalOverrideMinutes: nextValue });
      showMessage(nextValue === null ? "Using global wake time." : `Wake time set to ${nextValue} min.`);
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
      await refresh();
    }
  };
  intervalInput.addEventListener("change", saveInterval);
  intervalInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      intervalInput.blur();
    }
  });

  run.addEventListener("click", async () => {
    try {
      run.disabled = true;
      showMessage("Sending wake...");
      const response = await request({ type: "bridge:run-now", conversationId: conversation.id });
      if (!response?.ok) throw new Error(response?.reason || response?.error || "run failed");
      showMessage("Wake sent.");
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
    } finally {
      run.disabled = false;
    }
  });

  remove.addEventListener("click", async () => {
    try {
      remove.disabled = true;
      const response = await request({ type: "bridge:remove-conversation", conversationId: conversation.id });
      if (!response?.ok) throw new Error(response?.error || "remove failed");
      showMessage("Conversation removed.");
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
      remove.disabled = false;
    }
  });

  card.append(header, meta, controls);
  return card;
}

function renderConversations(state, schedules = {}, runtime = null, githubOwnership = {}) {
  elements.conversationList.replaceChildren();
  const conversations = Object.values(state.conversations || {}).sort((a, b) => String(a.label || "").localeCompare(String(b.label || "")));
  elements.conversationCount.textContent = String(conversations.length);
  if (!conversations.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No conversations yet.";
    elements.conversationList.append(empty);
    return;
  }
  for (const conversation of conversations) {
    elements.conversationList.append(renderConversation(
      conversation,
      state.settings,
      schedules[conversation.id] || null,
      runtime,
      githubOwnership[conversation.id] || null
    ));
  }
}

function shortRevision(value) {
  const text = String(value || "").trim();
  return /^[0-9a-f]{40}$/.test(text) ? text.slice(0, 8) : "-";
}

function formatReasonCounts(value) {
  if (!value || typeof value !== "object") return "";
  return Object.entries(value)
    .filter(([, count]) => Number(count) > 0)
    .map(([reason, count]) => `${reason}×${count}`)
    .join(", ");
}

function setOperatorLine(element, text, title = "") {
  if (!element) return;
  element.textContent = text;
  element.title = title || text;
}

function renderOperatorStatus(response) {
  const state = response?.state || {};
  const bridge = response?.bridgeInfo || {};
  const envelope = response?.operatorStatus || { available: false, source: "not_configured" };
  const remote = envelope.status || {};
  const daemon = remote.daemon || {};
  const operator = remote.operator || {};
  const dedupe = remote.dedupe || {};
  const currentId = currentTab?.normalizedUrl
    ? protocol.conversationId(currentTab.normalizedUrl)
    : null;
  const fabric = currentId ? response?.fabricStatus?.[currentId] || null : null;
  const campaign = fabric?.currentCampaign || null;

  const bridgeVersion = String(bridge.extensionVersion || "?");
  const daemonVersion = String(daemon.daemon_version || "?");
  const revision = shortRevision(daemon.self_revision);
  setOperatorLine(
    elements.operatorVersions,
    `Bridge ${bridgeVersion} · Agent ${daemonVersion} · ${revision}`,
    `Bridge ${bridgeVersion}; Local Agent ${daemonVersion}; deployed revision ${daemon.self_revision || "unavailable"}`
  );

  const master = state.settings?.masterEnabled ? "Master on" : "Master off";
  if (!envelope.available) {
    const reason = envelope.source === "not_configured"
      ? "Agent status not configured"
      : envelope.source === "misconfigured"
        ? "Agent status configuration invalid"
        : envelope.source === "stale"
          ? "Agent status stale"
          : "Agent status unavailable";
    const unavailableOverall = envelope.source === "stale"
      ? "Stale"
      : envelope.source === "misconfigured"
        ? "Config error"
        : master;
    setOperatorLine(elements.operatorOverall, unavailableOverall);
    setOperatorLine(
      elements.operatorRuntime,
      reason,
      envelope.source === "stale"
        ? `last update ${remote.updated_at || "unknown"}`
        : (envelope.error || reason)
    );
  } else {
    const configured = operator.configured ? "configured" : "misconfigured";
    const enabled = operator.enabled ? "enabled" : "disabled";
    const activity = operator.running ? "running" : "idle";
    const overall = !operator.configured
      ? "Misconfigured"
      : !operator.enabled
        ? "Disabled"
        : operator.running
          ? "Running"
          : "Ready";
    setOperatorLine(elements.operatorOverall, overall);
    setOperatorLine(
      elements.operatorRuntime,
      `${master} · ${enabled}/${configured} · ${activity}`,
      operator.configuration_error || ""
    );
  }

  const active = operator.active_request;
  if (active) {
    setOperatorLine(
      elements.operatorGoal,
      `${active.workflow_id} · ${active.children_total} child${active.children_total === 1 ? "" : "ren"}`
    );
  } else {
    setOperatorLine(elements.operatorGoal, operator.running ? "Running request unavailable" : "No active operator workflow");
  }

  if (campaign) {
    setOperatorLine(
      elements.operatorCampaign,
      `${campaign.campaignId} · ${campaign.state} · ${campaign.capturedResultCount}/${campaign.childCount} results`,
      [
        campaign.pendingChildIds?.length ? `pending: ${campaign.pendingChildIds.join(", ")}` : "",
        campaign.failedChildIds?.length ? `failed: ${campaign.failedChildIds.join(", ")}` : "",
        campaign.ambiguousChildIds?.length ? `ambiguous: ${campaign.ambiguousChildIds.join(", ")}` : ""
      ].filter(Boolean).join("; ")
    );
    setOperatorLine(
      elements.operatorFeedback,
      `${campaign.feedbackState}${campaign.cleanupPending ? " · cleanup pending" : ""}`,
      campaign.partialFailure ? "Campaign has partial child failure." : ""
    );
  } else {
    setOperatorLine(
      elements.operatorCampaign,
      currentId ? "No Fabric campaign for current chat" : "Open a ChatGPT conversation"
    );
    setOperatorLine(elements.operatorFeedback, "No terminal feedback pending");
  }

  if (envelope.available) {
    const reasonSummary = [
      formatReasonCounts(dedupe.suppression_reasons),
      formatReasonCounts(dedupe.reconciliation_reasons),
      formatReasonCounts(dedupe.rejection_reasons)
    ].filter(Boolean).join("; ");
    setOperatorLine(
      elements.operatorDedupe,
      `${dedupe.suppressed_count || 0} suppressed · ${dedupe.reconciled_count || 0} reconciled · ${dedupe.rejected_count || 0} rejected${dedupe.scan_truncated ? " · bounded" : ""}`,
      reasonSummary || "No durable dedupe events in the current bounded evidence set."
    );
  } else {
    setOperatorLine(elements.operatorDedupe, "Agent telemetry unavailable");
  }
}

async function refreshCurrentTabForm(state) {
  currentTab = await getCurrentChatTab();
  if (!currentTab) {
    elements.currentTitle.textContent = "No ChatGPT conversation detected";
    elements.currentUrl.textContent = "Open a ChatGPT conversation, then open Bridge again.";
    elements.addCurrent.textContent = "Add current chat";
    elements.addCurrent.disabled = true;
    return;
  }
  const id = protocol.conversationId(currentTab.normalizedUrl);
  const existing = state.conversations?.[id];
  elements.currentTitle.textContent = existing?.label || chatLabelFromTitle(currentTab.title);
  elements.currentUrl.textContent = currentTab.normalizedUrl;
  elements.addCurrent.textContent = existing ? "Added" : "Add current chat";
  elements.addCurrent.disabled = Boolean(existing);
}

function renderSettings(state, runtime) {
  elements.masterEnabled.checked = Boolean(state.settings.masterEnabled);
  elements.runtimeUrl.value = state.settings.runtimeUrl || "";
  elements.fallbackInterval.value = String(state.settings.fallbackIntervalMinutes || 10);
  elements.fallbackRetry.value = String(state.settings.fallbackBusyRetryMinutes || 1);
  elements.fallbackWakePrompt.value = state.settings.fallbackWakePrompt || "";
  elements.fallbackBootstrapPrompt.value = state.settings.fallbackBootstrapPrompt || "";
  elements.runtimeSource.textContent = runtime?.source || "-";
  elements.runtimeInterval.textContent = runtime?.intervalMinutes ? `${runtime.intervalMinutes} min` : "-";
}

async function refresh() {
  const response = await request({ type: "bridge:get-state" });
  if (!response?.state) throw new Error(response?.error || "Could not load Bridge state.");
  latestState = response.state;
  latestRuntime = response.runtime || null;
  renderSettings(latestState, latestRuntime);
  renderConversations(latestState, response.schedules || {}, latestRuntime, response.githubOwnership || {});
  await refreshCurrentTabForm(latestState);
  renderOperatorStatus(response);
  restartCountdownTimer();
}

async function addOrUpdateCurrent() {
  currentTab = await getCurrentChatTab();
  if (!currentTab) throw new Error("Open a concrete ChatGPT conversation first.");
  const id = protocol.conversationId(currentTab.normalizedUrl);
  const existing = latestState?.conversations?.[id];
  if (existing) return;
  const capabilities = await injectContentScript(currentTab.id, currentTab.normalizedUrl);
  const response = await request({
    type: "bridge:upsert-conversation",
    conversation: {
      url: currentTab.normalizedUrl,
      label: chatLabelFromTitle(currentTab.title),
      enabled: false,
      preferredTabId: currentTab.id,
      assistantBaseline: capabilities?.assistantIdentity || ""
    }
  });
  if (!response?.ok) throw new Error(response?.error || "add failed");
  showMessage("Conversation added. NEXT or the switch can arm it.");
  await refresh();
}

async function saveGlobalSettings() {
  const interval = Number(elements.fallbackInterval.value);
  const retry = Number(elements.fallbackRetry.value);
  if (!Number.isFinite(interval) || interval < 1 || interval > 1440) throw new Error("Default interval must be between 1 and 1440 minutes.");
  if (!Number.isFinite(retry) || retry < 1 || retry > 60) throw new Error("Busy retry must be between 1 and 60 minutes.");
  const response = await request({
    type: "bridge:save-global-settings",
    settings: {
      runtimeUrl: elements.runtimeUrl.value.trim(),
      fallbackIntervalMinutes: interval,
      fallbackBusyRetryMinutes: retry,
      fallbackWakePrompt: elements.fallbackWakePrompt.value.trim(),
      fallbackBootstrapPrompt: elements.fallbackBootstrapPrompt.value.trim()
    }
  });
  if (!response?.ok) throw new Error(response?.error || "save failed");
  showMessage("Settings saved.");
  await refresh();
}

elements.masterEnabled.addEventListener("change", async () => {
  try {
    const response = await request({ type: "bridge:save-global-settings", settings: { masterEnabled: elements.masterEnabled.checked } });
    if (!response?.ok) throw new Error(response?.error || "master update failed");
    showMessage(elements.masterEnabled.checked ? "Master scheduling enabled." : "Master scheduling paused.");
    await refresh();
  } catch (error) {
    showMessage(`Error: ${error.message}`);
    await refresh();
  }
});

elements.addCurrent.addEventListener("click", () => {
  addOrUpdateCurrent().catch((error) => showMessage(`Error: ${error.message}`));
});

elements.saveGlobal.addEventListener("click", () => {
  saveGlobalSettings().catch((error) => showMessage(`Error: ${error.message}`));
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && changes.bridgeState) refresh().catch((error) => showMessage(`Error: ${error.message}`));
});

refresh().catch((error) => showMessage(`Error: ${error.message}`));
