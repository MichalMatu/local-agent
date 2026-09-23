"use strict";

const assert = require("node:assert/strict");
const stateModel = require("./bridge_state.js");
const catalog = require("../config/agent_bindings.json").agents;
const runtimeAgents = require("./runtime.example.json").agents;
assert.equal(new Set(catalog.map((agent) => agent.id)).size, catalog.length);
assert.deepEqual(runtimeAgents, catalog.map(({ id, ...agent }) => ({ repository_id: id, ...agent })));

const MATRIX_BINDING = "033327ab-700d-43b4-9b3b-caff1acaa2c7";
const TRACKER_BINDING = "be481b25-9d97-4205-b93f-95f5c5827441";

// v2 conversations migrate fail-closed: no binding means no wake/admission.
const migratedV2 = stateModel.migrateLegacyStorage({
  bridgeState: {
    schemaVersion: 2,
    settings: {},
    conversations: {
      old: {
        url: "https://chatgpt.com/c/old",
        label: "Old unbound chat",
        enabled: true,
        bootstrapPending: false,
        lastStatus: "sent"
      }
    }
  }
});
assert.equal(migratedV2.migrated, true);
const old = Object.values(migratedV2.state.conversations)[0];
assert.equal(old.enabled, false);
assert.equal(old.bootstrapPending, true);
assert.equal(old.lastStatus, "binding_required");
assert.equal(old.agentBinding, null);
assert.equal(stateModel.isBoundConversation(old), false);

const migratedLegacy = stateModel.migrateLegacyStorage({
  enabled: true,
  conversationUrl: "https://chat.openai.com/c/legacy?x=1",
  fallbackIntervalMinutes: 7,
  fallbackBusyRetryMinutes: 2,
  fallbackPrompt: "legacy bootstrap",
  intervalOverrideMinutes: 12,
  lastStatus: "sent",
  lastControlFingerprint: "abcd1234"
});
assert.equal(migratedLegacy.migrated, true);
assert.equal(migratedLegacy.state.settings.fallbackIntervalMinutes, 7);
const legacy = Object.values(migratedLegacy.state.conversations)[0];
assert.equal(legacy.url, "https://chatgpt.com/c/legacy");
assert.equal(legacy.enabled, false);
assert.equal(legacy.bootstrapPending, true);
assert.equal(legacy.intervalOverrideMinutes, 12);
assert.equal(legacy.lastControlFingerprint, "abcd1234");
assert.equal(legacy.lastStatus, "binding_required");

// Old delivery uncertainty state is erased during schema-3 normalization.
const migratedDeliveryState = stateModel.migrateLegacyStorage({
  bridgeState: {
    schemaVersion: 3,
    settings: {},
    conversations: {
      oldDelivery: {
        url: "https://chatgpt.com/c/delivery",
        label: "Delivery legacy",
        enabled: false,
        repositoryId: "matrixhub",
        repository: "MichalMatu/MatrixHub",
        agentBinding: MATRIX_BINDING,
        bindingRevision: 1,
        pendingDelivery: { id: "legacy-delivery" },
        lastStatus: "delivery_uncertain"
      }
    }
  }
});
assert.equal(migratedDeliveryState.migrated, true);
const deliveryLegacy = Object.values(migratedDeliveryState.state.conversations)[0];
assert.equal(Object.hasOwn(deliveryLegacy, "pendingDelivery"), false);
assert.equal(deliveryLegacy.lastStatus, "delivery_unconfirmed");

let state = stateModel.emptyState();
let result = stateModel.upsertConversation(state, {
  url: "https://chatgpt.com/c/a",
  label: "Matrix chat",
  preferredTabId: 10,
  repositoryId: "matrixhub",
  repository: "MichalMatu/MatrixHub",
  agentBinding: MATRIX_BINDING,
  bindingRevision: 1,
  bindingSetAt: "2026-09-03T00:00:00Z"
});
state = result.state;
const aId = result.conversation.id;
result = stateModel.upsertConversation(state, {
  url: "https://chatgpt.com/c/b",
  label: "Tracker chat",
  preferredTabId: 20,
  repositoryId: "tracker",
  repository: "MichalMatu/tracker",
  agentBinding: TRACKER_BINDING,
  bindingRevision: 1,
  bindingSetAt: "2026-09-03T00:00:00Z"
});
state = result.state;
const bId = result.conversation.id;
assert.notEqual(aId, bId);
assert.equal(Object.keys(state.conversations).length, 2);
assert.equal(state.conversations[aId].bootstrapPending, true);
assert.equal(state.conversations[aId].repositoryId, "matrixhub");
assert.equal(state.conversations[aId].agentBinding, MATRIX_BINDING);
assert.equal(stateModel.isBoundConversation(state.conversations[aId]), true);
assert.equal(state.conversations[bId].agentBinding, TRACKER_BINDING);

const patched = stateModel.patchConversation(state, aId, {
  enabled: false,
  intervalOverrideMinutes: 15,
  lastStatus: "paused_by_assistant"
});
state = patched.state;
assert.equal(state.conversations[aId].enabled, false);
assert.equal(state.conversations[aId].intervalOverrideMinutes, 15);
assert.equal(state.conversations[aId].agentBinding, MATRIX_BINDING);
assert.equal(state.conversations[bId].enabled, true);
assert.equal(state.conversations[bId].intervalOverrideMinutes, null);

// Invalid binding format sanitizes to unbound and therefore cannot be runnable.
result = stateModel.upsertConversation(state, {
  url: "https://chatgpt.com/c/invalid",
  label: "Invalid binding",
  repositoryId: "matrixhub",
  repository: "MichalMatu/MatrixHub",
  agentBinding: "MATRIX"
});
assert.equal(result.conversation.agentBinding, null);
assert.equal(stateModel.isBoundConversation(result.conversation), false);

assert.equal(stateModel.findConversationByUrl(state, "https://chat.openai.com/c/b")?.id, bId);
state = stateModel.removeConversation(state, aId);
assert.equal(Object.keys(state.conversations).length, 1);
assert.equal(Boolean(state.conversations[bId]), true);

console.log("Chat Bridge state tests passed.");
