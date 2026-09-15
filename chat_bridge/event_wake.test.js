"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const { createHarness } = require("./worker_test_harness.js");

const MATRIX_URL = "https://chatgpt.com/c/a";
const MATRIX_REPOSITORY = "MichalMatu/MatrixHub";

function nativeEvent(harness, taskId, overrides = {}) {
  return {
    schema_version: 1,
    event_id: `evt-${String(overrides.eventHex || "a").repeat(32).slice(0, 32)}`,
    event_type: "task_result_ready",
    emitted_at: "2026-09-15T20:00:00+00:00",
    repository_id: "matrixhub",
    repository: MATRIX_REPOSITORY,
    agent_binding: harness.MATRIX_BINDING,
    task_id: taskId,
    task_digest: `digest-${taskId}`,
    result_status: "done",
    ...overrides
  };
}

async function addMatrixChat(harness, url = MATRIX_URL) {
  const response = await harness.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url,
      repositoryId: "matrixhub",
      enabled: true,
      preferredTabId: 11,
      assistantBaseline: ""
    }
  });
  assert.equal(response.ok, true);
  return response.conversation;
}

async function assistantControl(harness, conversation, marker, assistantIdentity = "assistant-new") {
  const control = protocol.parseAssistantControl(marker);
  assert.ok(control, `control must parse: ${marker}`);
  return harness.sendRuntimeMessage(
    {
      type: "bridge:assistant-control",
      conversationUrl: conversation.url,
      assistantIdentity,
      bindingRevision: conversation.bindingRevision,
      control,
      fingerprint: protocol.controlFingerprint(
        conversation.url,
        marker,
        control,
        assistantIdentity
      )
    },
    {
      id: harness.chrome.runtime.id,
      frameId: 0,
      url: conversation.url,
      tab: { id: conversation.preferredTabId || 11, url: conversation.url }
    }
  );
}

async function acceptEvent(harness, event) {
  return harness.evaluate(`acceptNativeTaskEvent(${JSON.stringify(event)})`);
}

