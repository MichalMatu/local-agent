"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const h = createHarness();
  const url = "https://chatgpt.com/c/a";
  const contentSender = { tab: { id: 11, url } };

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

  const report = (kind, userText, signature = `sig-${kind}`, assistantGenerating = false) =>
    h.sendRuntimeMessage({
      type: "bridge:assistant-transient-state",
      conversationUrl: url,
      kind,
      signature,
      userIdentity: "user-current",
      userText,
      assistantGenerating,
      composerOccupied: false
    }, contentSender);

  response = await report("connection_interrupted", bridgePrompt, "sig-first-interruption");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_connection_interrupted");
  assert.equal(response.action, "wait");
  assert.equal(h.sentMessages.length, 1, "initial proactive report must not submit a second user turn");

  h.storage.bridgeAssistantTransientRecovery.entries[chatId].firstSeenAt =
    new Date(Date.now() - 60_000).toISOString();
  response = await report("connection_interrupted", bridgePrompt, "sig-new-turn");
  assert.equal(response.reason, "assistant_connection_interrupted");
  assert.equal(response.action, "wait");
  assert.equal(h.storage.bridgeAssistantTransientRecovery.entries[chatId].signature, "sig-new-turn");
  assert.equal(h.sentMessages.length, 1,
    "a changed interruption fingerprint must start a fresh wait instead of inheriting an old timer");

  h.storage.bridgeAssistantTransientRecovery.entries[chatId].firstSeenAt =
    new Date(Date.now() - 60_000).toISOString();
  response = await report("connection_interrupted", bridgePrompt, "sig-new-turn");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_connection_continue_sent");
  assert.equal(response.action, "continue");
  assert.equal(h.sentMessages.at(-1).message.prompt, "Continue.");

  h.storage.bridgeAssistantTransientRecovery.entries[chatId].continueSentAt =
    new Date(Date.now() - 70_000).toISOString();
  response = await report("connection_interrupted", "Continue.", "sig-after-continue");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_tab_reloaded");
  assert.equal(response.action, "reload");
  assert.deepEqual(h.tabReloads, [11]);

  response = await report("connection_interrupted", "Continue.", "sig-after-continue");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_connection_reload_exhausted");
  assert.equal(response.terminal, true);
  assert.deepEqual(h.tabReloads, [11], "proactive reports must not create a reload loop");

  response = await h.sendRuntimeMessage({
    type: "bridge:assistant-transient-clear",
    conversationUrl: url
  }, contentSender);
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_transient_cleared");
  assert.equal(h.storage.bridgeAssistantTransientRecovery.entries[chatId], undefined,
    "worker clear must retire its durable reload reservation once the guard proves stable health");

  response = await report("connection_interrupted", bridgePrompt, "sig-later-interruption");
  assert.equal(response.reason, "assistant_connection_interrupted");
  assert.equal(response.action, "wait");
  assert.deepEqual(h.tabReloads, [11], "a later interruption must start with a fresh bounded wait");

  response = await h.sendRuntimeMessage({
    type: "bridge:assistant-transient-clear",
    conversationUrl: url
  }, contentSender);
  assert.equal(response.ok, true);

  response = await report("extended_thinking", bridgePrompt, "sig-thinking", true);
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_extended_thinking");
  assert.equal(response.terminal, true);
  assert.deepEqual(h.tabReloads, [11], "extended thinking stays wait-only");

  response = await report("stalled", "manual operator prompt", "sig-manual-stall", true);
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_stalled_unowned");
  assert.equal(response.terminal, true);
  assert.deepEqual(h.tabReloads, [11], "manual stalled turns are diagnostic-only");

  response = await report("stalled", bridgePrompt, "sig-owned-stall", true);
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_tab_reloaded");
  assert.deepEqual(h.tabReloads, [11, 11], "owned generic stall reloads immediately after detector proof");

  console.log("Chat Bridge fingerprints, escalates and retires owned transient recovery episodes.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
