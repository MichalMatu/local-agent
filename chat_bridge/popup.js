const protocol = globalThis.LocalAgentBridgeProtocol;

const elements = {
  masterEnabled: document.querySelector("#masterEnabled"),
  currentTitle: document.querySelector("#currentTitle"),
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
let countdownTimer = null;

function showMessage(text) {
  elements.message.textContent = text;
}

function formatTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

function formatRemaining(milliseconds) {
  const totalSeconds = Math.max(0, Math.ceil(Number(milliseconds) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function updateNextWakeElement(element) {
  const masterEnabled = element.dataset.masterEnabled === "true";
  const conversationEnabled = element.dataset.conversationEnabled === "true";
  const nextRunAt = element.dataset.nextRunAt || null;
  if (!masterEnabled) {
    element.textContent = "Next: master disabled";
    return;
  }
  if (!conversationEnabled) {
    element.textContent = "Next: paused";
    return;
  }
  const when = Date.parse(String(nextRunAt || ""));
  if (!Number.isFinite(when)) {
    element.textContent = "Next: not scheduled";
    return;
  }
  const remaining = when - Date.now();
  const relative = remaining <= 0 ? "due now" : `in ${formatRemaining(remaining)}`;
  element.textContent = `Next: ${relative} · ${formatTime(nextRunAt)}`;
}

function updateCountdowns() {
  document.querySelectorAll("[data-next-run-at]").forEach(updateNextWakeElement);
}

function restartCountdownTimer() {
  if (countdownTimer !== null) clearInterval(countdownTimer);
  updateCountdowns();
  countdownTimer = setInterval(updateCountdowns, 1000);
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

function renderConversation(conversation, settings, schedule) {
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
    (() => {
      const next = document.createElement("span");
      next.dataset.nextRunAt = schedule?.nextRunAt || "";
      next.dataset.masterEnabled = settings.masterEnabled ? "true" : "false";
      next.dataset.conversationEnabled = conversation.enabled ? "true" : "false";
      updateNextWakeElement(next);
      return next;
    })(),
    Object.assign(document.createElement("span"), {
      textContent: `Mode: ${runtimeState}`
    }),
    Object.assign(document.createElement("span"), {
      textContent: `Pacing: ${conversation.intervalOverrideMinutes === null ? "auto" : `${conversation.intervalOverrideMinutes} min override`}`
    })
  );

  const grid = document.createElement("div");
  grid.className = "card-grid";
  const labelWrap = document.createElement("div");
  const labelLabel = document.createElement("label");
  labelLabel.textContent = "Label";
  const labelInput = createTextInput(conversation.label);
  labelWrap.append(labelLabel, labelInput);

  const intervalWrap = document.createElement("div");
  intervalWrap.className = "full-width";
  const intervalLabel = document.createElement("label");
  intervalLabel.textContent = "Interval override (min, blank = auto)";
  const intervalInput = document.createElement("input");
  intervalInput.type = "number";
  intervalInput.min = "1";
  intervalInput.max = "1440";
  intervalInput.placeholder = "auto";
  intervalInput.value =
    conversation.intervalOverrideMinutes === null ? "" : String(conversation.intervalOverrideMinutes);
  intervalWrap.append(intervalLabel, intervalInput);
  grid.append(labelWrap, intervalWrap);

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
          intervalOverrideMinutes: intervalInput.value.trim()
            ? Number(intervalInput.value)
            : null
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
      showMessage(`Sending wake to ${conversation.label || conversation.id}...`);
      const response = await request({
        type: "bridge:run-now",
        conversationId: conversation.id
      });
      if (!response?.ok) throw new Error(response?.reason || response?.error || "run failed");
      showMessage(`Sent ${response.bridgeMode || "wake"} to ${conversation.label || conversation.id}.`);
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

function renderConversations(state, schedules = {}) {
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
      renderConversation(conversation, state.settings, schedules[conversation.id] || null)
    );
  }
}

async function refreshCurrentTabForm(state) {
  currentTab = await getCurrentChatTab();
  if (!currentTab) {
    elements.currentTitle.textContent = "No ChatGPT conversation detected";
    elements.currentUrl.textContent = "Open a concrete ChatGPT conversation, then open this popup again.";
    elements.addCurrent.textContent = "Add current chat";
    elements.addCurrent.disabled = true;
    return;
  }

  const id = protocol.conversationId(currentTab.normalizedUrl);
  const existing = state.conversations?.[id];
  elements.currentTitle.textContent = existing?.label || chatLabelFromTitle(currentTab.title);
  elements.currentUrl.textContent = currentTab.normalizedUrl;
  elements.addCurrent.textContent = existing ? "Update current chat" : "Add current chat";
  elements.addCurrent.disabled = false;
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

  renderConversations(latestState, response.schedules || {});
  restartCountdownTimer();
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

  const id = protocol.conversationId(currentTab.normalizedUrl);
  const existing = latestState?.conversations?.[id];
  await injectContentScript(currentTab.id);

  const response = await request({
    type: "bridge:upsert-conversation",
    conversation: {
      url: currentTab.normalizedUrl,
      label: existing?.label || chatLabelFromTitle(currentTab.title),
      enabled: existing ? Boolean(existing.enabled) : true,
      preferredTabId: currentTab.id
    }
  });
  if (!response?.ok) throw new Error(response?.error || "save failed");
  showMessage(existing ? "Current conversation updated." : "Current conversation added and scheduled.");
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

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName !== "local" || !changes.bridgeState) return;
  refresh().catch((error) => showMessage(`Error: ${error.message}`));
});

refresh().catch((error) => showMessage(`Error: ${error.message}`));