(async () => {
  {
    const harness = createHarness();
    const conversation = await addMatrixChat(harness);
    const waiting = await assistantControl(harness, conversation, "[LAB:WAIT_TASK=build-1]");
    assert.equal(waiting.ok, true);
    assert.equal(waiting.reason, "waiting_task");
    assert.equal(harness.storage.eventWakeState.watches[conversation.id].taskId, "build-1");

    const accepted = await acceptEvent(harness, nativeEvent(harness, "build-1"));
    assert.equal(accepted.ok, true);
    assert.equal(accepted.reason, "event_pending");
    assert.equal(accepted.matchedChatId, conversation.id);
    assert.equal(harness.storage.eventWakeState.pendingWakes[conversation.id].taskId, "build-1");
    assert.ok(harness.alarms.has(`local-agent-chat:${conversation.id}`));

    const delivery = await harness.evaluate(
      `runFeedbackCycle({ conversationId: ${JSON.stringify(conversation.id)}, manual: false })`
    );
    assert.equal(delivery.ok, true);
    assert.equal(delivery.eventWake.taskId, "build-1");
    const sent = harness.sentMessages.at(-1).message.prompt;
    assert.match(sent, /\[LA_EVENT=task_result_ready\]/);
    assert.match(sent, /\[LA_TASK=build-1\]/);
    assert.match(sent, /Read the exact result before deciding the next action/);
    assert.equal(harness.storage.eventWakeState.pendingWakes[conversation.id], undefined);
    assert.equal(harness.storage.eventWakeState.watches[conversation.id], undefined);
  }

  // Fast-task race: result reaches the extension before the assistant registers WAIT_TASK.
  {
    const harness = createHarness();
    const conversation = await addMatrixChat(harness);
    const early = nativeEvent(harness, "fast-1", { eventHex: "b" });
    const cached = await acceptEvent(harness, early);
    assert.equal(cached.ok, true);
    assert.equal(cached.reason, "event_cached");
    assert.equal(cached.matchedChatId, null);

    const waiting = await assistantControl(harness, conversation, "[LAB:WAIT_TASK=fast-1]");
    assert.equal(waiting.ok, true);
    assert.equal(waiting.reason, "task_result_already_ready");
    assert.equal(waiting.matchedRecentEvent, true);
    assert.equal(harness.storage.eventWakeState.pendingWakes[conversation.id].eventId, early.event_id);
    assert.ok(harness.alarms.has(`local-agent-chat:${conversation.id}`));
  }

  // Pause preserves the watch and pending event but must not wake the chat until resume.
  {
    const harness = createHarness();
    const conversation = await addMatrixChat(harness);
    await assistantControl(harness, conversation, "[LAB:WAIT_TASK=paused-1]", "assistant-wait");
    const paused = await assistantControl(harness, conversation, "[LAB:PAUSE]", "assistant-pause");
    assert.equal(paused.ok, true);
    assert.equal(harness.alarms.has(`local-agent-chat:${conversation.id}`), false);
    assert.equal(harness.storage.eventWakeState.watches[conversation.id].taskId, "paused-1");

    const accepted = await acceptEvent(
      harness,
      nativeEvent(harness, "paused-1", { eventHex: "c" })
    );
    assert.equal(accepted.ok, true);
    assert.equal(accepted.schedulable, false);
    assert.equal(harness.alarms.has(`local-agent-chat:${conversation.id}`), false);
    assert.equal(harness.storage.eventWakeState.pendingWakes[conversation.id].taskId, "paused-1");

    const resumedConversation = harness.storage.bridgeState.conversations[conversation.id];
    const resumed = await assistantControl(
      harness,
      resumedConversation,
      "[LAB:RESUME]",
      "assistant-resume"
    );
    assert.equal(resumed.ok, true);
    assert.ok(harness.alarms.has(`local-agent-chat:${conversation.id}`));
  }

  // A valid event for a different binding must never wake the Matrix conversation.
  {
    const harness = createHarness();
    const conversation = await addMatrixChat(harness);
    await assistantControl(harness, conversation, "[LAB:WAIT_TASK=route-1]");
    const before = harness.alarms.get(`local-agent-chat:${conversation.id}`)?.scheduledTime;
    const accepted = await acceptEvent(
      harness,
      nativeEvent(harness, "route-1", {
        eventHex: "d",
        repository_id: "tracker",
        repository: "MichalMatu/tracker",
        agent_binding: harness.TRACKER_BINDING
      })
    );
    assert.equal(accepted.ok, true);
    assert.equal(accepted.matchedChatId, null);
    assert.equal(harness.storage.eventWakeState.pendingWakes[conversation.id], undefined);
    const after = harness.alarms.get(`local-agent-chat:${conversation.id}`)?.scheduledTime;
    assert.equal(after, before);
  }

  // Only one chat can own an exact repository/binding/task watch. A rejected second owner
  // must retain polling fallback rather than becoming dependent on the native event path.
  {
    const harness = createHarness();
    const first = await addMatrixChat(harness, "https://chatgpt.com/c/owner-a");
    const second = await addMatrixChat(harness, "https://chatgpt.com/c/owner-b");
    const firstWait = await assistantControl(harness, first, "[LAB:WAIT_TASK=shared-1]", "assistant-owner-a");
    assert.equal(firstWait.ok, true);

    const secondWait = await assistantControl(harness, second, "[LAB:WAIT_TASK=shared-1]", "assistant-owner-b");
    assert.equal(secondWait.ok, false);
    assert.equal(secondWait.reason, "task_watch_conflict");
    assert.equal(secondWait.conflictChatId, first.id);
    assert.equal(secondWait.fallbackScheduled, true);
    assert.equal(harness.storage.eventWakeState.watches[first.id].taskId, "shared-1");
    assert.equal(harness.storage.eventWakeState.watches[second.id], undefined);
    assert.ok(harness.alarms.has(`local-agent-chat:${second.id}`));
  }

  console.log("Chat Bridge event wake tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
