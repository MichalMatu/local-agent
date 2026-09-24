"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const { createHarness } = require("./worker_test_harness.js");

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
      label: `Parent ${preferredTabId}`,
      enabled: true,
      preferredTabId,
      agentBinding: binding
    }
  });
  assert.equal(response.ok, true);
  return response.conversation;
}

function childTerminalEvent(parentUrl, workflowId, suffix, overrides = {}) {
  return {
    schema_version: 1,
    event_id: `evt-${suffix.repeat(32)}`,
    event_type: "child_terminal_ready",
    emitted_at: new Date().toISOString(),
    parent_conversation_url: parentUrl,
    workflow_id: workflowId,
    workflow_node_id: `node-${suffix}`,
    child_request_id: `child-${suffix}`,
    child_request_digest: `sha256:${suffix.repeat(64)}`,
    terminal_digest: `sha256:${suffix.repeat(64)}`,
    outcome: "succeeded",
    ...overrides
  };
}

(async () => {
  assert.deepEqual(
    protocol.parseAssistantControl("[LAB:WAIT_WORKFLOW=audit-44]"),
    {
      action: "wait_workflow",
      workflowId: "audit-44",
      marker: "[LAB:WAIT_WORKFLOW=audit-44]"
    }
  );
  assert.equal(protocol.parseAssistantControl("[LAB:WAIT_WORKFLOW=bad workflow]"), null);

  const h = createHarness();
  const parent = await addConversation(h, "https://chatgpt.com/c/a", h.MATRIX_BINDING, 11);
  let response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: parent.id });
  assert.equal(response.ok, true);

  response = await assistantControl(h, parent.url, "71000001", "[LAB:WAIT_WORKFLOW=audit-44]");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "waiting_workflow");
  assert.equal(response.workflowId, "audit-44");
  assert.equal(response.subscriptionUnchanged, false);
  assert.equal(h.storage.workflowAttentionState.watches[parent.id].workflowId, "audit-44");
  assert.equal(h.storage.workflowAttentionState.watches[parent.id].conversationUrl, parent.url);
  assert.equal(h.alarms.has(`local-agent-chat:${parent.id}`), true,
    "workflow attention must retain scheduled reconciliation fallback");

  const first = childTerminalEvent(parent.url, "audit-44", "4");
  let accepted = await h.context.acceptNativeBridgeEvent(first);
  assert.equal(accepted.ok, true);
  assert.equal(accepted.reason, "workflow_event_pending");
  assert.equal(accepted.matchedChatId, parent.id);
  assert.equal(h.storage.workflowAttentionState.pendingWakes[first.event_id].workflowId, "audit-44");
  assert.equal(h.storage.workflowAttentionState.watches[parent.id].workflowId, "audit-44",
    "workflow watch must remain persistent after one child completion");

  response = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: parent.id });
  assert.equal(response.ok, true);
  assert.equal(response.eventWake.eventId, first.event_id);
  assert.equal(response.eventWake.workflowId, "audit-44");
  assert.equal(response.eventWake.childRequestId, "child-4");
  const sent = h.sentMessages.at(-1).message.prompt;
  assert.match(sent, /\[LA_EVENT=child_terminal_ready\]/);
  assert.match(sent, /\[LA_WORKFLOW=audit-44\]/);
  assert.match(sent, /\[LA_WORKFLOW_NODE=node-4\]/);
  assert.match(sent, /\[LA_CHILD_REQUEST=child-4\]/);
  assert.match(sent, /Wake hint only/);
  assert.equal(h.storage.workflowAttentionState.pendingWakes[first.event_id], undefined);
  assert.equal(h.storage.workflowAttentionState.watches[parent.id].workflowId, "audit-44");

  response = await assistantControl(h, parent.url, "71000002", "[LAB:WAIT_WORKFLOW=audit-44]");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "waiting_workflow");
  assert.equal(response.subscriptionUnchanged, true,
    "repeating the same persistent subscription must be idempotent");
  assert.equal(response.matchedRecentEvents, 0,
    "repeating WAIT_WORKFLOW must not replay already delivered recent child hints");
  assert.equal(h.storage.workflowAttentionState.pendingWakes[first.event_id], undefined);

  const second = childTerminalEvent(parent.url, "audit-44", "5");
  accepted = await h.context.acceptNativeBridgeEvent(second);
  assert.equal(accepted.reason, "workflow_event_pending",
    "the persistent workflow watch must route later child terminals too");
  assert.ok(h.storage.workflowAttentionState.pendingWakes[second.event_id]);

  const wrongWorkflow = childTerminalEvent(parent.url, "other-workflow", "6");
  accepted = await h.context.acceptNativeBridgeEvent(wrongWorkflow);
  assert.equal(accepted.reason, "workflow_event_cached");
  assert.equal(h.storage.workflowAttentionState.pendingWakes[wrongWorkflow.event_id], undefined);

  const wrongParent = childTerminalEvent("https://chatgpt.com/c/b", "audit-44", "7");
  accepted = await h.context.acceptNativeBridgeEvent(wrongParent);
  assert.equal(accepted.reason, "workflow_event_cached");
  assert.equal(h.storage.workflowAttentionState.pendingWakes[wrongParent.event_id], undefined,
    "workflow id alone must never route cross-conversation attention");

  response = await assistantControl(h, parent.url, "71000003", "[LAB:REBIND=tracker]");
  assert.equal(response.ok, true);
  assert.equal(h.storage.workflowAttentionState.watches[parent.id], undefined,
    "binding epoch change must invalidate parent workflow ownership");
  assert.equal(
    Object.values(h.storage.workflowAttentionState.pendingWakes).some(
      (pending) => pending.conversationId === parent.id
    ),
    false
  );

  const restartStorage = {};
  const beforeRestart = createHarness({ storage: restartStorage });
  const restartParent = await addConversation(
    beforeRestart, "https://chatgpt.com/c/a", beforeRestart.MATRIX_BINDING, 11
  );
  response = await assistantControl(
    beforeRestart,
    restartParent.url,
    "71000004",
    "[LAB:WAIT_WORKFLOW=restart-workflow]"
  );
  assert.equal(response.ok, true);
  const afterRestart = createHarness({ storage: restartStorage });
  const restored = await afterRestart.context.loadWorkflowAttentionState();
  assert.equal(restored.watches[restartParent.id].workflowId, "restart-workflow",
    "workflow watch must survive service-worker restart");

  console.log("Chat Bridge workflow attention integration tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
