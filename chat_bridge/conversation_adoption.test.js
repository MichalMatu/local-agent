"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

function authority(harness, patch = {}) {
  return {
    schema_version: 1,
    child_request_id: "child-audit-001",
    child_request_digest: `sha256:${"a".repeat(64)}`,
    child_conversation_url: "https://chatgpt.com/c/a",
    repository_id: "matrixhub",
    agent_binding: harness.MATRIX_BINDING,
    bootstrap_digest: `sha256:${"b".repeat(64)}`,
    ...patch
  };
}

(async () => {
  const harness = createHarness();
  const adoptedAuthority = authority(harness);

  // The operator popup has no message route for adoption. Only trusted worker code may
  // invoke adoptRegisteredConversation with a prevalidated durable authority envelope.
  let response = await harness.sendRuntimeMessage({
    type: "bridge:adopt-registered-conversation",
    authority: adoptedAuthority
  });
  assert.equal(response, undefined);
  assert.equal(harness.storage.bridgeState, undefined);

  const adopted = await harness.evaluate(
    `adoptRegisteredConversation(${JSON.stringify(adoptedAuthority)})`
  );
  assert.equal(adopted.url, adoptedAuthority.child_conversation_url);
  assert.equal(adopted.repositoryId, "matrixhub");
  assert.equal(adopted.agentBinding, harness.MATRIX_BINDING);
  assert.equal(adopted.bootstrapPending, false);
  assert.equal(adopted.lastStatus, "adopted_registered_child");

  const conversations = Object.values(harness.storage.bridgeState.conversations);
  assert.equal(conversations.length, 1);
  const chatId = conversations[0].id;

  response = await harness.sendRuntimeMessage({
    type: "bridge:run-now",
    conversationId: chatId
  });
  assert.equal(response.ok, true);
  assert.equal(response.bridgeMode, "wake");
  assert.equal(harness.sentMessages.length, 1);
  assert.equal(harness.sentMessages[0].message.bridgeMode, "wake");
  assert.match(harness.sentMessages[0].message.prompt, /WAKE/);
  assert.equal(harness.storage.bridgeState.conversations[chatId].bootstrapPending, false);

  const retry = await harness.evaluate(
    `adoptRegisteredConversation(${JSON.stringify(adoptedAuthority)})`
  );
  assert.equal(retry.id, chatId);
  assert.equal(Object.keys(harness.storage.bridgeState.conversations).length, 1);
  assert.equal(harness.storage.bridgeState.conversations[chatId].bootstrapPending, false);

  const conflicting = authority(harness, {
    repository_id: "tracker",
    agent_binding: harness.TRACKER_BINDING
  });
  await assert.rejects(
    harness.evaluate(`adoptRegisteredConversation(${JSON.stringify(conflicting)})`),
    /different repository binding/
  );

  const nonCanonical = authority(harness, {
    child_conversation_url: "https://chat.openai.com/c/a"
  });
  await assert.rejects(
    harness.evaluate(`adoptRegisteredConversation(${JSON.stringify(nonCanonical)})`),
    /must be canonical/
  );

  console.log("Chat Bridge registered child adoption tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
