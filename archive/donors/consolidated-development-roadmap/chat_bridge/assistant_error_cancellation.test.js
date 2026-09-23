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
  const bridgePrompt = h.sentMessages.at(-1).message.prompt;

  const errorMessage = (extra = {}) => ({
    conversationUrl: url,
    kind: "message_delivery_timeout",
    assistantIdentity: "timeout-answer",
    userIdentity: "user:1:timeout",
    userText: bridgePrompt,
    signature: "timeout-cancellation-signature",
    ...extra
  });

  await h.sendRuntimeMessage({
    type: "bridge:save-global-settings",
    settings: { masterEnabled: false }
  });
  response = await h.sendRuntimeMessage({ type: "bridge:assistant-error", ...errorMessage() }, sender);
  assert.equal(response.ok, true);
  assert.equal(response.bridgeOwned, true);
  assert.equal(response.retryEligible, false);

  response = await h.sendRuntimeMessage({
    type: "bridge:authorize-assistant-retry",
    ...errorMessage({ bindingRevision: response.bindingRevision, generation: response.generation })
  }, sender);
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_retry_cancelled");
  assert.equal(h.storage.bridgeAssistantErrorRecovery?.entries?.[chatId], undefined,
    "Master-off authorization must not consume retry budget");

  await h.sendRuntimeMessage({
    type: "bridge:save-global-settings",
    settings: { masterEnabled: true }
  });
  await h.sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: chatId,
    patch: { enabled: false }
  });
  response = await h.sendRuntimeMessage({ type: "bridge:assistant-error", ...errorMessage() }, sender);
  assert.equal(response.ok, true);
  assert.equal(response.bridgeOwned, true);
  assert.equal(response.retryEligible, false);

  response = await h.sendRuntimeMessage({
    type: "bridge:authorize-assistant-retry",
    ...errorMessage({ bindingRevision: response.bindingRevision, generation: response.generation })
  }, sender);
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_retry_cancelled");
  assert.equal(h.storage.bridgeAssistantErrorRecovery?.entries?.[chatId], undefined,
    "disabled-chat authorization must not consume retry budget");

  console.log("Chat Bridge assistant retry cancellation gates preserve retry budget.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
