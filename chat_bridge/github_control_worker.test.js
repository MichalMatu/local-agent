"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const runtimeExample = require("./runtime.example.json");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const matrix = runtimeExample.agents.find((agent) => agent.repository_id === "matrixhub");
  assert.ok(matrix);
  const url = "https://chatgpt.com/c/a";
  const chatId = protocol.conversationId(url);
  let control = {
    conversation_id: chatId,
    repository_id: matrix.repository_id,
    repository: matrix.repository,
    agent_binding: matrix.agent_binding,
    binding_revision: 1,
    control_generation: 1,
    enabled: false,
    interval_minutes: 5,
    next_wake_at: null,
    updated_at: "2026-09-30T00:40:00+02:00"
  };

  const h = createHarness({
    fetch: async () => ({
      ok: true,
      async json() {
        return {
          ...runtimeExample,
          bootstrap_prompt: "BOOTSTRAP",
          wake_prompt: "WAKE",
          conversation_controls: [control]
        };
      }
    })
  });

  let response = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url,
      label: "Project A",
      enabled: true,
      preferredTabId: 11,
      agentBinding: matrix.agent_binding
    }
  });
  assert.equal(response.ok, true);
  assert.equal(response.conversation.id, chatId);
  assert.equal(h.alarms.has("local-agent-chat-github-control"), false);

  // Chrome install/startup lifecycle creates the durable remote-control discovery poll.
  await h.installed();
  assert.equal(h.alarms.has("local-agent-chat-github-control"), true);
  let conversation = h.storage.bridgeState.conversations[chatId];
  assert.equal(conversation.enabled, false);
  assert.equal(conversation.intervalOverrideMinutes, 5);
  assert.equal(conversation.lastControlAction, "github:1");
  assert.equal(conversation.lastStatus, "github_control_paused");
  assert.equal(h.alarms.has(`local-agent-chat:${chatId}`), false);
  assert.equal(h.storage.bridgeGithubControlApplied[chatId].generation, 1);

  const targetMs = Date.now() + 120_000;
  control = {
    ...control,
    control_generation: 2,
    enabled: true,
    interval_minutes: 7,
    next_wake_at: new Date(targetMs).toISOString(),
    updated_at: new Date().toISOString()
  };
  h.evaluate("runtimeCache = null");
  let reconcile = await h.evaluate("reconcileGithubConversationControls()");
  assert.equal(reconcile.applied.length, 1);
  assert.equal(reconcile.applied[0].repaired, false);
  conversation = h.storage.bridgeState.conversations[chatId];
  assert.equal(conversation.enabled, true);
  assert.equal(conversation.intervalOverrideMinutes, 7);
  assert.equal(conversation.lastControlAction, "github:2");
  const scheduled = h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime;
  assert.ok(Number.isFinite(scheduled));
  assert.ok(Math.abs(scheduled - targetMs) < 2000, JSON.stringify({ scheduled, targetMs }));

  const stableGeneration = conversation.generation;
  const stableScheduled = scheduled;
  reconcile = await h.evaluate("reconcileGithubConversationControls()");
  assert.equal(reconcile.applied.length, 0);
  assert.equal(h.storage.bridgeState.conversations[chatId].generation, stableGeneration);
  assert.equal(h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime, stableScheduled);

  // GitHub remains authoritative even if a legacy DOM command or popup mutates local state.
  h.storage.bridgeState.conversations[chatId].enabled = false;
  h.storage.bridgeState.conversations[chatId].intervalOverrideMinutes = 3;
  h.storage.bridgeState.conversations[chatId].nextRunAt = null;
  h.alarms.delete(`local-agent-chat:${chatId}`);
  reconcile = await h.evaluate("reconcileGithubConversationControls()");
  assert.equal(reconcile.applied.length, 1);
  assert.equal(reconcile.applied[0].repaired, true);
  conversation = h.storage.bridgeState.conversations[chatId];
  assert.equal(conversation.enabled, true);
  assert.equal(conversation.intervalOverrideMinutes, 7);
  assert.equal(conversation.lastStatus, "github_control_reconciled");
  assert.equal(h.storage.bridgeGithubControlApplied[chatId].generation, 2);
  const repairedScheduled = h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime;
  assert.ok(Number.isFinite(repairedScheduled));
  assert.ok(repairedScheduled > Date.now());

  control = {
    ...control,
    control_generation: 3,
    binding_revision: 2,
    enabled: false,
    next_wake_at: null,
    updated_at: new Date().toISOString()
  };
  h.evaluate("runtimeCache = null");
  reconcile = await h.evaluate("reconcileGithubConversationControls()");
  assert.equal(reconcile.applied.length, 0);
  assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);
  assert.equal(h.storage.bridgeGithubControlApplied[chatId].generation, 2);

  console.log("GitHub Bridge control worker tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
