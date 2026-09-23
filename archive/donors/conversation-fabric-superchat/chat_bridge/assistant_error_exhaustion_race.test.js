"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const h = createHarness();
  const url = "https://chatgpt.com/c/a";

  let response = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url,
      label: "Project A",
      enabled: true,
      preferredTabId: 11,
      agentBinding: h.MATRIX_BINDING
    }
  });
  assert.equal(response.ok, true);
  const chatId = response.conversation.id;

  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  const staleConversation = JSON.parse(JSON.stringify(h.storage.bridgeState.conversations[chatId]));

  response = await h.sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: chatId,
    patch: { enabled: false }
  });
  assert.equal(response.ok, true);
  response = await h.sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: chatId,
    patch: { enabled: true }
  });
  assert.equal(response.ok, true);
  const current = h.storage.bridgeState.conversations[chatId];
  assert.ok(current.generation > staleConversation.generation);
  assert.equal(current.enabled, true);

  const markExhausted = h.evaluate("markAssistantRetryExhausted");
  const marked = await markExhausted(staleConversation);
  assert.equal(marked, false,
    "stale generation must not terminally disable a newer conversation lifecycle");
  assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);
  assert.notEqual(h.storage.bridgeState.conversations[chatId].lastStatus, "assistant_retry_exhausted");

  console.log("Chat Bridge retry exhaustion cannot cross a conversation generation change.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
