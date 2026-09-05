const protocol = globalThis.LocalAgentBridgeProtocol;
const CONTENT_PROTOCOL_VERSION = 2;

const elements = {
  masterEnabled: document.querySelector("#masterEnabled"),
  currentTitle: document.querySelector("#currentTitle"),
  currentUrl: document.querySelector("#currentUrl"),
  currentAgent: document.querySelector("#currentAgent"),
  addCurrent: document.querySelector("#addCurrent"),
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
  const update = () =>
    document.querySelectorAll("[data-next-run-at]").forEach(updateNextWakeElement);
  update();
  countdownTimer = setInterval(update, 1000);
}

function chatLabelFromTitle(title) {
  const cleaned = String(title || "")
    .replace(/\s*[|–—-]\s*ChatGPT\s*$/i, "")
    .trim();
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

async function probeContentScript(tabId, expectedUrl) {
  try {
    const response = await chrome.tabs.sendMessage(
      tabId,
      { type: "bridge:capabilities", expectedUrl, protocolVersion: CONTENT_PROTOCOL_VERSION },
      { frameId: 0 }
    );
    return { reachable: true, response };
  } catch (error) {
    return { reachable: false, error };
  }
}

async function injectContentScript(tabId, expectedUrl) {
  const before = await probeContentScript(tabId, expectedUrl);
  if (before.response?.ok && before.response.protocolVersion === CONTENT_PROTOCOL_VERSION) return;
  if (before.reachable) {
    throw new Error("This ChatGPT tab has an older Bridge content script. Reload the tab, then try again.");
  }
  try {
    await chrome.scripting.executeScript({ target: { tabId }, files: ["control_protocol.js", "content.js"] });
  } catch (error) {
    throw new Error(`Cannot activate bridge in this tab: ${error.message}`);
  }
  const after = await probeContentScript(tabId, expectedUrl);
  if (!after.response?.ok || after.response.protocolVersion !== CONTENT_PROTOCOL_VERSION) {
    throw new Error("Bridge content script did not become ready. Reload the ChatGPT tab, then try again.");
  }
}

function agentLabel(agent) {
  return `${agent.repositoryId} · ${agent.repository}`;
}

function createAgentSelect(agents, selectedBinding = null, includeBlank = true) {
  const select = document.createElement("select");
  if (includeBlank) {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Choose repository...";
    select.append(blank);
  }
  for (const agent of agents || []) {
    const option = document.createElement("option");
    option.value = agent.agentBinding;
    option.textContent = agentLabel(agent);
    select.append(option);
  }
  select.value = selectedBinding || "";
  return select;
}

function replaceSelectOptions(select, agents, selectedBinding = null, includeBlank = true) {
  const fresh = createAgentSelect(agents, selectedBinding, includeBlank);
  select.replaceChildren(...fresh.childNodes);
  select.value = selectedBinding || "";
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

async function resolvePendingDelivery(conversation, wasSent) {
  const response = await request({
    type: "bridge:resolve-delivery",
    conversationId: conversation.id,
    wasSent
  });
  if (!response?.ok) throw new Error(response?.error || "delivery resolution failed");
}

async function updateConversation(conversationId, patch) {
  const response = await request({ type: "bridge:update-conversation", conversationId, patch });
  if (!response?.ok) throw new Error(response?.error || "update failed");
  return response.conversation;
}

function renderConversation(conversation, settings, schedule, runtime) {
  const card = document.createElement("article");
  card.className = "conversation-card";
  if (!conversation.enabled) card.classList.add("is-paused");
  if (conversation.pendingDelivery) card.classList.add("has-pending-delivery");

  const header = document.createElement("div");
  header.className = "card-header";

  const titleBlock = document.createElement("div");
  titleBlock.className = "card-title-block";
  const titleLine = document.createElement("div");
  titleLine.className = "card-title-line";
  const title = makeMeta(conversation.label || conversation.id, "card-title");
  title.title = conversation.label || conversation.id;
  const repo = makeMeta(conversation.repositoryId || "UNBOUND", "repo-badge");
  titleLine.append(title, repo);
  titleBlock.append(titleLine);

  const enableLabel = document.createElement("label");
  enableLabel.className = "enable-check";
  enableLabel.title = conversation.pendingDelivery
    ? "Resolve the uncertain delivery or remove this chat."
    : "Enable or pause scheduled wakes.";
  const enabled = document.createElement("input");
  enabled.type = "checkbox";
  enabled.checked = Boolean(conversation.enabled);
  enabled.disabled = Boolean(conversation.pendingDelivery);
  enabled.setAttribute("aria-label", `Enable ${conversation.label || conversation.id}`);
  const checkVisual = makeMeta("✓", "check-visual");
  enableLabel.append(enabled, checkVisual);
  header.append(titleBlock, enableLabel);

  const meta = document.createElement("div");
  meta.className = "card-meta";
  const status = makeMeta(conversation.lastStatus || "ready", "status-text");
  status.title = `Last status: ${conversation.lastStatus || "ready"}`;
  const next = makeMeta("", "next-wake");
  next.dataset.nextRunAt = schedule?.nextRunAt || "";
  next.dataset.masterEnabled = settings.masterEnabled ? "true" : "false";
  next.dataset.conversationEnabled = conversation.enabled ? "true" : "false";
  updateNextWakeElement(next);
  meta.append(status, next);

  let pendingResolution = null;
  if (conversation.pendingDelivery) {
    pendingResolution = document.createElement("div");
    pendingResolution.className = "delivery-resolution";
    const pendingText = makeMeta("Delivery uncertain", "delivery-label");
    pendingText.title = "Bridge cannot prove whether the previous wake reached ChatGPT.";
    const sent = makeButton("✓", "resolution-icon resolution-sent");
    sent.setAttribute("aria-label", "Confirm wake was sent");
    sent.title = "Wake was sent";
    const notSent = makeButton("×", "resolution-icon resolution-not-sent");
    notSent.setAttribute("aria-label", "Confirm wake was not sent");
    notSent.title = "Wake was not sent";

    sent.addEventListener("click", async () => {
      try {
        await resolvePendingDelivery(conversation, true);
        showMessage("Wake marked as sent.");
        await refresh();
      } catch (error) {
        showMessage(`Error: ${error.message}`);
      }
    });
    notSent.addEventListener("click", async () => {
      try {
        await resolvePendingDelivery(conversation, false);
        showMessage("Wake marked as not sent.");
        await refresh();
      } catch (error) {
        showMessage(`Error: ${error.message}`);
      }
    });
    pendingResolution.append(pendingText, sent, notSent);
  }

  const controls = document.createElement("div");
  controls.className = "card-controls";

  const wakeField = document.createElement("label");
  wakeField.className = "wake-field";
  const wakeLabel = makeMeta("Wake every", "field-label");
  const wakeInputWrap = document.createElement("div");
  wakeInputWrap.className = "wake-input-wrap";
  const intervalInput = document.createElement("input");
  intervalInput.type = "number";
  intervalInput.min = "1";
  intervalInput.max = "1440";
  intervalInput.placeholder = String(runtime?.intervalMinutes || settings.fallbackIntervalMinutes || 10);
  intervalInput.value = conversation.intervalOverrideMinutes === null
    ? ""
    : String(conversation.intervalOverrideMinutes);
  intervalInput.disabled = Boolean(conversation.pendingDelivery);
  intervalInput.title = `Leave empty to use global default (${runtime?.intervalMinutes || settings.fallbackIntervalMinutes || 10} min).`;
  const unit = makeMeta("min");
  wakeInputWrap.append(intervalInput, unit);
  wakeField.append(wakeLabel, wakeInputWrap);

  const run = makeButton("Run now", "run-button");
  run.disabled = Boolean(conversation.pendingDelivery);
  const remove = makeButton("Remove", "remove-button");
  controls.append(wakeField, run, remove);

  enabled.addEventListener("change", async () => {
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
      showMessage(`Sending wake to ${conversation.repositoryId}...`);
      const response = await request({ type: "bridge:run-now", conversationId: conversation.id });
      if (!response?.ok) throw new Error(response?.reason || response?.error || "run failed");
      showMessage(`Wake sent to ${response.repositoryId}.`);
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
      if (conversation.pendingDelivery) await resolvePendingDelivery(conversation, false);
      const response = await request({ type: "bridge:remove-conversation", conversationId: conversation.id });
      if (!response?.ok) throw new Error(response?.error || "remove failed");
      showMessage("Conversation removed.");
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
      remove.disabled = false;
    }
  });

  card.append(header, meta);
  if (pendingResolution) card.append(pendingResolution);
  card.append(controls);
  return card;
}

function renderConversations(state, schedules = {}, runtime = null) {
  elements.conversationList.replaceChildren();
  const conversations = Object.values(state.conversations || {}).sort((a, b) =>
    String(a.label || "").localeCompare(String(b.label || ""))
  );
  elements.conversationCount.textContent = String(conversations.length);
  if (!conversations.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No conversations yet.";
    elements.conversationList.append(empty);
    return;
  }
  for (const conversation of conversations) {
    elements.conversationList.append(
      renderConversation(conversation, state.settings, schedules[conversation.id] || null, runtime)
    );
  }
}

async function refreshCurrentTabForm(state, runtime) {
  currentTab = await getCurrentChatTab();
  if (!currentTab) {
    elements.currentTitle.textContent = "No ChatGPT conversation detected";
    elements.currentUrl.textContent = "Open a ChatGPT conversation, then open Bridge again.";
    replaceSelectOptions(elements.currentAgent, runtime?.agents || [], null, true);
    elements.currentAgent.disabled = true;
    elements.addCurrent.textContent = "Add current chat";
    elements.addCurrent.disabled = true;
    return;
  }

  const id = protocol.conversationId(currentTab.normalizedUrl);
  const existing = state.conversations?.[id];
  elements.currentTitle.textContent = existing?.label || chatLabelFromTitle(currentTab.title);
  elements.currentUrl.textContent = currentTab.normalizedUrl;
  replaceSelectOptions(elements.currentAgent, runtime?.agents || [], existing?.agentBinding || null, true);
  elements.currentAgent.disabled = Boolean(existing);
  elements.addCurrent.textContent = existing ? "Already added" : "Add current chat";
  elements.addCurrent.disabled = Boolean(existing) || !elements.currentAgent.value;
}

async function refresh() {
  const response = await request({ type: "bridge:get-state" });
  if (response?.error) throw new Error(response.error);
  latestState = response.state;
  latestRuntime = response.runtime;
  const { settings } = latestState;

  elements.masterEnabled.checked = Boolean(settings.masterEnabled);
  elements.runtimeUrl.value = settings.runtimeUrl || "";
  elements.fallbackInterval.value = settings.fallbackIntervalMinutes;
  elements.fallbackRetry.value = settings.fallbackBusyRetryMinutes;
  elements.fallbackWakePrompt.value = settings.fallbackWakePrompt || "";
  elements.fallbackBootstrapPrompt.value = settings.fallbackBootstrapPrompt || "";
  elements.runtimeSource.textContent = response.runtime?.source || "-";
  elements.runtimeInterval.textContent = `${response.runtime?.intervalMinutes || settings.fallbackIntervalMinutes} min`;

  renderConversations(latestState, response.schedules || {}, response.runtime || null);
  restartCountdownTimer();
  await refreshCurrentTabForm(latestState, response.runtime || null);
}

async function saveGlobal() {
  const response = await request({
    type: "bridge:save-global-settings",
    settings: {
      masterEnabled: elements.masterEnabled.checked,
      runtimeUrl: elements.runtimeUrl.value,
      fallbackIntervalMinutes: Number(elements.fallbackInterval.value),
      fallbackBusyRetryMinutes: Number(elements.fallbackRetry.value),
      fallbackWakePrompt: elements.fallbackWakePrompt.value,
      fallbackBootstrapPrompt: elements.fallbackBootstrapPrompt.value
    }
  });
  if (!response?.ok) throw new Error(response?.error || "save failed");
  showMessage("Global settings saved.");
  await refresh();
}

async function addCurrent() {
  currentTab = await getCurrentChatTab();
  if (!currentTab) throw new Error("Open a concrete ChatGPT conversation first.");
  const id = protocol.conversationId(currentTab.normalizedUrl);
  if (latestState?.conversations?.[id]) return;
  const agentBinding = elements.currentAgent.value;
  if (!agentBinding) throw new Error("Choose repository first.");
  await injectContentScript(currentTab.id, currentTab.normalizedUrl);

  const response = await request({
    type: "bridge:upsert-conversation",
    conversation: {
      url: currentTab.normalizedUrl,
      label: chatLabelFromTitle(currentTab.title),
      enabled: true,
      preferredTabId: currentTab.id,
      agentBinding
    }
  });
  if (!response?.ok) throw new Error(response?.error || "add failed");
  showMessage(`Added ${response.conversation.repositoryId}.`);
  await refresh();
}

elements.masterEnabled.addEventListener("change", () => {
  saveGlobal().catch((error) => {
    showMessage(`Error: ${error.message}`);
    refresh().catch(() => undefined);
  });
});

elements.currentAgent.addEventListener("change", () => {
  if (!currentTab) return;
  const id = protocol.conversationId(currentTab.normalizedUrl);
  if (!latestState?.conversations?.[id]) elements.addCurrent.disabled = !elements.currentAgent.value;
});

elements.saveGlobal.addEventListener("click", () => {
  saveGlobal().catch((error) => showMessage(`Error: ${error.message}`));
});

elements.addCurrent.addEventListener("click", () => {
  addCurrent().catch((error) => showMessage(`Error: ${error.message}`));
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes.bridgeState) return;
  refresh().catch((error) => showMessage(`Error: ${error.message}`));
});

refresh().catch((error) => showMessage(`Error: ${error.message}`));