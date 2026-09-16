"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const { createHarness } = require("./worker_test_harness.js");

function fakePort() {
  const messageListeners = [];
  const disconnectListeners = [];
  return {
    sent: [],
    disconnected: false,
    onMessage: { addListener(listener) { messageListeners.push(listener); } },
    onDisconnect: { addListener(listener) { disconnectListeners.push(listener); } },
    postMessage(message) { this.sent.push(message); },
    disconnect() {
      if (this.disconnected) return;
      this.disconnected = true;
      for (const listener of disconnectListeners) listener();
    },
    emitMessage(message) {
      for (const listener of messageListeners) listener(message);
    }
  };
}

async function nextTurn() {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await new Promise((resolve) => setTimeout(resolve, 0));
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
    fingerprint: protocol.controlFingerprint(conversation.url, marker, { marker }, `assistant-${taskId}`)
  }, {
    id: harness.chrome.runtime.id,
    frameId: 0,
    url: conversation.url,
    tab: { id: 11, url: conversation.url }
  });
}

function nativeEvent(harness, taskId) {
  return {
    schema_version: 1,
    event_id: `evt-${"d".repeat(32)}`,
    event_type: "task_result_ready",
    emitted_at: new Date().toISOString(),
    repository_id: "matrixhub",
    repository: "MichalMatu/MatrixHub",
    agent_binding: harness.MATRIX_BINDING,
    task_id: taskId,
    task_digest: `digest-${taskId}`,
    result_status: "done"
  };
}

(async () => {
  // Protocol mismatch is a visible fail-closed state, not a silent idle disconnect.
  {
    const ports = [];
    const harness = createHarness({
      connectNative: (hostName) => {
        assert.equal(hostName, "com.michalmatu.local_agent_bridge");
        const port = fakePort();
        ports.push(port);
        return port;
      }
    });
    const conversation = await addChat(harness);
    const waiting = await waitTask(harness, conversation, "native-mismatch-1");
    assert.equal(waiting.ok, true);
    assert.equal(ports.length, 1);
    assert.equal(ports[0].sent[0].type, "hello");
    assert.equal(ports[0].sent[0].protocol_version, 1);

    ports[0].emitMessage({
      type: "hello",
      protocol_version: 999,
      host_name: "com.michalmatu.local_agent_bridge"
    });
    await nextTurn();

    assert.equal(ports[0].disconnected, true);
    assert.equal(harness.storage.eventWakeState.diagnostics.nativeState, "incompatible");
    assert.equal(harness.storage.eventWakeState.diagnostics.lastError, "native_protocol_mismatch");
    assert.equal(harness.evaluate("nativeTransport.port"), null);
    assert.equal(harness.evaluate("nativeTransport.reconnectTimer"), null,
      "protocol mismatch must not enter an automatic reconnect loop");
  }

  // A valid handshake and event persists routing state before ACK and schedules the owner.
  {
    const ports = [];
    const harness = createHarness({
      connectNative: () => {
        const port = fakePort();
        ports.push(port);
        return port;
      }
    });
    const conversation = await addChat(harness);
    const waiting = await waitTask(harness, conversation, "native-delivery-1");
    assert.equal(waiting.ok, true);
    const port = ports[0];

    port.emitMessage({
      type: "hello",
      protocol_version: 1,
      host_name: "com.michalmatu.local_agent_bridge",
      host_version: "test"
    });
    await nextTurn();
    assert.equal(harness.storage.eventWakeState.diagnostics.nativeState, "connected");

    const event = nativeEvent(harness, "native-delivery-1");
    port.emitMessage({ type: "event", protocol_version: 1, event });
    await nextTurn();

    assert.equal(
      harness.storage.eventWakeState.pendingWakes[conversation.id].eventId,
      event.event_id,
      "event must be durable in Bridge state before the host handoff is acknowledged"
    );
    assert.ok(harness.alarms.has(`local-agent-chat:${conversation.id}`));
    const ack = port.sent.find((message) => message.type === "ack");
    assert.ok(ack);
    assert.equal(ack.protocol_version, 1);
    assert.equal(ack.event_id, event.event_id);
  }

  console.log("Chat Bridge native transport state-machine tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
