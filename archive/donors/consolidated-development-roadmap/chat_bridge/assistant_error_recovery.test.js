"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const { storage, alarms, sentMessages, sendRuntimeMessage, MATRIX_BINDING } = createHarness();
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

  response = await sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  assert.equal(response.reason, "sent");
  assert.equal(sentMessages.length, 1);
  const bridgePrompt = sentMessages[0].message.prompt;
  assert.match(bridgePrompt, /\[LA_CHAT=chat-[0-9a-f]{8}\]/);

  const sender = { tab: { id: 11, url: "https://chatgpt.com/c/a" } };
  const report = (userText = bridgePrompt, userIdentity = "bridge-user-1") => sendRuntimeMessage({
    type: "bridge:assistant-error",
    conversationUrl: "https://chatgpt.com/c/a",
    kind: "message_delivery_timeout",
    assistantIdentity: "timeout-answer",
    userIdentity,
    userText,
    signature: "timeout-signature"
  }, sender);
  const authorize = (userText = bridgePrompt, userIdentity = "bridge-user-1", contextPatch = {}) => {
    const conversation = storage.bridgeState.conversations[chatId];
    return sendRuntimeMessage({
      type: "bridge:authorize-assistant-retry",
      conversationUrl: "https://chatgpt.com/c/a",
      kind: "message_delivery_timeout",
      assistantIdentity: "timeout-answer",
      userIdentity,
      userText,
      signature: "timeout-signature",
      bindingRevision: conversation.bindingRevision,
      generation: conversation.generation,
      ...contextPatch
    }, sender);
  };

  response = await report();
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_delivery_timeout");
  assert.equal(response.bridgeOwned, true);
  assert.equal(response.retryEligible, true);
  assert.equal(response.attempts, 0);
  assert.equal(response.retryAfterMs, 1500);
  assert.equal(response.bindingRevision, storage.bridgeState.conversations[chatId].bindingRevision);
  assert.equal(response.generation, storage.bridgeState.conversations[chatId].generation);
  assert.equal(storage.bridgeState.conversations[chatId].lastStatus, "assistant_delivery_timeout");

  response = await authorize(bridgePrompt, "bridge-user-1", {
    generation: storage.bridgeState.conversations[chatId].generation + 1
  });
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_retry_stale_context");
  assert.equal(storage.bridgeAssistantErrorRecovery?.entries?.[chatId], undefined,
    "stale authorization must not consume retry budget");

  response = await authorize();
  assert.equal(response.ok, true);
  assert.equal(response.attempt, 1);
  assert.equal(storage.bridgeState.conversations[chatId].lastStatus, "assistant_retry_1");

  response = await report();
  assert.equal(response.attempts, 1);
  assert.equal(response.retryAfterMs, 5000);
  assert.equal((await authorize()).attempt, 2);
  response = await report();
  assert.equal(response.attempts, 2);
  assert.equal(response.retryAfterMs, 15000);
  assert.equal((await authorize()).attempt, 3);

  response = await report();
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_retry_exhausted");
  assert.equal(response.retryEligible, false);
  const exhausted = storage.bridgeState.conversations[chatId];
  assert.equal(exhausted.enabled, false);
  assert.equal(exhausted.lastStatus, "assistant_retry_exhausted");
  assert.equal(exhausted.nextRunAt, null);
  assert.equal(alarms.has(`local-agent-chat:${chatId}`), false);

  response = await sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: chatId,
    patch: { enabled: true, lastStatus: "sent" }
  });
  assert.equal(response.ok, true);
  response = await report("Manual user message", "manual-user");
  assert.equal(response.ok, true);
  assert.equal(response.bridgeOwned, false);
  assert.equal(response.retryEligible, false);
  assert.equal(storage.bridgeState.conversations[chatId].lastStatus, "assistant_delivery_timeout_unowned");
  response = await authorize("Manual user message", "manual-user");
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_retry_not_bridge_owned");

  response = await sendRuntimeMessage({
    type: "bridge:assistant-error",
    conversationUrl: "https://chatgpt.com/c/a",
    kind: "message_delivery_timeout",
    assistantIdentity: "timeout-answer",
    userIdentity: "bridge-user-duplicate-tab",
    userText: bridgePrompt,
    signature: "duplicate-tab"
  }, { tab: { id: 44, url: "https://chatgpt.com/c/a" } });
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_error_wrong_tab");

  response = await sendRuntimeMessage({
    type: "bridge:assistant-error",
    conversationUrl: "https://chatgpt.com/c/a",
    kind: "message_delivery_timeout",
    assistantIdentity: "timeout-answer",
    userIdentity: "bridge-user-2",
    userText: bridgePrompt,
    signature: "wrong-url"
  }, { tab: { id: 22, url: "https://chatgpt.com/c/b" } });
  assert.equal(response.ok, false);
  assert.equal(response.reason, "conversation_not_found");

  console.log("Chat Bridge assistant error recovery tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
