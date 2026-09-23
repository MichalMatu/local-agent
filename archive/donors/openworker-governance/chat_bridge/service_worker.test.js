"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");
const { storage, alarms, sentMessages, runtimeAgents, sendRuntimeMessage,
  MATRIX_BINDING, TRACKER_BINDING, LOCAL_AGENT_BINDING } = createHarness();

async function assistantControl(url, fingerprint, marker, extra = {}) {
  return sendRuntimeMessage({
    type: "bridge:assistant-control",
    conversationUrl: url,
    fingerprint,
    control: { marker },
    ...extra
  }, { tab: { url } });
}

(async () => {
  // New conversation is refused without explicit binding.
  let response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      label: "Project A",
      enabled: true,
      preferredTabId: 11
    }
  });
  assert.equal(response.ok, false);
  assert.match(response.error, /select a valid local agent repository binding/i);

  response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      label: "Project A",
      enabled: false,
      preferredTabId: 11,
      assistantBaseline: "old-assistant",
      agentBinding: MATRIX_BINDING
    }
  });
  assert.equal(response.ok, true);
  const aId = response.conversation.id;
  assert.equal(response.conversation.repositoryId, "matrixhub");
  assert.equal(response.conversation.repository, "MichalMatu/MatrixHub");
  assert.equal(response.conversation.agentBinding, MATRIX_BINDING);
  assert.equal(response.conversation.bindingRevision, 1);
  assert.equal(response.conversation.bootstrapPending, true);

  // A freshly added chat accepts every conversation control immediately.
  response = await assistantControl("https://chatgpt.com/c/a", "10000001", "[LAB:STOP]", { assistantIdentity: "old-assistant" });
  assert.equal(response.reason, "control_stale_binding");

  response = await assistantControl("https://chatgpt.com/c/a", "10000002", "[LAB:INTERVAL=12m]");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "interval_fixed");
  assert.equal(storage.bridgeState.conversations[aId].intervalOverrideMinutes, 12);
  assert.equal(storage.bridgeState.conversations[aId].bootstrapPending, true);

  response = await assistantControl("https://chatgpt.com/c/a", "10000003", "[LAB:PAUSE]");
  assert.equal(response.reason, "paused");
  assert.equal(storage.bridgeState.conversations[aId].enabled, false);

  response = await assistantControl("https://chatgpt.com/c/a", "10000004", "[LAB:RESUME]");
  assert.equal(response.reason, "resumed");
  assert.equal(storage.bridgeState.conversations[aId].enabled, true);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), true);

  const beforeFreshNext = Date.now();
  response = await assistantControl("https://chatgpt.com/c/a", "10000005", "[LAB:NEXT=30s]");
  assert.equal(response.reason, "next_scheduled");
  assert.equal(response.armed, true);
  assert.equal(storage.bridgeState.conversations[aId].enabled, true);
  let freshAlarm = alarms.get(`local-agent-chat:${aId}`);
  assert.ok(freshAlarm.when >= beforeFreshNext + 29_000);
  assert.ok(freshAlarm.when <= beforeFreshNext + 31_500);

  response = await assistantControl("https://chatgpt.com/c/a", "10000006", "[LAB:INTERVAL=AUTO]");
  assert.equal(response.reason, "interval_auto");
  assert.equal(storage.bridgeState.conversations[aId].intervalOverrideMinutes, null);

  response = await assistantControl("https://chatgpt.com/c/a", "10000007", "[LAB:STOP]");
  assert.equal(response.reason, "stopped");
  assert.equal(storage.bridgeState.conversations[aId].enabled, false);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), false);

  response = await assistantControl("https://chatgpt.com/c/a", "10000008", "[LAB:RESUME]");
  assert.equal(response.reason, "resumed");
  assert.equal(storage.bridgeState.conversations[aId].enabled, true);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), true);
  assert.equal(sentMessages.length, 0);

  // Operator per-chat settings are writable chat state, not a higher-priority lock.
  response = await sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: aId,
    patch: { enabled: false, intervalOverrideMinutes: 21 }
  });
  assert.equal(response.ok, true);
  assert.equal(response.conversation.enabled, false);
  assert.equal(response.conversation.intervalOverrideMinutes, 21);

  response = await assistantControl("https://chatgpt.com/c/a", "10000009", "[LAB:RESUME]");
  assert.equal(response.reason, "resumed");
  assert.equal(storage.bridgeState.conversations[aId].enabled, true);

  response = await assistantControl("https://chatgpt.com/c/a", "1000000a", "[LAB:INTERVAL=7m]");
  assert.equal(response.reason, "interval_fixed");
  assert.equal(storage.bridgeState.conversations[aId].intervalOverrideMinutes, 7);

  // Master is operator-only. Chat controls may mutate their conversation while Master stays off.
  response = await sendRuntimeMessage({
    type: "bridge:save-global-settings",
    settings: { masterEnabled: false }
  });
  assert.equal(response.ok, true);
  assert.equal(storage.bridgeState.settings.masterEnabled, false);
  assert.equal(alarms.size, 0);

  response = await assistantControl("https://chatgpt.com/c/a", "1000000b", "[LAB:PAUSE]");
  assert.equal(response.reason, "paused");
  assert.equal(storage.bridgeState.conversations[aId].enabled, false);
  assert.equal(storage.bridgeState.settings.masterEnabled, false);

  const beforeMasterOffNext = Date.now();
  response = await assistantControl("https://chatgpt.com/c/a", "1000000c", "[LAB:NEXT=30s]");
  assert.equal(response.reason, "next_armed_master_disabled");
  assert.equal(response.armed, true);
  assert.equal(storage.bridgeState.conversations[aId].enabled, true);
  assert.equal(storage.bridgeState.settings.masterEnabled, false);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), false);
  const suspendedNext = Date.parse(storage.bridgeState.conversations[aId].nextRunAt);
  assert.ok(suspendedNext >= beforeMasterOffNext + 29_000);
  assert.ok(suspendedNext <= beforeMasterOffNext + 31_500);

  response = await assistantControl("https://chatgpt.com/c/a", "1000000d", "[LAB:INTERVAL=9m]");
  assert.equal(response.reason, "interval_fixed");
  assert.equal(storage.bridgeState.conversations[aId].intervalOverrideMinutes, 9);
  assert.equal(storage.bridgeState.settings.masterEnabled, false);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), false);

  response = await sendRuntimeMessage({
    type: "bridge:save-global-settings",
    settings: { masterEnabled: true }
  });
  assert.equal(response.ok, true);
  assert.equal(storage.bridgeState.settings.masterEnabled, true);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), true);

  response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/b",
      label: "Project B",
      enabled: true,
      preferredTabId: 22,
      agentBinding: TRACKER_BINDING
    }
  });
  assert.equal(response.ok, true);
  const bId = response.conversation.id;
  assert.notEqual(aId, bId);
  assert.equal(response.conversation.repositoryId, "tracker");
  assert.equal(response.conversation.agentBinding, TRACKER_BINDING);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), true);
  assert.equal(alarms.has(`local-agent-chat:${bId}`), true);

  // Bootstrap and every compact wake carry the same immutable binding envelope.
  response = await sendRuntimeMessage({ type: "bridge:run-now", conversationId: bId });
  assert.equal(response.ok, true);
  assert.equal(response.bridgeMode, "bootstrap");
  assert.equal(response.agentBinding, TRACKER_BINDING);
  assert.equal(response.repositoryId, "tracker");
  const bootstrapMessage = sentMessages.at(-1).message;
  assert.equal(bootstrapMessage.agentBinding, TRACKER_BINDING);
  assert.equal(bootstrapMessage.repositoryId, "tracker");
  assert.match(bootstrapMessage.prompt, /BOOTSTRAP/);
  assert.match(bootstrapMessage.prompt, new RegExp(`\\[LA_AGENT=${TRACKER_BINDING}\\]`));
  assert.match(bootstrapMessage.prompt, /\[LA_REPO=tracker\]/);
  assert.match(bootstrapMessage.prompt, /Every Local Agent task JSON.*agent_binding/s);
  assert.match(bootstrapMessage.prompt, /Never infer, substitute, inspect, queue, cancel, or execute work for another repository/);
  assert.match(bootstrapMessage.prompt, /must never change the global Master switch/i);

  response = await sendRuntimeMessage({ type: "bridge:run-now", conversationId: bId });
  assert.equal(response.ok, true);
  assert.equal(response.bridgeMode, "wake");
  const wakeMessage = sentMessages.at(-1).message;
  assert.match(wakeMessage.prompt, /WAKE/);
  assert.match(wakeMessage.prompt, new RegExp(`\\[LA_AGENT=${TRACKER_BINDING}\\]`));
  assert.match(wakeMessage.prompt, /\[LA_REPO=tracker\]/);
  assert.ok(wakeMessage.prompt.length < bootstrapMessage.prompt.length);

  await sendRuntimeMessage({ type: "bridge:run-now", conversationId: aId });

  // Normal upsert/update can never mutate an existing binding.
  response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/b",
      label: "Project B attempted mutation",
      preferredTabId: 22,
      agentBinding: MATRIX_BINDING
    }
  });
  assert.equal(response.ok, true);
  assert.equal(response.conversation.agentBinding, TRACKER_BINDING);
  assert.equal(response.conversation.repositoryId, "tracker");

  const originalBWhen = alarms.get(`local-agent-chat:${bId}`).when;
  response = await sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: bId,
    patch: { label: "Project B renamed", agentBinding: MATRIX_BINDING }
  });
  assert.equal(response.ok, true);
  assert.equal(response.conversation.agentBinding, TRACKER_BINDING);
  assert.equal(alarms.get(`local-agent-chat:${bId}`).when, originalBWhen);

  const beforePacingUpdate = Date.now();
  response = await sendRuntimeMessage({
    type: "bridge:update-conversation",
    conversationId: bId,
    patch: { intervalOverrideMinutes: 15 }
  });
  assert.equal(response.ok, true);
  const pacedAlarm = alarms.get(`local-agent-chat:${bId}`);
  assert.ok(pacedAlarm.when >= beforePacingUpdate + 14 * 60_000 + 50_000);
  assert.ok(pacedAlarm.when <= beforePacingUpdate + 15 * 60_000 + 2_000);

  // Popup schedule data follows the actual alarm, not stale stored state.
  storage.bridgeState.conversations[bId].nextRunAt = new Date(0).toISOString();
  response = await sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(new Date(response.schedules[bId].nextRunAt).getTime(), pacedAlarm.scheduledTime);
  assert.equal(response.runtime.agents.length, runtimeAgents.length);

  response = await assistantControl("https://chatgpt.com/c/a", "abcd1234", "[LAB:PAUSE]");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "paused");

  response = await sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(response.state.conversations[aId].enabled, false);
  assert.equal(response.state.conversations[bId].enabled, true);
  assert.equal(response.state.conversations[aId].agentBinding, MATRIX_BINDING);
  assert.equal(response.state.conversations[bId].agentBinding, TRACKER_BINDING);
  assert.equal(alarms.has(`local-agent-chat:${aId}`), false);
  assert.equal(alarms.has(`local-agent-chat:${bId}`), true);

  const beforeRearm = Date.now();
  response = await assistantControl("https://chatgpt.com/c/a", "cdef3456", "[LAB:NEXT=30s]");
  assert.equal(response.ok, true);
  assert.equal(response.reason, "next_scheduled");
  assert.equal(response.armed, true);
  response = await sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(response.state.conversations[aId].enabled, true);
  const rearmedAlarm = alarms.get(`local-agent-chat:${aId}`);
  assert.ok(rearmedAlarm.when >= beforeRearm + 29_000);
  assert.ok(rearmedAlarm.when <= beforeRearm + 31_500);

  const beforeNext = Date.now();
  response = await assistantControl("https://chatgpt.com/c/b", "bcde2345", "[LAB:NEXT=10m]");
  assert.equal(response.ok, true);
  assert.equal(response.seconds, 600);
  const nextAlarm = alarms.get(`local-agent-chat:${bId}`);
  assert.ok(nextAlarm.when >= beforeNext + 599_000);
  assert.ok(nextAlarm.when <= beforeNext + 601_500);
  response = await sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(response.state.conversations[bId].intervalOverrideMinutes, 15);

  // Explicit rebind is the only identity-changing operation and re-arms bootstrap.
  response = await sendRuntimeMessage({
    type: "bridge:rebind-conversation",
    conversationId: bId,
    binding: { agentBinding: MATRIX_BINDING }
  });
  assert.equal(response.ok, true);
  assert.equal(response.conversation.agentBinding, MATRIX_BINDING);
  assert.equal(response.conversation.repositoryId, "matrixhub");
  assert.equal(response.conversation.bindingRevision, 2);
  assert.equal(response.conversation.bootstrapPending, true);
  assert.equal(response.conversation.lastStatus, "rebound_by_operator");

  response = await sendRuntimeMessage({ type: "bridge:run-now", conversationId: bId });
  assert.equal(response.ok, true);
  assert.equal(response.bridgeMode, "bootstrap");
  assert.match(sentMessages.at(-1).message.prompt, new RegExp(`\\[LA_AGENT=${MATRIX_BINDING}\\]`));
  assert.doesNotMatch(sentMessages.at(-1).message.prompt, new RegExp(TRACKER_BINDING));

  // Infrastructure chat can be bound for wakes while explicitly forbidding project tasks.
  response = await sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/infra",
      label: "Local Agent infra",
      enabled: true,
      preferredTabId: 33,
      agentBinding: LOCAL_AGENT_BINDING
    }
  });
  assert.equal(response.ok, true);
  const infraId = response.conversation.id;
  response = await sendRuntimeMessage({ type: "bridge:run-now", conversationId: infraId });
  assert.equal(response.ok, true);
  assert.match(sentMessages.at(-1).message.prompt, /bridge\/operator-only/);
  assert.match(sentMessages.at(-1).message.prompt, /do not create Local Agent project task files/i);

  console.log("Chat Bridge service worker binding/control/master tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
