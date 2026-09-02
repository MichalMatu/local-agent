"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

const storage = {};
const alarms = new Map();
const sentMessages = [];
const runtimeMessageListeners = [];
const alarmListeners = [];
const installedListeners = [];
const startupListeners = [];
const tabs = [
  { id: 11, url: "https://chatgpt.com/c/a", title: "Project A" },
  { id: 22, url: "https://chatgpt.com/c/b", title: "Project B" }
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
    create(name, info) {
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
      return { ok: true, reason: "sent" };
    }
  },
  runtime: {
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
  console,
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
  fetch: async () => ({
    ok: true,
    async json() {
      return {
        schema_version: 2,
        interval_minutes: 10,
        busy_retry_minutes: 1,
        bootstrap_prompt: "BOOTSTRAP",
        wake_prompt: "WAKE"
      };
    }
  })
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

assert.equal(runtimeMessageListeners.length, 1);
assert.equal(alarmListeners.length, 1);

async function sendRuntimeMessage(message, sender = {}) {
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

(async () => {
  let response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      label: "Project A",
      repositoryId: "repo-a",
      enabled: true,
      preferredTabId: 11
    }
  });
  assert.equal(response.ok, true);
  const aId = response.conversation.id;

  response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/b",
      label: "Project B",
      repositoryId: "repo-b",
      enabled: true,
      preferredTabId: 22
    }
  });
  assert.equal(response.ok, true);
  const bId = response.conversation.id;
  assert.notEqual(aId, bId);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), true);
  assert.equal(alarms.has(`local-agent-chat:${bId}`), true);

  const originalBWhen = alarms.get(`local-agent-chat:${bId}`).when;
  response = await sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: bId,
    patch: { label: "Project B renamed" }
  });
  assert.equal(response.ok, true);
  assert.equal(alarms.get(`local-agent-chat:${bId}`).when, originalBWhen);

  const beforePacingUpdate = Date.now();
  response = await sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: bId,
    patch: { intervalOverrideMinutes: 15 }
  });
  assert.equal(response.ok, true);
  const pacedAlarm = alarms.get(`local-agent-chat:${bId}`);
  assert.ok(pacedAlarm.when >= beforePacingUpdate + 14 * 60_000 + 50_000);
  assert.ok(pacedAlarm.when <= beforePacingUpdate + 15 * 60_000 + 2_000);

  // Popup schedule data must follow the actual Chrome alarm, not stale stored state.
  storage.bridgeState.conversations[bId].nextRunAt = new Date(0).toISOString();
  response = await sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(
    new Date(response.schedules[bId].nextRunAt).getTime(),
    pacedAlarm.scheduledTime
  );

  response = await sendRuntimeMessage(
    {
      type: "bridge:assistant-control",
      conversationUrl: "https://chatgpt.com/c/a",
      fingerprint: "abcd1234",
      control: { marker: "[LAB:PAUSE]" }
    },
    { tab: { url: "https://chatgpt.com/c/a" } }
  );
  assert.equal(response.ok, true);
  assert.equal(response.reason, "paused");

  response = await sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(response.state.conversations[aId].enabled, false);
  assert.equal(response.state.conversations[bId].enabled, true);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), false);
  assert.equal(alarms.has(`local-agent-chat:${bId}`), true);

  const beforeRearm = Date.now();
  response = await sendRuntimeMessage(
    {
      type: "bridge:assistant-control",
      conversationUrl: "https://chatgpt.com/c/a",
      fingerprint: "cdef3456",
      control: { marker: "[LAB:NEXT=30s]" }
    },
    { tab: { url: "https://chatgpt.com/c/a" } }
  );
  assert.equal(response.ok, true);
  assert.equal(response.reason, "next_scheduled");
  assert.equal(response.armed, true);
  response = await sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(response.state.conversations[aId].enabled, true);
  const rearmedAlarm = alarms.get(`local-agent-chat:${aId}`);
  assert.ok(rearmedAlarm.when >= beforeRearm + 29_000);
  assert.ok(rearmedAlarm.when <= beforeRearm + 31_500);

  const beforeNext = Date.now();
  response = await sendRuntimeMessage(
    {
      type: "bridge:assistant-control",
      conversationUrl: "https://chatgpt.com/c/b",
      fingerprint: "bcde2345",
      control: { marker: "[LAB:NEXT=10m]" }
    },
    { tab: { url: "https://chatgpt.com/c/b" } }
  );
  assert.equal(response.ok, true);
  assert.equal(response.seconds, 600);
  const nextAlarm = alarms.get(`local-agent-chat:${bId}`);
  assert.ok(nextAlarm.when >= beforeNext + 599_000);
  assert.ok(nextAlarm.when <= beforeNext + 601_500);
  response = await sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(response.state.conversations[bId].intervalOverrideMinutes, 15);

  response = await sendRuntimeMessage({
    type: "bridge:run-now",
    conversationId: bId
  });
  assert.equal(response.ok, true);
  assert.equal(response.bridgeMode, "bootstrap");
  assert.match(sentMessages.at(-1).message.prompt, /BOOTSTRAP/);
  assert.match(sentMessages.at(-1).message.prompt, /\[LAB:NEXT=30s\]/);

  response = await sendRuntimeMessage({
    type: "bridge:run-now",
    conversationId: bId
  });
  assert.equal(response.ok, true);
  assert.equal(response.bridgeMode, "wake");
  assert.equal(sentMessages.at(-1).message.prompt, "WAKE");
  assert.ok(sentMessages.at(-1).message.prompt.length < sentMessages.at(-2).message.prompt.length);

  response = await sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(response.state.conversations[bId].bootstrapPending, false);
  assert.equal(response.state.conversations[aId].bootstrapPending, true);

  console.log("Chat Bridge service worker tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
