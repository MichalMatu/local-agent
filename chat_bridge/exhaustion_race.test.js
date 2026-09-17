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

(async () => {
  const h = createHarness();
  const id = await addConversation(h);
  const alarmName = `local-agent-chat:${id}`;
  assert.equal(h.alarms.has(alarmName), true);

  const snapshotReady = deferred();
  const releaseSnapshot = deferred();
  h.context.signalExhaustionSnapshot = snapshotReady.resolve;
  h.context.releaseExhaustionSnapshot = releaseSnapshot.promise;
  h.evaluate(`
    const originalGetBridgeStateForExhaustionRace = getBridgeState;
    let holdNextBridgeStateReadForExhaustionRace = true;
    getBridgeState = async function () {
      const state = await originalGetBridgeStateForExhaustionRace();
      if (holdNextBridgeStateReadForExhaustionRace) {
        holdNextBridgeStateReadForExhaustionRace = false;
        signalExhaustionSnapshot();
        await releaseExhaustionSnapshot;
      }
      return state;
    };
  `);

  const exhaustion = h.sendRuntimeMessage({
    type: "bridge:conversation-exhausted",
    conversationUrl: "https://chatgpt.com/c/a",
    assistantIdentity: "limit-message",
    signature: "deadbeef"
  }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });

  await snapshotReady.promise;
  const next = await h.sendRuntimeMessage({
    type: "bridge:assistant-control",
    conversationUrl: "https://chatgpt.com/c/a",
    fingerprint: "abc12345",
    control: { marker: "[LAB:NEXT=30s]" }
  }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });
  assert.equal(next.ok, true);
  assert.equal(next.reason, "next_scheduled");
  assert.equal(h.alarms.has(alarmName), true);

  releaseSnapshot.resolve();
  const exhausted = await exhaustion;
  assert.equal(exhausted.ok, false);
  assert.equal(exhausted.reason, "conversation_state_changed");
  assert.equal(h.storage.bridgeState.conversations[id].enabled, true);
  assert.equal(h.storage.bridgeState.conversations[id].generation, 1);
  assert.equal(h.alarms.has(alarmName), true);
  assert.ok(h.alarms.get(alarmName).when < Date.now() + 31_000);

  console.log("Chat Bridge stale exhaustion race test passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
