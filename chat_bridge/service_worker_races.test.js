"use strict";
const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");
function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}
async function add(harness) {
  const result = await harness.sendRuntimeMessage({ type: "bridge:upsert-conversation", conversation: {
    url: "https://chatgpt.com/c/a", agentBinding: harness.MATRIX_BINDING, enabled: true
  } });
  assert.equal(result.ok, true, result.error);
  return result.conversation.id;
}
const sent = { ok: true, reason: "sent", protocolVersion: 1 };

(async () => {
  // Alarm/manual overlap cannot authorize two sends or rebind an in-flight wake.
  {
    const ready = deferred(); const finish = deferred();
    const h = createHarness({ sendMessage: async ({ authorize }) => {
      assert.equal((await authorize()).ok, true);
      ready.resolve(); await finish.promise; return sent;
    } });
    const id = await add(h);
    const first = h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    await ready.promise;
    const second = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    assert.equal(second.reason, "delivery_in_progress");
    const rebind = await h.sendRuntimeMessage({ type: "bridge:rebind-conversation", conversationId: id, binding: { agentBinding: h.C6_BINDING } });
    assert.equal(rebind.ok, false);
    assert.match(rebind.error, /in-progress wake/);
    const remove = await h.sendRuntimeMessage({ type: "bridge:remove-conversation", conversationId: id });
    assert.equal(remove.ok, false);
    finish.resolve(); assert.equal((await first).ok, true);
    assert.equal(h.sentMessages.length, 1);
    assert.equal(h.storage.bridgeState.conversations[id].pendingDelivery, null);
  }

  // A pause while the content script waits invalidates authorization.
  {
    const ready = deferred(); const finish = deferred();
    const h = createHarness({ sendMessage: async ({ authorize }) => {
      ready.resolve(); await finish.promise;
      assert.equal((await authorize()).ok, false);
      return { ok: false, reason: "delivery_cancelled", protocolVersion: 1 };
    } });
    const id = await add(h);
    const first = h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    await ready.promise;
    await h.sendRuntimeMessage({ type: "bridge:update-conversation", conversationId: id, patch: { enabled: false } });
    finish.resolve(); assert.equal((await first).reason, "delivery_cancelled");
    assert.equal(h.storage.bridgeState.conversations[id].enabled, false);
    assert.equal(h.alarms.has(`local-agent-chat:${id}`), false);
  }

  // A suspended worker cannot replay a delivery whose reply was lost.
  {
    const ready = deferred(); const finish = deferred();
    const h = createHarness({ sendMessage: async ({ authorize }) => {
      await authorize(); ready.resolve(); await finish.promise;
      return { ok: false, reason: "delivery_uncertain", protocolVersion: 1 };
    } });
    const id = await add(h);
    const first = h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    await ready.promise;
    const recovered = createHarness({ storage: JSON.parse(JSON.stringify(h.storage)) });
    let response = await recovered.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    assert.equal(response.reason, "delivery_uncertain");
    assert.equal(recovered.sentMessages.length, 0);
    response = await recovered.sendRuntimeMessage({ type: "bridge:remove-conversation", conversationId: id });
    assert.equal(response.ok, false);
    response = await recovered.sendRuntimeMessage({ type: "bridge:update-conversation", conversationId: id, patch: { enabled: true } });
    assert.equal(response.ok, false);
    response = await recovered.sendRuntimeMessage({ type: "bridge:resolve-delivery", conversationId: id, wasSent: true });
    assert.equal(response.ok, true);
    assert.equal(response.conversation.enabled, false);
    assert.equal(response.conversation.bootstrapPending, false);
    assert.equal(recovered.sentMessages.length, 0);
    finish.resolve(); await first;
  }

  // An unavailable or malformed catalog never falls back to another catalog.
  {
    const h = createHarness({ console: { warn() {}, error() {} } });
    const id = await add(h);
    h.context.fetch = async () => ({ ok: true, json: async () => ({ schema_version: 3, agents: [] }) });
    h.evaluate("runtimeCache = null");
    const result = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    assert.equal(result.reason, "runtime_unavailable");
    assert.equal(h.sentMessages.length, 0);
    assert.equal(h.storage.bridgeState.conversations[id].agentBinding, h.MATRIX_BINDING);
    assert.throws(() => h.evaluate('sanitizeRuntimeAgent({repository_id:"a",repository:"Owner/A",agent_binding:"033327ab-700d-43b4-9b3b-caff1acaa2c7",execution_enabled:"false"})'), /boolean/);
    assert.throws(() => h.evaluate('validateRuntimeConfig({schema_version:2},stateModel.DEFAULT_SETTINGS)'), /schema_version=3/);
  }

  // Privileged operator actions are unavailable to conversation content scripts.
  {
    const h = createHarness(); const id = await add(h);
    for (const type of ["bridge:rebind-conversation", "bridge:save-global-settings", "bridge:remove-conversation", "bridge:run-now"]) {
      const result = await h.sendRuntimeMessage({ type, conversationId: id, binding: { agentBinding: h.C6_BINDING } }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });
      assert.equal(result.reason, "operator_ui_required");
    }
    assert.equal(h.storage.bridgeState.conversations[id].agentBinding, h.MATRIX_BINDING);
  }

  // Old messages and old binding revisions cannot stop a rebound conversation.
  {
    const h = createHarness(); const id = await add(h);
    await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    await h.sendRuntimeMessage({ type: "bridge:rebind-conversation", conversationId: id, binding: { agentBinding: h.C6_BINDING } });
    await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    for (const patch of [{ bindingRevision: 1 }, { bindingRevision: 2, assistantIdentity: "old-assistant" }]) {
      const result = await h.sendRuntimeMessage({ type: "bridge:assistant-control", conversationUrl: "https://chatgpt.com/c/a", fingerprint: "abcd1234", control: { marker: "[LAB:STOP]" }, ...patch }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });
      assert.equal(result.reason, "control_stale_binding");
      assert.equal(h.storage.bridgeState.conversations[id].enabled, true);
    }
  }

  // Racing duplicate controls change state once and retain the newest schedule.
  {
    const h = createHarness(); const id = await add(h);
    await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    const control = { type: "bridge:assistant-control", conversationUrl: "https://chatgpt.com/c/a", fingerprint: "abc12345", control: { marker: "[LAB:NEXT=30s]" } };
    const sender = { tab: { id: 11, url: control.conversationUrl } };
    const results = await Promise.all([h.sendRuntimeMessage(control, sender), h.sendRuntimeMessage(control, sender)]);
    assert.equal(results.filter((r) => r.duplicate).length, 1);
    assert.equal(h.storage.bridgeState.conversations[id].generation, 1);
    assert.ok(h.alarms.get(`local-agent-chat:${id}`).when < Date.now() + 31_000);
  }

  // Turning the master switch off clears every conversation alarm.
  {
    const h = createHarness(); await add(h);
    await h.sendRuntimeMessage({ type: "bridge:upsert-conversation", conversation: {
      url: "https://chatgpt.com/c/b", agentBinding: h.C6_BINDING, enabled: true
    } });
    assert.equal(h.alarms.size, 2);
    await h.sendRuntimeMessage({ type: "bridge:save-global-settings", settings: { masterEnabled: false } });
    assert.equal(h.alarms.size, 0);
  }

  console.log("Chat Bridge delivery, recovery, authority and scheduling race tests passed (8 scenarios).");
})().catch((error) => { console.error(error); process.exitCode = 1; });
