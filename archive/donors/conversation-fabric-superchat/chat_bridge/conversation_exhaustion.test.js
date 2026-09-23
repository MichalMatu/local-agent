"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const { storage, alarms, sendRuntimeMessage, MATRIX_BINDING } = createHarness();
  let response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      label: "Project A",
      enabled: true,
      preferredTabId: 11,
      agentBinding: MATRIX_BINDING
    }
  });
  assert.equal(response.ok, true);
  const chatId = response.conversation.id;
  assert.equal(alarms.has(`local-agent-chat:${chatId}`), true);
  const generation = storage.bridgeState.conversations[chatId].generation;

  response = await sendRuntimeMessage({
    type: "bridge:conversation-exhausted",
    conversationUrl: "https://chatgpt.com/c/a",
    assistantIdentity: "23ce695f-ebce-4b62-ae56-7eed597d913f",
    signature: "deadbeef"
  }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });

  assert.equal(response.ok, true);
  assert.equal(response.reason, "conversation_exhausted");
  const exhausted = storage.bridgeState.conversations[chatId];
  assert.equal(exhausted.enabled, false);
  assert.equal(exhausted.lastStatus, "conversation_exhausted");
  assert.equal(exhausted.nextRunAt, null);
  assert.equal(exhausted.generation, generation + 1);
  assert.equal(alarms.has(`local-agent-chat:${chatId}`), false);

  response = await sendRuntimeMessage({
    type: "bridge:conversation-exhausted",
    conversationUrl: "https://chatgpt.com/c/a"
  }, { tab: { id: 22, url: "https://chatgpt.com/c/b" } });
  assert.equal(response.ok, false);
  assert.equal(response.reason, "conversation_not_found");

  console.log("Chat Bridge conversation exhaustion tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
