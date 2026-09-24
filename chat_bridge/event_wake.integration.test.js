"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const manifest = require("./manifest.json");
const { createHarness } = require("./worker_test_harness.js");

function makeNativePort() {
  const posted = [];
  let messageListener = null;
  let disconnected = false;
  return {
    posted,
    get disconnected() { return disconnected; },
    port: {
      onMessage: { addListener(listener) { messageListener = listener; } },
      onDisconnect: { addListener() {} },
      postMessage(message) { posted.push(JSON.parse(JSON.stringify(message))); },
      disconnect() { disconnected = true; }
    },
    emit(message) {
      assert.ok(messageListener, "native message listener must be installed");
      messageListener(message);
    }
  };
}

function taskEvent(harness, taskId, eventId, overrides = {}) {
  return {
    schema_version: 1,
    event_id: eventId,
    event_type: "task_result_ready",
    emitted_at: new Date().toISOString(),
    repository_id: "matrixhub",
    repository: "MichalMatu/MatrixHub",
    agent_binding: harness.MATRIX_BINDING,
    task_id: taskId,
    task_digest: `digest-${taskId}`,
    result_status: "done",
    ...overrides
  };
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 10));

async function assistantControl(harness, url, fingerprint, marker) {
  return harness.sendRuntimeMessage({
    type: "bridge:assistant-control",
    conversationUrl: url,
    fingerprint,
    control: { marker }
  }, { tab: { url } });
}

async function addConversation(harness, url, binding, preferredTabId) {
  const response = await harness.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url,
      label: `Chat ${preferredTabId}`,
      enabled: true,
      preferredTabId,
      agentBinding: binding
    }
  });
  assert.equal(response.ok, true);
  return response.conversation;
}

