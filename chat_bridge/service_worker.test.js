"use strict";

const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const h = createHarness();
  const {
    storage,
    alarms,
    sentMessages,
    sendRuntimeMessage,
    MATRIX_BINDING,
    TRACKER_BINDING
  } = h;

  // A chat no longer needs a repository binding to become Bridge-managed.
  let response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      label: "Superchat A",
      enabled: false,
      preferredTabId: 11
    }
  });
  assert.equal(response.ok, true, response.error);
  const aId = response.conversation.id;
  assert.equal(response.conversation.repositoryId, "host-ops");
  assert.equal(response.conversation.bindingRevision, 1);
  assert.equal(response.conversation.bootstrapPending, true);

  // Local pacing still works, but repository metadata is not execution authority.
  response = await sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: aId,
    patch: { enabled: true, intervalOverrideMinutes: 7 }
  });
  assert.equal(response.ok, true, response.error);
  assert.equal(response.conversation.enabled, true);
  assert.equal(response.conversation.intervalOverrideMinutes, 7);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), true);

  response = await sendRuntimeMessage({ type: "bridge:run-now", conversationId: aId });
  assert.equal(response.ok, true, response.reason);
  assert.equal(response.bridgeMode, "bootstrap");
  assert.equal(response.repositoryId, "host-ops");
  let prompt = sentMessages.at(-1).message.prompt;
  assert.match(prompt, /\[LA_CHAT=chat-[0-9a-f]{8}\]/);
  assert.match(prompt, /transport\/scheduling channel, not a repository execution binding/);
  assert.match(prompt, /multiple repositories, including donor and target repositories/);
  assert.match(prompt, /exact canonical agent_binding/);
  assert.doesNotMatch(prompt, /\[LA_AGENT=/);
  assert.doesNotMatch(prompt, /Work only on repository/);

  response = await sendRuntimeMessage({ type: "bridge:run-now", conversationId: aId });
  assert.equal(response.ok, true, response.reason);
  assert.equal(response.bridgeMode, "wake");
  prompt = sentMessages.at(-1).message.prompt;
  assert.match(prompt, /WAKE/);
  assert.match(prompt, /without rebinding the chat/);
  assert.doesNotMatch(prompt, /\[LA_AGENT=/);

  // Explicit legacy metadata may still be stored, but it does not narrow the chat's reasoning scope.
  response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/b",
      label: "Superchat B",
      enabled: true,
      preferredTabId: 22,
      agentBinding: TRACKER_BINDING
    }
  });
  assert.equal(response.ok, true, response.error);
  const bId = response.conversation.id;
  assert.equal(response.conversation.repositoryId, "tracker");
  assert.equal(response.conversation.agentBinding, TRACKER_BINDING);

  response = await sendRuntimeMessage({ type: "bridge:run-now", conversationId: bId });
  assert.equal(response.ok, true, response.reason);
  prompt = sentMessages.at(-1).message.prompt;
  assert.match(prompt, /tracker=MichalMatu\/tracker@be481b25-9d97-4205-b93f-95f5c5827441;execution=enabled/);
  assert.match(prompt, /donor and target repositories/);
  assert.doesNotMatch(prompt, /Work only on repository MichalMatu\/tracker/);

  // Ordinary upsert cannot silently rewrite legacy metadata.
  response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/b",
      label: "Superchat B renamed",
      preferredTabId: 22,
      agentBinding: MATRIX_BINDING
    }
  });
  assert.equal(response.ok, true, response.error);
  assert.equal(response.conversation.agentBinding, TRACKER_BINDING);
  assert.equal(response.conversation.repositoryId, "tracker");

  // Legacy rebind is only a metadata/epoch refresh; prompt scope remains transport-only/multirepo.
  response = await sendRuntimeMessage({
    type: "bridge:rebind-conversation",
    conversationId: bId,
    binding: { agentBinding: MATRIX_BINDING }
  });
  assert.equal(response.ok, true, response.error);
  assert.equal(response.conversation.agentBinding, MATRIX_BINDING);
  assert.equal(response.conversation.repositoryId, "matrixhub");
  assert.equal(response.conversation.bindingRevision, 2);
  assert.equal(response.conversation.lastStatus, "transport_metadata_refreshed");
  assert.equal(response.conversation.bootstrapPending, true);

  response = await sendRuntimeMessage({ type: "bridge:run-now", conversationId: bId });
  assert.equal(response.ok, true, response.reason);
  prompt = sentMessages.at(-1).message.prompt;
  assert.match(prompt, /transport\/scheduling channel/);
  assert.match(prompt, /Current runtime catalog:/);
  assert.doesNotMatch(prompt, /Work only on repository MichalMatu\/MatrixHub/);
  assert.doesNotMatch(prompt, /\[LA_AGENT=/);

  // Master remains an operator-level scheduler switch, independent from repository metadata.
  response = await sendRuntimeMessage({
    type: "bridge:save-global-settings",
    settings: { masterEnabled: false }
  });
  assert.equal(response.ok, true, response.error);
  assert.equal(storage.bridgeState.settings.masterEnabled, false);
  assert.equal(alarms.size, 0);

  response = await sendRuntimeMessage({
    type: "bridge:save-global-settings",
    settings: { masterEnabled: true }
  });
  assert.equal(response.ok, true, response.error);
  assert.equal(storage.bridgeState.settings.masterEnabled, true);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), true);
  assert.equal(alarms.has(`local-agent-chat:${bId}`), true);

  console.log("Chat Bridge transport-only Superchat service worker tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});