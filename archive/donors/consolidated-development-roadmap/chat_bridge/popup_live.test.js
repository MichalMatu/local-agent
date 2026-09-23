"use strict";

const assert = require("node:assert/strict");
const { LIVE_SYNC_MS, createController } = require("./popup_live.js");

function makeCard() {
  const nodes = {
    title: { textContent: "", title: "" },
    repo: { textContent: "" },
    enabled: { checked: false },
    status: { textContent: "", title: "" },
    next: { dataset: {}, textContent: "" },
    interval: { value: "", placeholder: "", title: "" }
  };
  const classes = new Set();
  return {
    dataset: {},
    nodes,
    classes,
    classList: {
      toggle(name, enabled) {
        if (enabled) classes.add(name);
        else classes.delete(name);
      }
    },
    querySelector(selector) {
      return {
        ".card-title": nodes.title,
        ".repo-badge": nodes.repo,
        ".enable-switch input": nodes.enabled,
        ".status-text": nodes.status,
        ".next-wake": nodes.next,
        ".wake-input-wrap input": nodes.interval
      }[selector] || null;
    }
  };
}

(async () => {
  const card = makeCard();
  const cards = [];
  const document = { activeElement: null };
  const elements = {
    conversationList: { querySelectorAll: () => cards },
    conversationCount: { textContent: "" },
    masterEnabled: { checked: true },
    runtimeSource: { textContent: "" },
    runtimeInterval: { textContent: "" }
  };
  let latestState = null;
  let latestRuntime = null;
  let renderCount = 0;
  let refreshCurrentCount = 0;
  let restartCountdownCount = 0;
  let nextWakeUpdates = 0;
  let intervalCallback = null;
  let intervalDelay = null;
  let storageListener = null;
  let pageHideListener = null;
  let response = {
    state: {
      settings: { masterEnabled: true, fallbackIntervalMinutes: 10 },
      conversations: {
        chat1: {
          id: "chat1",
          label: "Live chat",
          repositoryId: "local-agent",
          enabled: false,
          lastStatus: "paused_by_assistant",
          intervalOverrideMinutes: 9
        }
      }
    },
    runtime: { source: "remote", intervalMinutes: 10 },
    schedules: { chat1: { nextRunAt: null } }
  };

  const controller = createController({
    elements,
    request: async () => response,
    renderConversations: () => {
      renderCount += 1;
      if (!cards.length) cards.push(card);
    },
    refreshCurrentTabForm: async () => { refreshCurrentCount += 1; },
    restartCountdownTimer: () => { restartCountdownCount += 1; },
    updateNextWakeElement: () => { nextWakeUpdates += 1; },
    setLatestState: (value) => { latestState = value; },
    setLatestRuntime: (value) => { latestRuntime = value; },
    document,
    storageOnChanged: { addListener: (listener) => { storageListener = listener; } },
    addPageHideListener: (listener) => { pageHideListener = listener; },
    setIntervalFn: (callback, delay) => {
      intervalCallback = callback;
      intervalDelay = delay;
      return 123;
    },
    clearIntervalFn: () => {},
    logger: { warn: () => {} }
  });

  await controller.syncNow();
  assert.equal(renderCount, 1);
  assert.equal(refreshCurrentCount, 1);
  assert.equal(restartCountdownCount, 1);
  assert.equal(card.dataset.conversationId, "chat1");
  assert.equal(card.nodes.enabled.checked, false);
  assert.equal(card.classes.has("is-paused"), true);
  assert.equal(card.nodes.status.textContent, "paused_by_assistant");
  assert.equal(card.nodes.interval.value, "9");
  assert.equal(card.nodes.next.dataset.conversationEnabled, "false");
  assert.equal(elements.masterEnabled.checked, true);
  assert.equal(elements.runtimeSource.textContent, "remote");
  assert.equal(elements.runtimeInterval.textContent, "10 min");
  assert.equal(latestState, response.state);
  assert.equal(latestRuntime, response.runtime);

  response = {
    ...response,
    state: {
      ...response.state,
      settings: { ...response.state.settings, masterEnabled: false },
      conversations: {
        chat1: {
          ...response.state.conversations.chat1,
          enabled: true,
          lastStatus: "resumed_by_assistant",
          intervalOverrideMinutes: 7
        }
      }
    },
    schedules: { chat1: { nextRunAt: "2030-01-01T00:00:00.000Z" } }
  };
  document.activeElement = card.nodes.interval;
  await controller.syncNow();
  assert.equal(renderCount, 1, "existing cards should patch in place");
  assert.equal(card.nodes.enabled.checked, true);
  assert.equal(card.classes.has("is-paused"), false);
  assert.equal(card.nodes.status.textContent, "resumed_by_assistant");
  assert.equal(card.nodes.interval.value, "9", "focused interval draft must not be overwritten");
  assert.equal(card.nodes.next.dataset.masterEnabled, "false");
  assert.equal(card.nodes.next.dataset.conversationEnabled, "true");
  assert.equal(elements.masterEnabled.checked, false);

  document.activeElement = null;
  await controller.syncNow();
  assert.equal(card.nodes.interval.value, "7");
  assert.ok(nextWakeUpdates >= 3);

  controller.start();
  assert.equal(intervalDelay, LIVE_SYNC_MS);
  assert.equal(LIVE_SYNC_MS, 500);
  assert.equal(typeof intervalCallback, "function");
  assert.equal(typeof storageListener, "function");
  assert.equal(typeof pageHideListener, "function");
  storageListener({ bridgeState: { newValue: {} } }, "sync");
  await Promise.resolve();
  assert.equal(latestState, response.state, "non-local storage events must be ignored");

  console.log("Popup live-state tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