(async () => {
  assert.equal(protocol.CONTENT_PROTOCOL_VERSION, 8,
    "WAIT_TASK changes content behavior and must invalidate already-open v7 content scripts");
  assert.deepEqual(
    protocol.parseAssistantControl("[LAB:WAIT_TASK=build-123]"),
    { action: "wait_task", taskId: "build-123", marker: "[LAB:WAIT_TASK=build-123]" }
  );
  assert.equal(protocol.parseAssistantControl("[LAB:WAIT_TASK=bad task]"), null);
  assert.ok(manifest.permissions.includes("nativeMessaging"));

  const h = createHarness();
  const nativePorts = [];
  h.chrome.runtime.connectNative = (name) => {
    assert.equal(name, "com.michalmatu.local_agent_bridge");
    const fake = makeNativePort();
    nativePorts.push(fake);
    return fake.port;
  };

  const a = await addConversation(h, "https://chatgpt.com/c/a", h.MATRIX_BINDING, 11);
  let response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: a.id });
  assert.equal(response.ok, true, "bootstrap must still use the current delivery path");
  assert.equal(h.storage.bridgeState.conversations[a.id].bootstrapPending, false);

  response = await assistantControl(h, a.url, "70000001", "[LAB:WAIT_TASK=task-1]");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "waiting_task");
  assert.equal(h.storage.eventWakeState.watches[a.id].taskId, "task-1");
  assert.equal(h.storage.eventWakeState.watches[a.id].agentBinding, h.MATRIX_BINDING);
  assert.equal(h.alarms.has(`local-agent-chat:${a.id}`), true,
    "WAIT_TASK must retain scheduled reconciliation fallback");
  assert.equal(nativePorts.length, 1);
  assert.deepEqual(nativePorts[0].posted[0], { type: "hello", protocol_version: 1 });

  nativePorts[0].emit({
    type: "hello",
    protocol_version: 1,
    host_name: "com.michalmatu.local_agent_bridge",
    host_version: "test"
  });
  await settle();
  const event1 = taskEvent(h, "task-1", `evt-${"1".repeat(32)}`);
  nativePorts[0].emit({ type: "event", protocol_version: 1, event: event1 });
  await settle();
  assert.ok(nativePorts[0].posted.some((message) =>
    message.type === "ack" && message.event_id === event1.event_id
  ));
  assert.equal(h.storage.eventWakeState.pendingWakes[a.id].taskId, "task-1");
  assert.equal(h.storage.eventWakeState.watches[a.id], undefined);
  assert.ok(h.alarms.get(`local-agent-chat:${a.id}`).when <= Date.now() + 2500,
    "matching events must accelerate the existing alarm path");

  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: a.id });
  assert.equal(response.ok, true);
  assert.equal(response.eventWake.eventId, event1.event_id);
  assert.equal(response.eventWake.taskId, "task-1");
  const eventMessage = h.sentMessages.at(-1).message;
  assert.match(eventMessage.prompt, /\[LA_EVENT=task_result_ready\]/);
  assert.match(eventMessage.prompt, /\[LA_TASK=task-1\]/);
  assert.match(eventMessage.prompt, /Wake hint only/);
  assert.match(eventMessage.prompt, new RegExp(`\\[LA_AGENT=${h.MATRIX_BINDING}\\]`));
  assert.equal(h.storage.eventWakeState.pendingWakes[a.id], undefined,
    "pending wake is consumed only after current delivery succeeds");
  assert.equal(h.storage.eventWakeState.diagnostics.lastDeliveredEventId, event1.event_id);

  response = await assistantControl(h, a.url, "70000002", "[LAB:WAIT_TASK=task-2]");
  assert.equal(response.ok, true);
  const secondPort = nativePorts.at(-1);
  secondPort.emit({
    type: "hello",
    protocol_version: 1,
    host_name: "com.michalmatu.local_agent_bridge",
    host_version: "test"
  });
  await settle();
  const unrelated = taskEvent(h, "other-task", `evt-${"2".repeat(32)}`);
  secondPort.emit({ type: "event", protocol_version: 1, event: unrelated });
  await settle();
  assert.equal(h.storage.eventWakeState.pendingWakes[a.id], undefined,
    "unrelated task event must not route attention");
  assert.equal(h.storage.eventWakeState.watches[a.id].taskId, "task-2",
    "unrelated event must not consume exact watch");

  const b = await addConversation(h, "https://chatgpt.com/c/b", h.MATRIX_BINDING, 22);
  response = await assistantControl(h, b.url, "70000003", "[LAB:WAIT_TASK=task-2]");
  assert.equal(response.ok, false);
  assert.equal(response.reason, "task_watch_conflict");
  assert.equal(response.conflictChatId, a.id);
  assert.equal(response.fallbackScheduled, true);

  response = await assistantControl(h, a.url, "70000004", "[LAB:REBIND=tracker]");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "assistant_rebind");
  assert.equal(h.storage.eventWakeState.watches[a.id], undefined,
    "binding epoch changes must clear old task ownership");

  const transientHarness = createHarness({
    exhaustionGuardProbe() {
      return {
        ok: true,
        reason: "ready",
        guardVersion: 5,
        recoverableAssistantError: false,
        assistantGenerating: true,
        assistantTransientState: "extended_thinking",
        assistantTransientSignature: "thinking",
        assistantTransientUserIdentity: "",
        assistantTransientUserText: "",
        composerOccupied: false
      };
    }
  });
  const transientChat = await addConversation(
    transientHarness, "https://chatgpt.com/c/a", transientHarness.MATRIX_BINDING, 11
  );
  response = await assistantControl(
    transientHarness, transientChat.url, "70000005", "[LAB:WAIT_TASK=task-transient]"
  );
  assert.equal(response.ok, true);
  const transientEvent = taskEvent(
    transientHarness, "task-transient", `evt-${"3".repeat(32)}`
  );
  const accepted = await transientHarness.evaluate(
    `acceptNativeTaskEvent(${JSON.stringify(transientEvent)})`
  );
  assert.equal(accepted.reason, "event_pending");
  response = await transientHarness.sendRuntimeMessage({
    type: "bridge:run-now",
    conversationId: transientChat.id
  });
  assert.equal(response.ok, false);
  assert.equal(response.reason, "assistant_extended_thinking");
  assert.equal(transientHarness.sentMessages.length, 0,
    "event routing must not bypass current transient preflight");
  assert.equal(
    transientHarness.storage.eventWakeState.pendingWakes[transientChat.id].eventId,
    transientEvent.event_id
  );

  const restartStorage = {};
  const beforeRestart = createHarness({ storage: restartStorage });
  const restartChat = await addConversation(
    beforeRestart, "https://chatgpt.com/c/a", beforeRestart.MATRIX_BINDING, 11
  );
  response = await assistantControl(
    beforeRestart, restartChat.url, "70000006", "[LAB:WAIT_TASK=task-restart]"
  );
  assert.equal(response.ok, true);
  assert.equal(restartStorage.eventWakeState.watches[restartChat.id].taskId, "task-restart");

  const restartPorts = [];
  const afterRestart = createHarness({ storage: restartStorage });
  afterRestart.chrome.runtime.connectNative = (name) => {
    assert.equal(name, "com.michalmatu.local_agent_bridge");
    const fake = makeNativePort();
    restartPorts.push(fake);
    return fake.port;
  };
  await afterRestart.evaluate("reconcileNativeEventTransport()");
  assert.equal(restartPorts.length, 1,
    "durable exact watch must reconnect notification transport after worker restart");
  assert.deepEqual(restartPorts[0].posted[0], { type: "hello", protocol_version: 1 });
  assert.equal(restartStorage.eventWakeState.watches[restartChat.id].taskId, "task-restart");
  await afterRestart.evaluate(
    `clearTaskWatch(${JSON.stringify(restartChat.id)}).then(() => reconcileNativeEventTransport())`
  );
  assert.equal(restartPorts[0].disconnected, true,
    "test cleanup must retire the fake port without leaving reconnect timers alive");

  console.log("Chat Bridge event wake integration tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
