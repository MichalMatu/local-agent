"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
function clone(value) { return value === undefined ? undefined : JSON.parse(JSON.stringify(value)); }
function createHarness(options = {}) {
const MATRIX_BINDING = "033327ab-700d-43b4-9b3b-caff1acaa2c7";
const TRACKER_BINDING = "be481b25-9d97-4205-b93f-95f5c5827441";
const LOCAL_AGENT_BINDING = "2180d453-1357-4fbc-be1a-e1e5b8fbb10a";
const runtimeAgents = [
  {
    repository_id: "local-agent",
    repository: "MichalMatu/local-agent",
    agent_binding: LOCAL_AGENT_BINDING,
    execution_enabled: false
  },
  {
    repository_id: "matrixhub",
    repository: "MichalMatu/MatrixHub",
    agent_binding: MATRIX_BINDING,
    execution_enabled: true
  },
  {
    repository_id: "tracker",
    repository: "MichalMatu/tracker",
    agent_binding: TRACKER_BINDING,
    execution_enabled: true
  }
];

const storage = options.storage || {};
const alarms = new Map();
const sentMessages = [];
const runtimeMessageListeners = [];
const alarmListeners = [];
const installedListeners = [];
const startupListeners = [];
const tabs = [
  { id: 11, url: "https://chatgpt.com/c/a", title: "Project A" },
  { id: 22, url: "https://chatgpt.com/c/b", title: "Project B" },
  { id: 33, url: "https://chatgpt.com/c/infra", title: "Local Agent" }
];

const chrome = {
  storage: {
    local: {
      async get(key) {
        if (key === null) return clone(storage);
        if (typeof key === "string") return { [key]: clone(storage[key]) };
        throw new Error("unsupported storage.get shape in test");
      },
      async set(patch) {
        Object.assign(storage, clone(patch));
      }
    }
  },
  alarms: {
    async create(name, info) {
      if (options.createAlarm) await options.createAlarm(name, info);
      const alarm = { name, ...clone(info) };
      if (Number.isFinite(Number(info.when))) alarm.scheduledTime = Number(info.when);
      alarms.set(name, alarm);
    },
    async clear(name) {
      return alarms.delete(name);
    },
    async getAll() {
      return Array.from(alarms.values()).map(clone);
    },
    onAlarm: {
      addListener(listener) {
        alarmListeners.push(listener);
      }
    }
  },
  tabs: {
    async query() {
      return clone(tabs);
    },
    async sendMessage(tabId, message) {
      sentMessages.push({ tabId, message: clone(message) });
      const authorize = () => sendRuntimeMessage({
        type: "bridge:authorize-delivery", conversationUrl: message.expectedUrl,
        deliveryId: message.deliveryId, assistantBaseline: "old-assistant"
      }, { tab: { id: tabId, url: message.expectedUrl } });
      if (options.sendMessage) return options.sendMessage({ tabId, message, authorize });
      const permission = await authorize();
      return permission.ok ? { ok: true, reason: "sent", protocolVersion: 1 }
        : { ok: false, reason: "delivery_cancelled", protocolVersion: 1 };
    }
  },
  runtime: {
    id: "test-bridge",
    getURL: (path) => `chrome-extension://test-bridge/${path}`,
    onInstalled: {
      addListener(listener) {
        installedListeners.push(listener);
      }
    },
    onStartup: {
      addListener(listener) {
        startupListeners.push(listener);
      }
    },
    onMessage: {
      addListener(listener) {
        runtimeMessageListeners.push(listener);
      }
    }
  }
};

const context = vm.createContext({
  console: options.console || console,
  crypto: require("node:crypto").webcrypto,
  chrome,
  URL,
  Date,
  Math,
  Number,
  String,
  Boolean,
  Object,
  Array,
  Set,
  Promise,
  AbortController,
  setTimeout,
  clearTimeout,
  fetch: options.fetch || (async () => ({
    ok: true,
    async json() {
      return {
        schema_version: 3,
        interval_minutes: 10,
        busy_retry_minutes: 1,
        bootstrap_prompt: "BOOTSTRAP",
        wake_prompt: "WAKE",
        agents: runtimeAgents
      };
    }
  }))
});
context.globalThis = context;
context.importScripts = (...filenames) => {
  for (const filename of filenames) {
    const source = fs.readFileSync(path.join(__dirname, filename), "utf8");
    vm.runInContext(source, context, { filename });
  }
};

const workerSource = fs.readFileSync(path.join(__dirname, "service_worker.js"), "utf8");
vm.runInContext(workerSource, context, { filename: "service_worker.js" });

async function sendRuntimeMessage(message, sender = { id: chrome.runtime.id, url: chrome.runtime.getURL("popup.html") }) {
  if (sender.tab) {
    sender = { id: chrome.runtime.id, frameId: 0, url: sender.tab.url, ...sender,
      tab: { id: tabs.find((tab) => tab.url === sender.tab.url)?.id, ...sender.tab } };
  }
  if (message.type === "bridge:assistant-control" && message.bindingRevision === undefined) {
    const stored = Object.values(storage.bridgeState?.conversations || {}).find((c) => c.url === message.conversationUrl);
    message = { bindingRevision: stored?.bindingRevision, assistantIdentity: "new-assistant", ...message };
  }
  const listener = runtimeMessageListeners[0];
  return new Promise((resolve, reject) => {
    let settled = false;
    const timeout = setTimeout(() => {
      if (!settled) reject(new Error(`message timed out: ${message.type}`));
    }, 1000);
    const sendResponse = (response) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      resolve(response);
    };
    try {
      const keepAlive = listener(message, sender, sendResponse);
      if (keepAlive !== true && !settled) {
        settled = true;
        clearTimeout(timeout);
        resolve(undefined);
      }
    } catch (error) {
      clearTimeout(timeout);
      reject(error);
    }
  });
}

return { storage, alarms, sentMessages, tabs, chrome, context, sendRuntimeMessage,
  MATRIX_BINDING, TRACKER_BINDING, LOCAL_AGENT_BINDING, runtimeAgents,
  evaluate: (source) => vm.runInContext(source, context),
  installed: () => installedListeners[0](), startup: () => startupListeners[0]() };
}
module.exports = { createHarness };