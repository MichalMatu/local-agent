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

  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  const oldPrompt = h.sentMessages.at(-1).message.prompt;
  assert.equal(h.storage.bridgeState.conversations[chatId].bootstrapPending, false);

  response = await h.sendRuntimeMessage({
    type: "bridge:rebind-conversation",
    conversationId: chatId,
    binding: { agentBinding: h.MATRIX_BINDING }
  });
  assert.equal(response.ok, true);
  assert.equal(response.conversation.bindingRevision, 2);
  assert.equal(response.conversation.bootstrapPending, true);

  const stalePayload = {
    conversationUrl: url,
    kind: "message_delivery_timeout",
    assistantIdentity: "pre-rebind-timeout",
    userIdentity: "user:1:old-binding-turn",
    userText: oldPrompt,
    signature: "pre-rebind-timeout-signature"
  };
  response = await h.sendRuntimeMessage({ type: "bridge:assistant-error", ...stalePayload }, sender);
  assert.equal(response.ok, true);
  assert.equal(response.bridgeOwned, false,
    "a pre-bootstrap timeout must not be adopted by the new binding lifecycle");
  assert.equal(response.retryEligible, false);
  assert.equal(response.reason, "assistant_delivery_timeout_unowned");

  response = await h.sendRuntimeMessage({
    type: "bridge:authorize-assistant-retry",
    ...stalePayload,
    bindingRevision: h.storage.bridgeState.conversations[chatId].bindingRevision,
    generation: h.storage.bridgeState.conversations[chatId].generation
  }, sender);
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_retry_not_bridge_owned");
  assert.equal(h.storage.bridgeAssistantErrorRecovery?.entries?.[chatId], undefined);

  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  const currentPrompt = h.sentMessages.at(-1).message.prompt;
  assert.equal(h.storage.bridgeState.conversations[chatId].bootstrapPending, false);

  response = await h.sendRuntimeMessage({
    type: "bridge:assistant-error",
    ...stalePayload,
    assistantIdentity: "current-bootstrap-timeout",
    userIdentity: "user:2:current-binding-turn",
    userText: currentPrompt,
    signature: "current-bootstrap-timeout-signature"
  }, sender);
  assert.equal(response.ok, true);
  assert.equal(response.bridgeOwned, true,
    "a timeout after the current lifecycle bootstrap is confirmed may be retried");
  assert.equal(response.retryEligible, true);

  console.log("Chat Bridge timeout ownership does not cross a fresh bootstrap boundary.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
