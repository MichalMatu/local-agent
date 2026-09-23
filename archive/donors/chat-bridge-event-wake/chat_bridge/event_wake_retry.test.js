"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const { createHarness } = require("./worker_test_harness.js");

function fingerprint(value) {
  return protocol.fnv1a32(value);
}

async function addChat(harness) {
  const response = await harness.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      repositoryId: "matrixhub",
      enabled: true,
      preferredTabId: 11,
      assistantBaseline: ""
    }
  });
  assert.equal(response.ok, true);
  return response.conversation;
}

async function waitTask(harness, conversation, taskId) {
  const marker = `[LAB:WAIT_TASK=${taskId}]`;
  return harness.sendRuntimeMessage({
    type: "bridge:assistant-control",
    conversationUrl: conversation.url,
    assistantIdentity: `assistant-${taskId}`,
    bindingRevision: conversation.bindingRevision,
    control: protocol.parseAssistantControl(marker),
    fingerprint: fingerprint(marker)
  }, {
    id: harness.chrome.runtime.id,
    frameId: 0,
    url: conversation.url,
    tab: { id: 11, url: conversation.url }
  });
}

function nativeEvent(harness, taskId, hex) {
  return {
    schema_version: 1,
    event_id: `evt-${hex.repeat(32)}`,
    event_type: "task_result_ready",
    emitted_at: "2026-09-15T22:00:00+00:00",
    repository_id: "matrixhub",
    repository: "MichalMatu/MatrixHub",
    agent_binding: harness.MATRIX_BINDING,
    task_id: taskId,
    task_digest: `digest-${taskId}`,
    result_status: "done"
  };
}

async function accept(harness, event) {
  return harness.evaluate(`acceptNativeTaskEvent(${JSON.stringify(event)})`);
}

(async () => {
  // Missing ChatGPT tab must not consume the durable pending event.
  {
    const harness = createHarness();
    const conversation = await addChat(harness);
    await waitTask(harness, conversation, "missing-tab-1");
    const event = nativeEvent(harness, "missing-tab-1", "a");
    assert.equal((await accept(harness, event)).ok, true);
    harness.tabs.splice(0, harness.tabs.length);

    const result = await harness.evaluate(
      `runFeedbackCycle({ conversationId: ${JSON.stringify(conversation.id)}, manual: false })`
    );
    assert.equal(result.ok, false);
    assert.equal(result.reason, "conversation_tab_missing");
    assert.equal(harness.storage.eventWakeState.pendingWakes[conversation.id].eventId, event.event_id);
    assert.equal(harness.sentMessages.length, 0);
    assert.ok(harness.alarms.has(`local-agent-chat:${conversation.id}`));
  }

  // A transient send failure retains the same pending event; the next successful delivery
  // consumes it once and returns to normal scheduling.
  {
    let attempts = 0;
    const harness = createHarness({
      sendMessage: async ({ authorize }) => {
        attempts += 1;
        if (attempts === 1) {
          return {
            ok: false,
            reason: "send_button_not_ready",
            protocolVersion: protocol.CONTENT_PROTOCOL_VERSION
          };
        }
        const permission = await authorize();
        assert.equal(permission.ok, true);
        return {
          ok: true,
          reason: "sent",
          protocolVersion: protocol.CONTENT_PROTOCOL_VERSION
        };
      }
    });
    const conversation = await addChat(harness);
    await waitTask(harness, conversation, "retry-1");
    const event = nativeEvent(harness, "retry-1", "b");
    assert.equal((await accept(harness, event)).ok, true);

    const first = await harness.evaluate(
      `runFeedbackCycle({ conversationId: ${JSON.stringify(conversation.id)}, manual: false })`
    );
    assert.equal(first.ok, false);
    assert.equal(first.reason, "send_button_not_ready");
    assert.equal(harness.storage.eventWakeState.pendingWakes[conversation.id].eventId, event.event_id);

    const second = await harness.evaluate(
      `runFeedbackCycle({ conversationId: ${JSON.stringify(conversation.id)}, manual: false })`
    );
    assert.equal(second.ok, true);
    assert.equal(second.eventWake.eventId, event.event_id);
    assert.equal(harness.storage.eventWakeState.pendingWakes[conversation.id], undefined);
    assert.equal(attempts, 2);
    assert.equal(harness.sentMessages.length, 2,
      "two delivery attempts are expected, but only the successful one consumes the event");
  }

  console.log("Chat Bridge event wake retry retention tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
