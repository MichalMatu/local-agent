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

  const payload = {
    conversationUrl: url,
    kind: "message_delivery_timeout",
    assistantIdentity: "timeout-answer",
    userIdentity: "user:1:authorization-race",
    userText: bridgePrompt,
    signature: "authorization-race-signature"
  };
  const report = await h.sendRuntimeMessage({ type: "bridge:assistant-error", ...payload }, sender);
  assert.equal(report.ok, true);
  assert.equal(report.retryEligible, true);

  const originalSet = h.chrome.storage.local.set.bind(h.chrome.storage.local);
  let injectGenerationChange = true;
  h.chrome.storage.local.set = async (patch) => {
    await originalSet(patch);
    if (injectGenerationChange && patch.bridgeAssistantErrorRecovery) {
      injectGenerationChange = false;
      h.storage.bridgeState.conversations[chatId].generation += 1;
    }
  };

  response = await h.sendRuntimeMessage({
    type: "bridge:authorize-assistant-retry",
    ...payload,
    bindingRevision: report.bindingRevision,
    generation: report.generation
  }, sender);
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_retry_stale_context");
  assert.equal(response.attempt, 1,
    "the conservative reservation may be consumed, but must never authorize a stale click");
  assert.equal(h.storage.bridgeAssistantErrorRecovery.entries[chatId].attempts, 1);
  assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);
  assert.notEqual(h.storage.bridgeState.conversations[chatId].lastStatus, "assistant_retry_1",
    "stale finalization must not publish an authorized retry status");

  console.log("Chat Bridge revalidates generation after durable retry reservation before authorizing a click.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
