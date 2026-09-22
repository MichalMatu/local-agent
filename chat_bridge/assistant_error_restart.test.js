"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const first = createHarness();
  let response = await first.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      label: "Project A",
      enabled: true,
      preferredTabId: 11,
      agentBinding: first.MATRIX_BINDING
    }
  });
  assert.equal(response.ok, true);
  const chatId = response.conversation.id;

  response = await first.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  const bridgePrompt = first.sentMessages[0].message.prompt;
  const sender = { tab: { id: 11, url: "https://chatgpt.com/c/a" } };
  const payload = {
    conversationUrl: "https://chatgpt.com/c/a",
    kind: "message_delivery_timeout",
    assistantIdentity: "timeout-answer",
    userIdentity: "bridge-user-restart",
    userText: bridgePrompt,
    signature: "timeout-restart-signature"
  };

  response = await first.sendRuntimeMessage({
    type: "bridge:authorize-assistant-retry",
    ...payload
  }, sender);
  assert.equal(response.ok, true);
  assert.equal(response.attempt, 1);
  assert.equal(first.storage.bridgeAssistantErrorRecovery.entries[chatId].attempts, 1);

  const restarted = createHarness({ storage: first.storage });
  response = await restarted.sendRuntimeMessage({ type: "bridge:assistant-error", ...payload }, sender);
  assert.equal(response.ok, true);
  assert.equal(response.attempts, 1);
  assert.equal(response.retryAfterMs, 5000);

  response = await restarted.sendRuntimeMessage({
    type: "bridge:authorize-assistant-retry",
    ...payload
  }, sender);
  assert.equal(response.ok, true);
  assert.equal(response.attempt, 2);
  assert.equal(restarted.storage.bridgeAssistantErrorRecovery.entries[chatId].attempts, 2);

  const restartedAgain = createHarness({ storage: restarted.storage });
  response = await restartedAgain.sendRuntimeMessage({ type: "bridge:assistant-error", ...payload }, sender);
  assert.equal(response.ok, true);
  assert.equal(response.attempts, 2);
  assert.equal(response.retryAfterMs, 15000);

  console.log("Chat Bridge assistant error restart persistence tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
