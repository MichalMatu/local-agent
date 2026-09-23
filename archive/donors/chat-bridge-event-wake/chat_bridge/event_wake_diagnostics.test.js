"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const { createHarness } = require("./worker_test_harness.js");

function fingerprint(value) {
  return protocol.fnv1a32(value);
}

async function assistantControl(harness, conversation, marker, seed) {
  return harness.sendRuntimeMessage({
    type: "bridge:assistant-control",
    conversationUrl: conversation.url,
    fingerprint: fingerprint(seed),
    assistantIdentity: `assistant-${seed}`,
    contentProtocolVersion: protocol.CONTENT_PROTOCOL_VERSION,
    control: { marker }
  }, { tab: { id: conversation.preferredTabId || 11, url: conversation.url } });
}

(async () => {
  const h = createHarness();
  const added = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      repositoryId: "matrixhub",
      enabled: true,
      preferredTabId: 11,
      assistantBaseline: ""
    }
  });
  assert.equal(added.ok, true);

  let response = await assistantControl(h, added.conversation, "[LAB:CAPABILITIES]", "caps-idle");
  assert.equal(response.ok, true);
  assert.match(response.feedbackPrompt, /"taskResultEventWake": true/);
  assert.match(response.feedbackPrompt, /"nativeMessagingOnDemand": true/);
  assert.match(response.feedbackPrompt, /"alarmFallbackWhileWaiting": true/);
  assert.match(response.feedbackPrompt, /"mode": "native_messaging_on_demand_with_alarm_fallback"/);
  assert.match(response.feedbackPrompt, /"currentWatch": null/);

  response = await assistantControl(h, added.conversation, "[LAB:WAIT_TASK=diag-1]", "wait-diag");
  assert.equal(response.ok, true);

  response = await assistantControl(h, added.conversation, "[LAB:DEBUG]", "debug-diag");
  assert.equal(response.ok, true);
  assert.match(response.feedbackPrompt, /"taskId": "diag-1"/);
  assert.match(response.feedbackPrompt, /"repositoryId": "matrixhub"/);
  assert.match(response.feedbackPrompt, /"state": "unsupported"/);

  console.log("Chat Bridge event wake diagnostic tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
