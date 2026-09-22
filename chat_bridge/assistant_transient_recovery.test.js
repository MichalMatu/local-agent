"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  let transientState = "";
  let assistantGenerating = false;
  let latestUserText = "";
  let latestUserIdentity = "user-current";
  let composerOccupied = false;
  let h;
  h = createHarness({
    exhaustionGuardProbe: async () => ({
      ok: true,
      reason: "ready",
      guardVersion: h.EXHAUSTION_GUARD_VERSION,
      recoverableAssistantError: false,
      assistantGenerating,
      assistantTransientState: transientState,
      assistantTransientSignature: transientState ? `sig-${transientState}` : "",
      assistantTransientUserIdentity: transientState ? latestUserIdentity : "",
      assistantTransientUserText: transientState ? latestUserText : "",
      composerOccupied
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
  latestUserText = h.sentMessages.at(-1).message.prompt;

  transientState = "connection_interrupted";
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_connection_interrupted");
  assert.equal(h.sentMessages.length, 1, "first interruption observation must only wait");
  assert.deepEqual(h.tabReloads, []);

  h.storage.bridgeAssistantTransientRecovery.entries[chatId].firstSeenAt =
    new Date(Date.now() - 60_000).toISOString();
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_connection_continue_sent");
  assert.equal(h.sentMessages.at(-1).message.prompt, "Continue.");
  assert.deepEqual(h.tabReloads, []);

  latestUserText = "Continue.";
  latestUserIdentity = "user-continue";
  h.storage.bridgeAssistantTransientRecovery.entries[chatId].continueSentAt =
    new Date(Date.now() - 70_000).toISOString();
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_tab_reloaded");
  assert.deepEqual(h.tabReloads, [11], "persistent interruption must reload the whole tab once");

  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_connection_reload_exhausted");
  assert.deepEqual(h.tabReloads, [11], "durable reservation must prevent reload loops");

  transientState = "";
  assistantGenerating = false;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  assert.equal(h.storage.bridgeAssistantTransientRecovery.entries[chatId], undefined,
    "clean preflight must retire the previous recovery episode");
  latestUserText = h.sentMessages.at(-1).message.prompt;
  latestUserIdentity = "user-wake";

  transientState = "stalled";
  assistantGenerating = true;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_tab_reloaded");
  assert.deepEqual(h.tabReloads, [11, 11], "proven no-progress stall must reload atomically");

  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_stalled_after_reload");
  assert.deepEqual(h.tabReloads, [11, 11]);

  transientState = "";
  assistantGenerating = false;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  latestUserText = h.sentMessages.at(-1).message.prompt;
  latestUserIdentity = "user-draft-protection";

  transientState = "stalled";
  assistantGenerating = true;
  composerOccupied = true;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "composer_not_empty");
  assert.deepEqual(h.tabReloads, [11, 11], "operator draft must block automatic tab reload");

  transientState = "";
  assistantGenerating = false;
  composerOccupied = false;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);

  latestUserText = "manual operator prompt";
  latestUserIdentity = "user-manual";
  transientState = "stalled";
  assistantGenerating = true;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_stalled_unowned");
  assert.deepEqual(h.tabReloads, [11, 11], "manual operator turns must remain diagnostic-only");

  transientState = "";
  assistantGenerating = false;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.ok, true);
  latestUserText = h.sentMessages.at(-1).message.prompt;
  latestUserIdentity = "user-busy-interruption";

  transientState = "connection_interrupted";
  assistantGenerating = true;
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_connection_interrupted");
  h.storage.bridgeAssistantTransientRecovery.entries[chatId].firstSeenAt =
    new Date(Date.now() - 60_000).toISOString();
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_connection_continue_pending");
  assert.deepEqual(h.tabReloads, [11, 11]);

  h.storage.bridgeAssistantTransientRecovery.entries[chatId].firstSeenAt =
    new Date(Date.now() - 130_000).toISOString();
  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: chatId });
  assert.equal(response.reason, "assistant_tab_reloaded");
  assert.deepEqual(h.tabReloads, [11, 11, 11],
    "connection interruption that never becomes sendable must eventually reload once");

  console.log("Chat Bridge transient recovery is bounded, owned, draft-safe and reload-safe.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
