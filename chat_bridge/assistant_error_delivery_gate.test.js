"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  let recoverable = false;
  let h;
  h = createHarness({
    exhaustionGuardProbe: async () => ({
      ok: true,
      reason: "ready",
      guardVersion: h.EXHAUSTION_GUARD_VERSION,
      recoverableAssistantError: recoverable,
      assistantGenerating: false
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

  recoverable = true;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_recovery_pending");
  assert.equal(h.sentMessages.length, 1, "unresolved assistant timeout must block a new wake");
  assert.equal(h.storage.bridgeState.conversations[chatId].lastStatus, "assistant_recovery_pending");
  assert.ok(h.tabMessages.some((entry) =>
    entry.tabId === 11 && entry.message?.type === "bridge:assistant-recovery-kick"
  ), "blocked wake must re-arm timeout recovery in the exact delivery tab");

  recoverable = false;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  assert.equal(response.reason, "sent");
  assert.equal(h.sentMessages.length, 2, "wake may resume once live DOM no longer contains the timeout");

  console.log("Chat Bridge blocks new wakes while assistant timeout recovery remains unresolved.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
