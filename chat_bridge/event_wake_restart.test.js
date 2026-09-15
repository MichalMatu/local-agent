"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const { createHarness } = require("./worker_test_harness.js");

function fingerprint(value) {
  return protocol.fnv1a32(value);
}

async function addMatrixChat(harness) {
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

function eventFor(harness, taskId) {
  return {
    schema_version: 1,
    event_id: `evt-${"e".repeat(32)}`,
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

(async () => {
  const storage = {};

  const firstWorker = createHarness({ storage });
  const conversation = await addMatrixChat(firstWorker);
  const waiting = await waitTask(firstWorker, conversation, "restart-1");
  assert.equal(waiting.ok, true);
  assert.equal(storage.eventWakeState.watches[conversation.id].taskId, "restart-1");

  // Simulate MV3 worker replacement while the task is still running.
  const secondWorker = createHarness({ storage });
  assert.equal(storage.eventWakeState.watches[conversation.id].taskId, "restart-1");
  const accepted = await secondWorker.evaluate(
    `acceptNativeTaskEvent(${JSON.stringify(eventFor(secondWorker, "restart-1"))})`
  );
  assert.equal(accepted.ok, true);
  assert.equal(accepted.reason, "event_pending");
  assert.equal(storage.eventWakeState.watches[conversation.id], undefined);
  assert.equal(storage.eventWakeState.pendingWakes[conversation.id].taskId, "restart-1");

  // Replace the worker again after native receive but before ChatGPT delivery.
  const thirdWorker = createHarness({ storage });
  assert.equal(thirdWorker.alarms.size, 0, "new worker starts with no in-memory test alarms");
  await thirdWorker.startup();
  assert.ok(
    thirdWorker.alarms.has(`local-agent-chat:${conversation.id}`),
    "startup reconciliation must recreate the pending event wake alarm"
  );

  const delivery = await thirdWorker.evaluate(
    `runFeedbackCycle({ conversationId: ${JSON.stringify(conversation.id)}, manual: false })`
  );
  assert.equal(delivery.ok, true);
  assert.equal(delivery.eventWake.taskId, "restart-1");
  assert.equal(thirdWorker.sentMessages.length, 1);
  assert.match(thirdWorker.sentMessages[0].message.prompt, /\[LA_TASK=restart-1\]/);
  assert.equal(storage.eventWakeState.pendingWakes[conversation.id], undefined);
  assert.equal(storage.eventWakeState.watches[conversation.id], undefined);

  console.log("Chat Bridge event wake restart persistence tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
