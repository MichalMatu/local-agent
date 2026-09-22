"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const h = createHarness();
  const url = "https://chatgpt.com/c/a";
  const sender = { tab: { id: 11, url } };

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

  const latestPrompt = async () => {
    const delivery = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
    assert.equal(delivery.ok, true);
    return h.sentMessages[h.sentMessages.length - 1].message.prompt;
  };
  const payload = (userText) => ({
    conversationUrl: url,
    kind: "message_delivery_timeout",
    assistantIdentity: "timeout-answer",
    userIdentity: "user:1:stable-transcript-identity",
    userText,
    signature: "timeout-lifecycle-signature"
  });
  const authorize = (userText) => {
    const conversation = h.storage.bridgeState.conversations[chatId];
    return h.sendRuntimeMessage({
      type: "bridge:authorize-assistant-retry",
      ...payload(userText),
      bindingRevision: conversation.bindingRevision,
      generation: conversation.generation
    }, sender);
  };

  const firstPrompt = await latestPrompt();
  response = await authorize(firstPrompt);
  assert.equal(response.ok, true);
  assert.equal(response.attempt, 1);
  assert.equal(h.storage.bridgeAssistantErrorRecovery.entries[chatId].attempts, 1);

  response = await h.sendRuntimeMessage({
    type: "bridge:rebind-conversation",
    conversationId: chatId,
    binding: { agentBinding: h.TRACKER_BINDING }
  });
  assert.equal(response.ok, true);
  assert.equal(response.conversation.bindingRevision, 2);
  assert.equal(h.storage.bridgeAssistantErrorRecovery.entries[chatId], undefined,
    "rebind must clear timeout retry history from the previous binding lifecycle");

  const reboundPrompt = await latestPrompt();
  response = await authorize(reboundPrompt);
  assert.equal(response.ok, true);
  assert.equal(response.attempt, 1, "new binding revision must start a fresh retry budget");
  assert.equal(h.storage.bridgeAssistantErrorRecovery.entries[chatId].attempts, 1);

  response = await h.sendRuntimeMessage({ type: "bridge:remove-conversation", conversationId: chatId });
  assert.equal(response.ok, true);
  assert.equal(h.storage.bridgeAssistantErrorRecovery.entries[chatId], undefined,
    "remove must clear timeout retry history for the retired chat lifecycle");

  response = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url,
      label: "Project A re-added",
      enabled: true,
      preferredTabId: 11,
      agentBinding: h.MATRIX_BINDING
    }
  });
  assert.equal(response.ok, true);
  assert.equal(response.conversation.bindingRevision, 1);
  const readdedPrompt = await latestPrompt();

  response = await h.sendRuntimeMessage({ type: "bridge:assistant-error", ...payload(readdedPrompt) }, sender);
  assert.equal(response.ok, true);
  assert.equal(response.bridgeOwned, true);
  assert.equal(response.attempts, 0, "re-added chat must not inherit a retired lifecycle retry budget");
  assert.equal(response.retryAfterMs, 1500);

  console.log("Chat Bridge timeout recovery budget resets on rebind, remove and re-add lifecycles.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
