"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const { createHarness } = require("./worker_test_harness.js");

function fingerprint(value) {
  return protocol.fnv1a32(value);
}

async function addChat(harness) {
  const response = await harness.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      repositoryId: "matrixhub",
      enabled: true,
      preferredTabId: 11,
      assistantBaseline: ""
    }
  });
  assert.equal(response.ok, true);
  return response.conversation;
}

async function assistantControl(harness, conversation, marker, seed) {
  return harness.sendRuntimeMessage({
    type: "bridge:assistant-control",
    conversationUrl: conversation.url,
    assistantIdentity: `assistant-${seed}`,
    bindingRevision: conversation.bindingRevision,
    control: protocol.parseAssistantControl(marker),
    fingerprint: fingerprint(`${seed}:${marker}`)
  }, {
    id: harness.chrome.runtime.id,
    frameId: 0,
    url: conversation.url,
    tab: { id: 11, url: conversation.url }
  });
}

(async () => {
  const harness = createHarness();
  const conversation = await addChat(harness);

  let response = await assistantControl(
    harness,
    conversation,
    "[LAB:WAIT_TASK=lifecycle-1]",
    "wait"
  );
  assert.equal(response.ok, true);
  assert.equal(harness.evaluate("nativeTransport.wanted"), true);

  const latestAfterWait = harness.storage.bridgeState.conversations[conversation.id];
  response = await assistantControl(harness, latestAfterWait, "[LAB:PAUSE]", "pause");
  assert.equal(response.ok, true);
  assert.equal(harness.evaluate("nativeTransport.wanted"), false,
    "paused chat must not keep Native Messaging alive");
  assert.equal(harness.storage.eventWakeState.watches[conversation.id].taskId, "lifecycle-1",
    "pause must retain the durable task watch");

  const paused = harness.storage.bridgeState.conversations[conversation.id];
  response = await assistantControl(harness, paused, "[LAB:RESUME]", "resume");
  assert.equal(response.ok, true);
  assert.equal(harness.evaluate("nativeTransport.wanted"), true,
    "resume must reconnect transport for the retained watch");

  const masterOff = await harness.sendRuntimeMessage({
    type: "bridge:save-global-settings",
    settings: { masterEnabled: false }
  });
  assert.equal(masterOff.ok, true);
  assert.equal(harness.evaluate("nativeTransport.wanted"), false,
    "Master-off must suspend Native Messaging transport");
  assert.equal(harness.storage.eventWakeState.watches[conversation.id].taskId, "lifecycle-1");

  const masterOn = await harness.sendRuntimeMessage({
    type: "bridge:save-global-settings",
    settings: { masterEnabled: true }
  });
  assert.equal(masterOn.ok, true);
  assert.equal(harness.evaluate("nativeTransport.wanted"), true,
    "Master-on must reconnect transport for an active retained watch");

  const disabled = await harness.sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: conversation.id,
    patch: { enabled: false }
  });
  assert.equal(disabled.ok, true);
  assert.equal(harness.evaluate("nativeTransport.wanted"), false,
    "operator-disabled chat must not keep Native Messaging alive");

  const enabled = await harness.sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: conversation.id,
    patch: { enabled: true }
  });
  assert.equal(enabled.ok, true);
  assert.equal(harness.evaluate("nativeTransport.wanted"), true,
    "operator re-enable must reconnect transport for retained watch");

  console.log("Chat Bridge event wake transport lifecycle tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
