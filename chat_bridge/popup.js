const protocol = globalThis.LocalAgentBridgeProtocol;

const elements = {
  masterEnabled: document.querySelector("#masterEnabled"),
  currentLabel: document.querySelector("#currentLabel"),
  currentRepository: document.querySelector("#currentRepository"),
  currentUrl: document.querySelector("#currentUrl"),
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
let currentTab = null;

function showMessage(text) {
  elements.message.textContent = text;
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

async function request(message) {
  return chrome.runtime.sendMessage(message);
}

async function getCurrentChatTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const normalized = protocol.normalizeConversationUrl(tab?.url || "");
  if (!tab?.id || !normalized) return null;
  return { ...tab, normalizedUrl: normalized };
}

async function injectContentScript(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["control_protocol.js", "content.js"]
    });
  } catch (error) {
    throw new Error(`Cannot activate bridge in this tab: ${error.message}`);
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

function renderConversation(conversation) {
  const card = document.createElement("article");
  card.className = "conversation-card";

  const header = document.createElement("div");
  header.className = "card-header";

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = conversation.label || conversation.id;

  const toggleLabel = document.createElement("label");
  toggleLabel.className = "switch-row compact";
  const enabled = document.createElement("input");
  enabled.type = "checkbox";
  enabled.checked = Boolean(conversation.enabled);
  const enabledText = document.createElement("span");
  enabledText.textContent = enabled.checked ? "Enabled" : "Paused";
  toggleLabel.append(enabled, enabledText);
  header.append(title, toggleLabel);

  const meta = document.createElement("div");
  meta.className = "card-meta";
  const runtimeState = conversation.bootstrapPending ? "bootstrap pending" : "compact wake";
  meta.append(
    Object.assign(document.createElement("span"), {
      textContent: `Last: ${conversation.lastStatus || "-"}`
    }),
    Object.assign(document.createElement("span"), {
      textContent: `Next: ${formatTime(conversation.nextRunAt)}`
    }),
    Object.assign(document.createElement("span"), {
      textContent: `Mode: ${runtimeState}`
    })
  );

  const grid = document.createElement("div");
  grid.className = "card-grid";
  const labelWrap = document.createElement("div");
  const labelLabel = document.createElement("label");
  labelLabel.textContent = "Label";
  const labelInput = createTextInput(conversation.label);
  labelWrap.append(labelLabel, labelInput);

  const repoWrap = document.createElement("div");
  const repoLabel = document.createElement("label");
  repoLabel.textContent = "Repository id";
  const repoInput = createTextInput(conversation.repositoryId, "optional");
  repoWrap.append(repoLabel, repoInput);
  grid.append(labelWrap, repoWrap);

  const actions = document.createElement("div");
  actions.className = "card-actions";
  const save = document.createElement("button");
  save.type = "button";
  save.textContent = "Save";
  const run = document.createElement("button");
  run.type = "button";
  run.textContent = "Run now";
  const remove = document.createElement("button");
  remove.type = "button";
  remove.textContent = "Remove";
  remove.className = "danger";
  actions.append(save, run, remove);

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
          repositoryId: repoInput.value
        }
      });
      if (!response?.ok) throw new Error(response?.error || "save failed");
      showMessage("Conversation saved.");
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
    }
  });

  run.addEventListener("click", async () => {
    try {
      run.disabled = true;
      showMessage(`Sending wake to ${conversation.label}...`);
      const response = await request({
        type: "bridge:run-now",
        conversationId: conversation.id
      });
      if (!response?.ok) throw new Error(response?.reason || response?.error || "run failed");
      showMessage(`Sent ${response.bridgeMode || "wake"} to ${conversation.label}.`);
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
    } finally {
      run.disabled = false;
    }
  });

  remove.addEventListener("click", async () => {
    try {
      const response = await request({
        type: "bridge:remove-conversation",
        conversationId: conversation.id
      });
      if (!response?.ok) throw new Error(response?.error || "remove failed");
      showMessage("Conversation removed.");
      await refresh();
    } catch (error) {
      showMessage(`Error: ${error.message}`);
    }
  });

  card.append(header, meta, grid, actions);
  return card;
}

function renderConversations(state) {
  elements.conversationList.replaceChildren();
  const conversations = Object.values(state.conversations || {}).sort((a, b) =>
    String(a.label || "").localeCompare(String(b.label || ""))
  );
  elements.conversationCount.textContent = String(conversations.length);
  for (const conversation of conversations) {
    elements.conversationList.append(renderConversation(conversation));
  }
}

async function refreshCurrentTabForm(state) {
  currentTab = await getCurrentChatTab();
  if (!currentTab) {
    elements.currentUrl.textContent = "Open a concrete ChatGPT conversation.";
    elements.addCurrent.disabled = true;
    return;
  }
  elements.addCurrent.disabled = false;
  elements.currentUrl.textContent = currentTab.normalizedUrl;
  const id = protocol.conversationId(currentTab.normalizedUrl);
  const existing = state.conversations?.[id];
  if (existing) {
    elements.currentLabel.value = existing.label || "";
    elements.currentRepository.value = existing.repositoryId || "";
  } else if (!elements.currentLabel.value) {
    elements.currentLabel.value = String(currentTab.title || "ChatGPT conversation")
      .replace(/\s*[|–-]\s*ChatGPT\s*$/i, "")
      .slice(0, 120);
    elements.currentRepository.value = "";
  }
}

async function refresh() {
  const response = await request({ type: "bridge:get-state" });
  if (response?.error) throw new Error(response.error);
  latestState = response.state;
  const { settings } = latestState;

  elements.masterEnabled.checked = Boolean(settings.masterEnabled);
  elements.runtimeUrl.value = settings.runtimeUrl || "";
  elements.fallbackInterval.value = settings.fallbackIntervalMinutes;
  elements.fallbackRetry.value = settings.fallbackBusyRetryMinutes;
  elements.fallbackWakePrompt.value = settings.fallbackWakePrompt || "";
  elements.fallbackBootstrapPrompt.value = settings.fallbackBootstrapPrompt || "";
  elements.runtimeSource.textContent = response.runtime?.source || "-";
  elements.runtimeInterval.textContent = `${response.runtime?.intervalMinutes || settings.fallbackIntervalMinutes} min`;

  renderConversations(latestState);
  await refreshCurrentTabForm(latestState);
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
  await injectContentScript(currentTab.id);
  const response = await request({
    type: "bridge:upsert-conversation",
    conversation: {
      url: currentTab.normalizedUrl,
      label: elements.currentLabel.value || currentTab.title || "ChatGPT conversation",
      repositoryId: elements.currentRepository.value,
      enabled: true,
      preferredTabId: currentTab.id
    }
  });
  if (!response?.ok) throw new Error(response?.error || "save failed");
  showMessage("Current conversation added and scheduled.");
  await refresh();
}

elements.masterEnabled.addEventListener("change", () => {
  saveGlobal().catch((error) => {
    showMessage(`Error: ${error.message}`);
    refresh().catch(() => undefined);
  });
});

elements.saveGlobal.addEventListener("click", () => {
  saveGlobal().catch((error) => showMessage(`Error: ${error.message}`));
});

elements.addCurrent.addEventListener("click", () => {
  addOrUpdateCurrent().catch((error) => showMessage(`Error: ${error.message}`));
});

refresh().catch((error) => showMessage(`Error: ${error.message}`));
