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

function holdNextStateRead(harness, signal, release, suffix) {
  harness.context[`signalExhaustionSnapshot${suffix}`] = signal.resolve;
  harness.context[`releaseExhaustionSnapshot${suffix}`] = release.promise;
  harness.evaluate(`
    const originalGetBridgeStateForExhaustionRace${suffix} = getBridgeState;
    let holdNextBridgeStateReadForExhaustionRace${suffix} = true;
    getBridgeState = async function () {
      const state = await originalGetBridgeStateForExhaustionRace${suffix}();
      if (holdNextBridgeStateReadForExhaustionRace${suffix}) {
        holdNextBridgeStateReadForExhaustionRace${suffix} = false;
        signalExhaustionSnapshot${suffix}();
        await releaseExhaustionSnapshot${suffix};
      }
      return state;
    };
  `);
}

function reportExhaustion(harness) {
  return harness.sendRuntimeMessage({
    type: "bridge:conversation-exhausted",
    conversationUrl: "https://chatgpt.com/c/a",
    assistantIdentity: "limit-message",
    signature: "deadbeef"
  }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });
}

(async () => {
  // Confirmed exhaustion is terminal for the same binding even if a newer NEXT races first.
  {
    const h = createHarness();
    const id = await addConversation(h);
    const alarmName = `local-agent-chat:${id}`;
    const initialGeneration = h.storage.bridgeState.conversations[id].generation;
    const snapshotReady = deferred();
    const releaseSnapshot = deferred();
    holdNextStateRead(h, snapshotReady, releaseSnapshot, "Next");

    const exhaustion = reportExhaustion(h);
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
    assert.equal(exhausted.ok, true);
    assert.equal(exhausted.reason, "conversation_exhausted");
    const conversation = h.storage.bridgeState.conversations[id];
    assert.equal(conversation.enabled, false);
    assert.equal(conversation.lastStatus, "conversation_exhausted");
    assert.equal(conversation.generation, initialGeneration + 2);
    assert.equal(h.alarms.has(alarmName), false);
  }

  // A report from the previous hard binding cannot disable or clear a rebound conversation.
  {
    const h = createHarness();
    const id = await addConversation(h);
    const alarmName = `local-agent-chat:${id}`;
    const snapshotReady = deferred();
    const releaseSnapshot = deferred();
    holdNextStateRead(h, snapshotReady, releaseSnapshot, "Rebind");

    const exhaustion = reportExhaustion(h);
    await snapshotReady.promise;
    const rebound = await h.sendRuntimeMessage({
      type: "bridge:rebind-conversation",
      conversationId: id,
      binding: { agentBinding: h.TRACKER_BINDING }
    });
    assert.equal(rebound.ok, true, rebound.error);
    assert.equal(rebound.conversation.agentBinding, h.TRACKER_BINDING);
    assert.equal(h.alarms.has(alarmName), true);

    releaseSnapshot.resolve();
    const stale = await exhaustion;
    assert.equal(stale.ok, false);
    assert.equal(stale.reason, "conversation_state_changed");
    const conversation = h.storage.bridgeState.conversations[id];
    assert.equal(conversation.enabled, true);
    assert.equal(conversation.agentBinding, h.TRACKER_BINDING);
    assert.equal(conversation.lastStatus, "rebound_by_operator");
    assert.equal(h.alarms.has(alarmName), true);
  }

  console.log("Chat Bridge exhaustion ordering race tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
