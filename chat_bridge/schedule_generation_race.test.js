"use strict";

const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

async function addConversation(harness) {
  const result = await harness.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      agentBinding: harness.MATRIX_BINDING,
      enabled: true,
      preferredTabId: 11
    }
  });
  assert.equal(result.ok, true, result.error);
  return result.conversation.id;
}

function holdNextAlarmClear(harness, signal, release, suffix) {
  harness.context[`signalAlarmClear${suffix}`] = signal.resolve;
  harness.context[`releaseAlarmClear${suffix}`] = release.promise;
  harness.evaluate(`
    const originalClearConversationAlarm${suffix} = clearConversationAlarm;
    let holdNextConversationAlarmClear${suffix} = true;
    clearConversationAlarm = async function (...args) {
      if (holdNextConversationAlarmClear${suffix}) {
        holdNextConversationAlarmClear${suffix} = false;
        signalAlarmClear${suffix}();
        await releaseAlarmClear${suffix};
      }
      return originalClearConversationAlarm${suffix}(...args);
    };
  `);
}

function holdNextDefaultSchedule(harness, signal, release, suffix) {
  harness.context[`signalDefaultSchedule${suffix}`] = signal.resolve;
  harness.context[`releaseDefaultSchedule${suffix}`] = release.promise;
  harness.evaluate(`
    const originalScheduleDefault${suffix} = scheduleDefault;
    let holdNextScheduleDefault${suffix} = true;
    scheduleDefault = async function (...args) {
      if (holdNextScheduleDefault${suffix}) {
        holdNextScheduleDefault${suffix} = false;
        signalDefaultSchedule${suffix}();
        await releaseDefaultSchedule${suffix};
      }
      return originalScheduleDefault${suffix}(...args);
    };
  `);
}

(async () => {
  // A stale popup disable cleanup cannot clear a newer assistant NEXT schedule.
  {
    const h = createHarness();
    const id = await addConversation(h);
    const alarmName = `local-agent-chat:${id}`;
    const clearReady = deferred();
    const releaseClear = deferred();
    holdNextAlarmClear(h, clearReady, releaseClear, "Disable");

    const disable = h.sendRuntimeMessage({
      type: "bridge:update-conversation",
      conversationId: id,
      patch: { enabled: false }
    });
    await clearReady.promise;
    assert.equal(h.storage.bridgeState.conversations[id].enabled, false);

    const next = await h.sendRuntimeMessage({
      type: "bridge:assistant-control",
      conversationUrl: "https://chatgpt.com/c/a",
      fingerprint: "abc12345",
      control: { marker: "[LAB:NEXT=30s]" }
    }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });
    assert.equal(next.ok, true);
    assert.equal(next.reason, "next_scheduled");
    const nextGeneration = h.storage.bridgeState.conversations[id].generation;
    assert.equal(h.alarms.has(alarmName), true);

    releaseClear.resolve();
    const disabled = await disable;
    assert.equal(disabled.ok, true, disabled.error);
    assert.equal(h.storage.bridgeState.conversations[id].enabled, true);
    assert.equal(h.storage.bridgeState.conversations[id].generation, nextGeneration);
    assert.equal(h.alarms.has(alarmName), true);
  }

  // Reconciliation from an older master-off snapshot cannot clear a newer master-on schedule.
  {
    const h = createHarness();
    const id = await addConversation(h);
    const alarmName = `local-agent-chat:${id}`;
    const clearReady = deferred();
    const releaseClear = deferred();
    holdNextAlarmClear(h, clearReady, releaseClear, "Master");

    const masterOff = h.sendRuntimeMessage({
      type: "bridge:save-global-settings",
      settings: { masterEnabled: false }
    });
    await clearReady.promise;
    assert.equal(h.storage.bridgeState.settings.masterEnabled, false);

    const masterOn = await h.sendRuntimeMessage({
      type: "bridge:save-global-settings",
      settings: { masterEnabled: true }
    });
    assert.equal(masterOn.ok, true, masterOn.error);
    const currentGeneration = h.storage.bridgeState.conversations[id].generation;
    assert.equal(h.alarms.has(alarmName), true);

    releaseClear.resolve();
    const offResult = await masterOff;
    assert.equal(offResult.ok, true, offResult.error);
    assert.equal(h.storage.bridgeState.settings.masterEnabled, true);
    assert.equal(h.storage.bridgeState.conversations[id].generation, currentGeneration);
    assert.equal(h.alarms.has(alarmName), true);
  }

  // A rebind's delayed bootstrap schedule cannot overwrite a newer NEXT on the new binding.
  {
    const h = createHarness();
    const id = await addConversation(h);
    const alarmName = `local-agent-chat:${id}`;
    const scheduleReady = deferred();
    const releaseSchedule = deferred();
    holdNextDefaultSchedule(h, scheduleReady, releaseSchedule, "Rebind");

    const rebind = h.sendRuntimeMessage({
      type: "bridge:rebind-conversation",
      conversationId: id,
      binding: { agentBinding: h.TRACKER_BINDING }
    });
    await scheduleReady.promise;
    assert.equal(h.storage.bridgeState.conversations[id].agentBinding, h.TRACKER_BINDING);

    const next = await h.sendRuntimeMessage({
      type: "bridge:assistant-control",
      conversationUrl: "https://chatgpt.com/c/a",
      fingerprint: "fedcba98",
      control: { marker: "[LAB:NEXT=30s]" }
    }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });
    assert.equal(next.ok, true);
    assert.equal(next.reason, "next_scheduled");
    const nextGeneration = h.storage.bridgeState.conversations[id].generation;
    const nextWhen = h.alarms.get(alarmName).when;

    releaseSchedule.resolve();
    const rebound = await rebind;
    assert.equal(rebound.ok, true, rebound.error);
    assert.equal(h.storage.bridgeState.conversations[id].generation, nextGeneration);
    assert.equal(h.alarms.get(alarmName).when, nextWhen);
  }

  // Stale asynchronous status from an older generation cannot overwrite newer control state.
  {
    const h = createHarness();
    const id = await addConversation(h);
    const staleGeneration = h.storage.bridgeState.conversations[id].generation;
    const next = await h.sendRuntimeMessage({
      type: "bridge:assistant-control",
      conversationUrl: "https://chatgpt.com/c/a",
      fingerprint: "def67890",
      control: { marker: "[LAB:NEXT=30s]" }
    }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });
    assert.equal(next.ok, true);
    assert.equal(next.reason, "next_scheduled");

    h.context.scheduleRaceChatId = id;
    h.context.scheduleRaceStaleGeneration = staleGeneration;
    await h.evaluate(`updateConversationStatus(
      scheduleRaceChatId,
      { lastStatus: "stale_worker_error" },
      scheduleRaceStaleGeneration
    )`);
    assert.equal(h.storage.bridgeState.conversations[id].lastStatus, "next_30s_by_assistant");
  }

  console.log("Chat Bridge generation-ordered scheduling race tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
