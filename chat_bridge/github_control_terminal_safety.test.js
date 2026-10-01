"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const runtimeExample = require("./runtime.example.json");
const { createHarness } = require("./worker_test_harness.js");

const matrix = runtimeExample.agents.find((agent) => agent.repository_id === "matrixhub");
assert.ok(matrix);
const url = "https://chatgpt.com/c/a";
const chatId = protocol.conversationId(url);

function controlRecord(overrides = {}) {
  return {
    conversation_id: chatId,
    repository_id: matrix.repository_id,
    repository: matrix.repository,
    agent_binding: matrix.agent_binding,
    binding_revision: 1,
    control_generation: 1,
    enabled: true,
    interval_minutes: 5,
    next_wake_at: null,
    updated_at: new Date().toISOString(),
    ...overrides
  };
}

function harnessWithControl(readControl) {
  return createHarness({
    fetch: async () => ({
      ok: true,
      async json() {
        const control = readControl();
        return {
          ...runtimeExample,
          bootstrap_prompt: "BOOTSTRAP",
          wake_prompt: "WAKE",
          conversation_controls: control ? [control] : []
        };
      }
    })
  });
}

async function addConversation(h) {
  const result = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url,
      label: "Project A",
      enabled: true,
      preferredTabId: 11,
      agentBinding: matrix.agent_binding
    }
  });
  assert.equal(result.ok, true, result.error);
  return result.conversation;
}

(async () => {
  // Conversation-length exhaustion is terminal for the same hard binding. Neither the
  // already-applied desired state nor a newer pacing generation may resurrect that chat.
  {
    let control = controlRecord();
    const h = harnessWithControl(() => control);
    await addConversation(h);
    await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);

    const exhausted = await h.sendRuntimeMessage({
      type: "bridge:conversation-exhausted",
      conversationUrl: url,
      assistantIdentity: "limit-message",
      signature: "deadbeef"
    }, { tab: { id: 11, url } });
    assert.equal(exhausted.ok, true);
    assert.equal(exhausted.reason, "conversation_exhausted");
    const terminalGeneration = h.storage.bridgeState.conversations[chatId].generation;
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);
    assert.equal(h.alarms.has(`local-agent-chat:${chatId}`), false);

    const sameGeneration = await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(sameGeneration.applied.length, 0);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);
    assert.equal(h.storage.bridgeState.conversations[chatId].lastStatus, "conversation_exhausted");
    assert.equal(h.storage.bridgeState.conversations[chatId].generation, terminalGeneration);
    assert.equal(h.storage.bridgeGithubControlApplied[chatId].localGeneration, terminalGeneration);
    assert.equal(h.alarms.has(`local-agent-chat:${chatId}`), false);

    control = controlRecord({
      control_generation: 2,
      enabled: true,
      updated_at: new Date(Date.now() + 1000).toISOString()
    });
    const newerGeneration = await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(newerGeneration.applied.length, 0);
    assert.equal(h.storage.bridgeGithubControlApplied[chatId].generation, 2);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);
    assert.equal(h.storage.bridgeState.conversations[chatId].lastStatus, "conversation_exhausted");
    assert.equal(h.storage.bridgeState.conversations[chatId].generation, terminalGeneration);
    assert.equal(h.alarms.has(`local-agent-chat:${chatId}`), false);

    const manual = await h.sendRuntimeMessage({
      type: "bridge:run-now",
      conversationId: chatId
    });
    assert.equal(manual.ok, false);
    assert.equal(manual.reason, "conversation_exhausted");
    assert.equal(h.sentMessages.length, 0);
  }

  // Retry exhaustion is a local safety stop for the already-applied generation, while a
  // new remote generation is an explicit operator decision that may recover the conversation.
  {
    let control = controlRecord();
    const h = harnessWithControl(() => control);
    await addConversation(h);
    await h.evaluate("reconcileGithubConversationControls()");

    const marked = await h.evaluate(`(async () => {
      const state = await getBridgeState();
      return markAssistantRetryExhausted(state.conversations["${chatId}"]);
    })()`);
    assert.equal(marked, true);
    const terminalGeneration = h.storage.bridgeState.conversations[chatId].generation;
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);
    assert.equal(h.storage.bridgeState.conversations[chatId].lastStatus, "assistant_retry_exhausted");
    assert.equal(h.alarms.has(`local-agent-chat:${chatId}`), false);

    const sameGeneration = await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(sameGeneration.applied.length, 0);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);
    assert.equal(h.storage.bridgeState.conversations[chatId].lastStatus, "assistant_retry_exhausted");
    assert.equal(h.storage.bridgeState.conversations[chatId].generation, terminalGeneration);
    assert.equal(h.storage.bridgeGithubControlApplied[chatId].localGeneration, terminalGeneration);
    assert.equal(h.alarms.has(`local-agent-chat:${chatId}`), false);

    control = controlRecord({
      control_generation: 2,
      enabled: true,
      updated_at: new Date(Date.now() + 1000).toISOString()
    });
    const recovered = await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(recovered.applied.length, 1);
    assert.equal(h.storage.bridgeGithubControlApplied[chatId].generation, 2);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);
    assert.equal(h.storage.bridgeState.conversations[chatId].lastStatus, "github_control_enabled");
    assert.equal(h.alarms.has(`local-agent-chat:${chatId}`), true);
  }

  console.log("GitHub Bridge terminal safety reconciliation tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
