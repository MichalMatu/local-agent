const elements = {
  enabled: document.querySelector("#enabled"),
  conversationUrl: document.querySelector("#conversationUrl"),
  runtimeUrl: document.querySelector("#runtimeUrl"),
  fallbackInterval: document.querySelector("#fallbackInterval"),
  fallbackRetry: document.querySelector("#fallbackRetry"),
  fallbackPrompt: document.querySelector("#fallbackPrompt"),
  runtimeSource: document.querySelector("#runtimeSource"),
  runtimeInterval: document.querySelector("#runtimeInterval"),
  lastStatus: document.querySelector("#lastStatus"),
  nextRun: document.querySelector("#nextRun"),
  message: document.querySelector("#message"),
  save: document.querySelector("#save"),
  runNow: document.querySelector("#runNow"),
  useCurrent: document.querySelector("#useCurrent")
};

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

async function refresh() {
  const response = await request({ type: "bridge:get-state" });
  if (response?.error) throw new Error(response.error);
  const { state, runtime } = response;

  elements.enabled.checked = Boolean(state.enabled);
  elements.conversationUrl.value = state.conversationUrl || "";
  elements.runtimeUrl.value = state.runtimeUrl || "";
  elements.fallbackInterval.value = state.fallbackIntervalMinutes;
  elements.fallbackRetry.value = state.fallbackBusyRetryMinutes;
  elements.fallbackPrompt.value = state.fallbackPrompt || "";
  elements.runtimeSource.textContent = runtime.source;
  elements.runtimeInterval.textContent = `${runtime.intervalMinutes} min`;
  elements.lastStatus.textContent = state.lastStatus || "-";
  elements.nextRun.textContent = formatTime(state.nextRunAt);
}

async function save() {
  const response = await request({
    type: "bridge:save-settings",
    settings: {
      enabled: elements.enabled.checked,
      conversationUrl: elements.conversationUrl.value,
      runtimeUrl: elements.runtimeUrl.value,
      fallbackIntervalMinutes: Number(elements.fallbackInterval.value),
      fallbackBusyRetryMinutes: Number(elements.fallbackRetry.value),
      fallbackPrompt: elements.fallbackPrompt.value
    }
  });
  if (!response?.ok) throw new Error(response?.error || "save failed");
  showMessage("Saved.");
  await refresh();
}

async function injectContentScript(tabId) {
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"]
    });
  } catch (error) {
    throw new Error(`Cannot activate bridge in this tab: ${error.message}`);
  }
}

async function useCurrentConversation() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !tab?.url || !/^https:\/\/(chatgpt\.com|chat\.openai\.com)\//.test(tab.url)) {
    throw new Error("Open the target ChatGPT conversation first.");
  }
  const url = new URL(tab.url);
  url.search = "";
  url.hash = "";
  elements.conversationUrl.value = `${url.origin}${url.pathname.replace(/\/$/, "")}`;
  await injectContentScript(tab.id);
  await save();
  showMessage("Current conversation selected, activated, and saved.");
}

elements.save.addEventListener("click", () => {
  save().catch((error) => showMessage(`Error: ${error.message}`));
});

elements.useCurrent.addEventListener("click", () => {
  useCurrentConversation().catch((error) => showMessage(`Error: ${error.message}`));
});

elements.runNow.addEventListener("click", async () => {
  try {
    showMessage("Running...");
    const response = await request({ type: "bridge:run-now" });
    if (!response?.ok) {
      throw new Error(response?.reason || response?.error || "run failed");
    }
    showMessage("Feedback sent.");
    await refresh();
  } catch (error) {
    showMessage(`Error: ${error.message}`);
  }
});

refresh().catch((error) => showMessage(`Error: ${error.message}`));
