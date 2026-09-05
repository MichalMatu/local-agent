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

function showMessage(text) {
  elements.message.textContent = text;
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
      {
        type: "bridge:capabilities",
        expectedUrl,
        protocolVersion: CONTENT_PROTOCOL_VERSION
      },
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
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["control_protocol.js", "content.js"]
    });
  } catch (error) {
    throw new Error(`Cannot activate bridge in this tab: ${error.message}`);
  }

  const after = await probeContentScript(tabId, expectedUrl);
  if (!after.response?.ok || after.response.protocolVersion !== CONTENT_PROTOCOL_VERSION) {
    throw new Error("Bridge content script did not become ready. Reload the ChatGPT tab, then try again.");
  }
}

function createTextInput(value, placeholder = "") {
  const input = document.createElement("input");
  input.type = "text";
  input.value = value || "";
  input.placeholder = placeholder;
  input.maxLength = 120;
  return input;
}

function agentLabel(agent) {
  const mode = agent.executionEnabled === false ? "bridge only" : "executor";
  return `${agent.repositoryId} · ${agent.repository} · ${mode}`;
}

function createAgentSelect(agents, selectedBinding = null, includeBlank = true) {
  const select = document.createElement("select");
  if (includeBlank) {
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Select agent binding...";
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
  return response;
}

function renderConversation(conversation, settings, schedule, runtime) {
  const card = document.createElement("article");
  card.className = "conversation-card";
  if (conversation.pendingDelivery) card.classList.add("has-pending-delivery");

  const header = document.createElement("div");
  header.className = "card-header";

  const titleBlock = document.createElement("div");
  titleBlock.className = "card-title-block";
  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = conversation.label || conversation.id;
  const repo = makeMeta(
    conversation.agentBinding ? conversation.repositoryId : "UNBOUND",
    "repo-badge"
  );
  titleBlock.append(title, repo);

  const toggleLabel = document.createElement("label");
  toggleLabel.className = "switch-row compact";
  const enabled = document.createElement("input");
  enabled.type = "checkbox";
  enabled.checked = Boolean(conversation.enabled);
  enabled.disabled = Boolean(conversation.pendingDelivery);
  const enabledText = document.createElement("span");
  enabledText.textContent = enabled.checked ? "On" : "Off";
  toggleLabel.title = conversation.pendingDelivery
    ? "Resolve the uncertain delivery before changing scheduling."
    : "Enable or pause scheduled wakes.";
  toggleLabel.append(enabled, enabledText);
  header.append(titleBlock, toggleLabel);

  const meta = document.createElement("div");
  meta.className = "card-meta compact-meta";
  const status = makeMeta(conversation.lastStatus || "-", "status-text");
  status.title = `Last status: ${conversation.lastStatus || "-"}`;

  const next = makeMeta("", "next-wake");
  next.dataset.nextRunAt = schedule?.nextRunAt || "";
  next.dataset.masterEnabled = settings.masterEnabled ? "true" : "false";
  next.dataset.conversationEnabled = conversation.enabled ? "true" : "false";
  updateNextWakeElement(next);

  const mode = conversation.bootstrapPending
    ? "Bootstrap"
    : conversation.intervalOverrideMinutes === null
      ? "Auto"
      : `${conversation.intervalOverrideMinutes}m`;
  meta.append(status, next, makeMeta(mode, "mode-badge"));

  const primaryActions = document.createElement("div");
  primaryActions.className = "card-actions compact-actions";

  const run = makeButton("Run", "small-action");
  run.disabled = Boolean(conversation.pendingDelivery);

  const edit = document.createElement("details");
  edit.className = "card-editor";
  const editSummary = document.createElement("summary");
  editSummary.textContent = "Edit";
  editSummary.className = "button-like";
  edit.append(editSummary);

  const editorBody = document.createElement("div");
  editorBody.className = "editor-body";

  const grid = document.createElement("div");
  grid.className = "card-grid compact-grid";

  const labelWrap = document.createElement("div");
  const labelLabel = document.createElement("label");
  labelLabel.textContent = "Label";
  const labelInput = createTextInput(conversation.label);
  labelWrap.append(labelLabel, labelInput);

  const intervalWrap = document.createElement("div");
  const intervalLabel = document.createElement("label");
  intervalLabel.textContent = "Interval (min)";
  const intervalInput = document.createElement("input");
  intervalInput.type = "number";
  intervalInput.min = "1";
  intervalInput.max = "1440";
  intervalInput.placeholder = "auto";
  intervalInput.value =
    conversation.intervalOverrideMinutes === null ? "" : String(conversation.intervalOverrideMinutes);
  intervalWrap.append(intervalLabel, intervalInput);

  const bindingWrap = document.createElement("div");
  bindingWrap.className = "full-width";
  const bindingLabel = document.createElement("label");
  bindingLabel.textContent = "Repository binding";
  const bindingSelect = createAgentSelect(runtime?.agents || [], conversation.agentBinding, true);
  bindingWrap.append(bindingLabel, bindingSelect);
  grid.append(labelWrap, intervalWrap, bindingWrap);

  const editActions = document.createElement("div");
  editActions.className = "editor-actions";
  const save = makeButton("Save", "small-action");
  const rebind = makeButton(conversation.agentBinding ? "Rebind" : "Bind", "small-action");
  rebind.disabled = Boolean(conversation.pendingDelivery);
  editActions.append(save, rebind);
  editorBody.append(grid, editActions);
  edit.append(editorBody);

  const remove = makeButton("Remove", "danger small-action");
  primaryActions.append(run, edit, remove);

  let pendingResolution = null;
  if (conversation.pendingDelivery) {
    pendingResolution = document.createElement("div");
    pendingResolution.className = "delivery-resolution";
    const pendingText = makeMeta("Delivery uncertain", "delivery-label");
    pendingText.title =
      "Bridge cannot prove whether the previous wake reached ChatGPT. Confirm what you see in this chat.";

    const sent = makeButton("✓", "resolution-icon resolution-sent");
    sent.setAttribute("aria-label", "Confirm wake was sent");
    sent.title = "Wake was sent";

    const notSent = makeButton("×", "resolution-icon resolution-not-sent");
    notSent.setAttribute("aria-label", "Confirm wake was not sent");
    notSent.title = "Wake was not sent";

    sent.addEventListener("click", async () => {
      try {
        if (!confirm("Confirm that the previous wake is visible in this chat?")) return;
        await resolvePendingDelivery(conversation, true);
        showMessage("Previous wake marked as sent. Conversation remains paused until you resume it.");
        await refresh();
      } catch (error) {
        showMessage(`Error: ${error.message}`);
      }
    });

    notSent.addEventListener("click", async () => {
      try {
        if (!confirm("Confirm that the previous wake was not sent?")) return;
        await resolvePendingDelivery(conversation, false);
        showMessage("Previous wake marked as not sent. Conversation remains paused until you resume it.");
        await refresh();
      } catch (error) {
        showMessage(`Error: ${error.message}`);
      }
    });

    pendingResolution.append(pendingText, sent, notSent);
  }

  enabled.addEventListener("change", async () => {
    try {
      const response = await request({
        type: "bridge:update-conversation",
        conversationId: conversation.id,
        patch: { enabled: enabled.checked }
      });
      if (!response?.ok) throw new Error(response?.error || "update failed");
      showMessage(enabled.checked ? "Conversation resumed." : "Conversation paused.");
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
      await refresh();
    }
  });

  save.addEventListener("click", async () => {
    try {
      const response = await request({
        type: "bridge:update-conversation",
        conversationId: conversation.id,
        patch: {
          label: labelInput.value,
          intervalOverrideMinutes: intervalInput.value.trim()
            ? Number(intervalInput.value)
            : null
        }
      });
      if (!response?.ok) throw new Error(response?.error || "save failed");
      showMessage("Conversation saved. Binding unchanged.");
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
    }
  });

  rebind.addEventListener("click", async () => {
    try {
      const agentBinding = bindingSelect.value;
      if (!agentBinding) throw new Error("Select an agent binding first.");
      if (agentBinding === conversation.agentBinding) {
        showMessage("Binding is already set to this agent.");
        return;
      }
      const target = (runtime?.agents || []).find((agent) => agent.agentBinding === agentBinding);
      const description = target ? `${target.repositoryId} (${target.repository})` : agentBinding;
      if (!confirm(`Rebind this conversation to ${description}? This resets bootstrap state.`)) return;
      const response = await request({
        type: "bridge:rebind-conversation",
        conversationId: conversation.id,
        binding: { agentBinding }
      });
      if (!response?.ok) throw new Error(response?.error || "rebind failed");
      showMessage(`Conversation rebound to ${response.conversation.repositoryId}.`);
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
    }
  });

  run.addEventListener("click", async () => {
    try {
      run.disabled = true;
      showMessage(`Sending bound wake to ${conversation.label || conversation.id}...`);
      const response = await request({
        type: "bridge:run-now",
        conversationId: conversation.id
      });
      if (!response?.ok) throw new Error(response?.reason || response?.error || "run failed");
      showMessage(`Sent ${response.bridgeMode || "wake"} to ${response.repositoryId}.`);
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
    } finally {
      run.disabled = false;
    }
  });

  remove.addEventListener("click", async () => {
    try {
      const unresolved = Boolean(conversation.pendingDelivery);
      const prompt = unresolved
        ? "Remove this conversation? Its previous wake is unresolved. Removal will mark that attempt as not sent, discard its journal, and will not send anything."
        : "Remove this conversation from Local Agent Chat Bridge?";
      if (!confirm(prompt)) return;

      if (unresolved) await resolvePendingDelivery(conversation, false);

      const response = await request({
        type: "bridge:remove-conversation",
        conversationId: conversation.id
      });
      if (!response?.ok) throw new Error(response?.error || "remove failed");
      showMessage("Conversation removed.");
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
      await refresh();
    }
  });

  if (conversation.pendingDelivery) {
    editSummary.classList.add("disabled-summary");
    editSummary.title = "Resolve the uncertain delivery first.";
    edit.addEventListener("toggle", () => {
      if (edit.open) edit.open = false;
    });
  }

  card.append(header, meta);
  if (pendingResolution) card.append(pendingResolution);
  card.append(primaryActions);
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
    empty.className = "muted";
    empty.textContent = "No conversations configured.";
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
    elements.currentUrl.textContent = "Open a concrete ChatGPT conversation, then open this popup again.";
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
  elements.currentAgent.disabled = Boolean(existing?.agentBinding);
  elements.addCurrent.textContent = existing ? "Update current chat" : "Add current chat";
  elements.addCurrent.disabled = !existing && !elements.currentAgent.value;
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
  elements.runtimeInterval.textContent =
    `${response.runtime?.intervalMinutes || settings.fallbackIntervalMinutes} min`;

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

async function addOrUpdateCurrent() {
  currentTab = await getCurrentChatTab();
  if (!currentTab) throw new Error("Open a concrete ChatGPT conversation first.");

  const id = protocol.conversationId(currentTab.normalizedUrl);
  const existing = latestState?.conversations?.[id];
  const agentBinding = existing?.agentBinding || elements.currentAgent.value;
  if (!agentBinding) throw new Error("Select the exact agent/repository binding first.");
  await injectContentScript(currentTab.id, currentTab.normalizedUrl);

  const response = await request({
    type: "bridge:upsert-conversation",
    conversation: {
      url: currentTab.normalizedUrl,
      label: existing?.label || chatLabelFromTitle(currentTab.title),
      enabled: existing ? Boolean(existing.enabled) : true,
      preferredTabId: currentTab.id,
      agentBinding
    }
  });
  if (!response?.ok) throw new Error(response?.error || "save failed");
  showMessage(
    existing
      ? `Current conversation updated; binding remains ${response.conversation.repositoryId}.`
      : `Current conversation bound to ${response.conversation.repositoryId} and scheduled.`
  );
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
  const existing = latestState?.conversations?.[id];
  if (!existing) elements.addCurrent.disabled = !elements.currentAgent.value;
});

elements.saveGlobal.addEventListener("click", () => {
  saveGlobal().catch((error) => showMessage(`Error: ${error.message}`));
});

elements.addCurrent.addEventListener("click", () => {
  addOrUpdateCurrent().catch((error) => showMessage(`Error: ${error.message}`));
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes.bridgeState) return;
  refresh().catch((error) => showMessage(`Error: ${error.message}`));
});

refresh().catch((error) => showMessage(`Error: ${error.message}`));
