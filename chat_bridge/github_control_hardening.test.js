"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
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

async function addConversation(h, enabled = true) {
  const result = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url,
      label: "Project A",
      enabled,
      preferredTabId: 11,
      agentBinding: matrix.agent_binding
    }
  });
  assert.equal(result.ok, true, result.error);
  return result.conversation;
}

(async () => {
  // Concurrent reconciliation of one remote generation is serialized and applies once.
  {
    let control = null;
    const h = harnessWithControl(() => control);
    await h.installed();
    await addConversation(h);
    control = controlRecord({ enabled: false, updated_at: new Date().toISOString() });

    const [left, right] = await Promise.all([
      h.evaluate("reconcileGithubConversationControls()"),
      h.evaluate("reconcileGithubConversationControls()")
    ]);
    const conversation = h.storage.bridgeState.conversations[chatId];
    assert.equal(conversation.generation, 1);
    assert.equal(conversation.enabled, false);
    assert.equal(left.applied.length + right.applied.length, 1);
    assert.equal(h.storage.bridgeGithubControlApplied[chatId].generation, 1);
    assert.equal(h.storage.bridgeGithubControlApplied[chatId].localGeneration, 1);
    assert.ok(h.storage.bridgeGithubControlApplied[chatId].controlSignature);
  }

  // A control-boundary reconcile bypasses the 30-second runtime cache.
  {
    let control = controlRecord();
    const h = harnessWithControl(() => control);
    await addConversation(h);
    await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);

    control = controlRecord({
      control_generation: 2,
      enabled: false,
      updated_at: new Date(Date.now() + 1000).toISOString()
    });
    const reconcile = await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(reconcile.applied.length, 1);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);
    assert.equal(h.storage.bridgeGithubControlApplied[chatId].generation, 2);
  }

  // A remote rewrite under the same generation is rejected instead of masquerading as local drift.
  {
    let control = controlRecord({ updated_at: new Date().toISOString() });
    const h = harnessWithControl(() => control);
    await addConversation(h);
    await h.evaluate("reconcileGithubConversationControls()");
    const generation = h.storage.bridgeState.conversations[chatId].generation;

    control = controlRecord({
      enabled: false,
      updated_at: new Date(Date.now() + 1000).toISOString()
    });
    const conflict = await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(conflict.applied.length, 0);
    assert.equal(conflict.conflicts.length, 1);
    assert.equal(conflict.conflicts[0].reason, "same_generation_rewritten");
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);
    assert.equal(h.storage.bridgeState.conversations[chatId].generation, generation);

    const popupState = await h.sendRuntimeMessage({ type: "bridge:get-state" });
    assert.equal(popupState.githubOwnership[chatId].source, "cached");
    assert.equal(popupState.githubOwnership[chatId].controlGeneration, 1);
    assert.equal(popupState.runtime.conversationControls.length, 0);
  }

  // A lower remote generation cannot replace the applied desired state or popup ownership.
  {
    let control = controlRecord({
      control_generation: 2,
      enabled: false,
      updated_at: new Date().toISOString()
    });
    const h = harnessWithControl(() => control);
    await addConversation(h);
    await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);

    control = controlRecord({
      control_generation: 1,
      enabled: true,
      updated_at: new Date(Date.now() + 1000).toISOString()
    });
    const rollback = await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(rollback.applied.length, 0);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);
    const popupState = await h.sendRuntimeMessage({ type: "bridge:get-state" });
    assert.equal(popupState.githubOwnership[chatId].source, "cached");
    assert.equal(popupState.githubOwnership[chatId].controlGeneration, 2);
    assert.equal(popupState.runtime.conversationControls.length, 0);
  }

  // A cold profile never converts an already-expired one-shot into an immediate wake.
  {
    const now = Date.now();
    const control = controlRecord({
      interval_minutes: 7,
      next_wake_at: new Date(now - 60_000).toISOString(),
      updated_at: new Date(now - 120_000).toISOString()
    });
    const h = harnessWithControl(() => control);
    await addConversation(h);
    await h.evaluate("reconcileGithubConversationControls()");
    const alarm = h.alarms.get(`local-agent-chat:${chatId}`);
    assert.ok(alarm?.scheduledTime > Date.now() + 6 * 60_000, JSON.stringify(alarm));
    assert.ok(alarm?.scheduledTime < Date.now() + 8 * 60_000, JSON.stringify(alarm));
  }

  // Once GitHub ownership has been applied, a missing remote record remains fail-closed.
  // Explicit Remove clears that durable ownership before the same URL is added again.
  {
    let control = controlRecord();
    const h = harnessWithControl(() => control);
    await addConversation(h);
    await h.evaluate("reconcileGithubConversationControls()");
    const generation = h.storage.bridgeState.conversations[chatId].generation;

    control = null;
    const popupState = await h.sendRuntimeMessage({ type: "bridge:get-state" });
    assert.equal(popupState.githubOwnership[chatId].managed, true);
    assert.equal(popupState.githubOwnership[chatId].source, "cached");

    const localMutation = await h.sendRuntimeMessage({
      type: "bridge:update-conversation",
      conversationId: chatId,
      patch: { enabled: false }
    });
    assert.equal(localMutation.ok, false);
    assert.match(localMutation.error, /managed by GitHub desired state/);
    assert.equal(h.storage.bridgeState.conversations[chatId].generation, generation);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);

    let response = await h.sendRuntimeMessage({
      type: "bridge:assistant-control",
      conversationUrl: url,
      fingerprint: "abc00011",
      control: { marker: "[LAB:PAUSE]" }
    }, { tab: { id: 11, url } });
    assert.equal(response.ok, true);
    assert.equal(response.reason, "github_control_managed");
    assert.equal(response.authoritySource, "cached");
    assert.equal(h.storage.bridgeState.conversations[chatId].generation, generation);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);

    response = await h.sendRuntimeMessage({
      type: "bridge:assistant-control",
      conversationUrl: url,
      fingerprint: "abc00012",
      control: { marker: "[LAB:STATUS]" }
    }, { tab: { id: 11, url } });
    assert.equal(response.ok, true);
    assert.equal(response.reason, "github_control_managed");
    assert.equal(response.feedbackPrompt, undefined);

    const removed = await h.sendRuntimeMessage({
      type: "bridge:remove-conversation",
      conversationId: chatId
    });
    assert.equal(removed.ok, true);
    assert.equal(h.storage.bridgeGithubControlApplied?.[chatId], undefined);

    await addConversation(h, true);
    const unmanagedMutation = await h.sendRuntimeMessage({
      type: "bridge:update-conversation",
      conversationId: chatId,
      patch: { enabled: false }
    });
    assert.equal(unmanagedMutation.ok, true, unmanagedMutation.error);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);
  }

  // Master remains an independent local gate for a GitHub-managed enabled conversation.
  {
    const target = Date.now() + 5 * 60_000;
    const control = controlRecord({ next_wake_at: new Date(target).toISOString() });
    const h = harnessWithControl(() => control);
    await addConversation(h);
    await h.sendRuntimeMessage({
      type: "bridge:save-global-settings",
      settings: { masterEnabled: false }
    });
    await h.evaluate("reconcileGithubConversationControls()");
    assert.equal(h.storage.bridgeState.settings.masterEnabled, false);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);
    assert.equal(h.alarms.has(`local-agent-chat:${chatId}`), false);

    await h.sendRuntimeMessage({
      type: "bridge:save-global-settings",
      settings: { masterEnabled: true }
    });
    assert.equal(h.storage.bridgeState.settings.masterEnabled, true);
    assert.equal(h.alarms.has(`local-agent-chat:${chatId}`), true);
  }

  const popup = fs.readFileSync(path.join(__dirname, "popup.js"), "utf8");
  assert.match(popup, /function managedControlForConversation/);
  assert.match(popup, /enabled\.disabled = githubManaged/);
  assert.match(popup, /intervalInput\.disabled = githubManaged/);
  assert.match(popup, /githubOwnership\[conversation\.id\]/);
  assert.match(popup, /GitHub managed/);

  console.log("GitHub Bridge reconciliation, cache, ownership and popup hardening tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
