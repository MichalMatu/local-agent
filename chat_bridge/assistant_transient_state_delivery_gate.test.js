"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  let transientState = "";
  let h;
  h = createHarness({
    exhaustionGuardProbe: async () => ({
      ok: true,
      reason: "ready",
      guardVersion: h.EXHAUSTION_GUARD_VERSION,
      recoverableAssistantError: false,
      assistantGenerating: Boolean(transientState),
      assistantTransientState: transientState
    })
  });

  let response = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
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
  assert.equal(response.reason, "sent");
  assert.equal(h.sentMessages.length, 1);

  transientState = "connection_interrupted";
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_connection_interrupted");
  assert.equal(h.sentMessages.length, 1, "connection interruption must not layer a new Bridge wake");
  assert.equal(h.storage.bridgeState.conversations[chatId].lastStatus, "assistant_connection_interrupted");
  assert.equal(h.tabMessages.some((entry) => entry.message?.type === "bridge:assistant-recovery-kick"), false,
    "connection interruption has no proven native Retry contract");

  transientState = "extended_thinking";
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_extended_thinking");
  assert.equal(h.sentMessages.length, 1, "extended thinking must not layer a new Bridge wake");
  assert.equal(h.storage.bridgeState.conversations[chatId].lastStatus, "assistant_extended_thinking");
  assert.equal(h.tabMessages.some((entry) => entry.message?.type === "bridge:assistant-recovery-kick"), false,
    "Bridge must not click the optional faster-model action");

  transientState = "";
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  assert.equal(response.reason, "sent");
  assert.equal(h.sentMessages.length, 2, "normal delivery resumes after the transient state disappears");

  console.log("Chat Bridge blocks wakes during captured transient assistant states.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
