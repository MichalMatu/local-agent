"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const parentUrl = "https://chatgpt.com/c/parent-feedback";
const campaignId = "cf-0123456789abcdef";
let savedCampaign = {
  schema_version: 1,
  id: campaignId,
  state: "completed",
  parent_conversation_url: parentUrl,
  feedback_delivered: false,
  children: [],
  results: [],
  failed_children: []
};
let saveCount = 0;

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

const context = vm.createContext({
  console,
  Date,
  JSON,
  Object,
  Array,
  Set,
  Map,
  Number,
  String,
  Boolean,
  Promise,
  CONVERSATION_FABRIC_RESULT_CHARS: 6000,
  CONVERSATION_FABRIC_TIMEOUT_MS: 15 * 60 * 1000,
  conversationFabricOperations: new Map(),
  applyConversationFabricControl: async () => ({
    ok: true,
    reason: "conversation_fabric_completed",
    campaignId,
    feedbackPrompt: "terminal feedback that must not use the direct path"
  }),
  pollConversationFabricCampaigns: async () => {},
  acknowledgeConversationFabricFeedback: async () => ({ ok: true }),
  validateConversationFabricMessage(message) {
    return {
      conversationUrl: parentUrl,
      parentTabId: 11,
      assistantIdentity: "assistant-parent",
      fingerprint: "a1b2c3d4",
      control: message.control
    };
  },
  async conversationFabricManagedParent() {
    return { id: "parent", url: parentUrl, enabled: true };
  },
  async conversationFabricCampaignId() {
    return campaignId;
  },
  async loadConversationFabricCampaign(id) {
    return id === campaignId ? clone(savedCampaign) : null;
  },
  async saveConversationFabricCampaign(campaign) {
    savedCampaign = clone(campaign);
    saveCount += 1;
    return clone(savedCampaign);
  },
  async conversationFabricFeedbackForParent() {
    return savedCampaign.feedback_delivered
      ? null
      : { campaign: clone(savedCampaign), prompt: "terminal feedback" };
  },
  conversationFabricFailedChildren: () => [],
  stableConversationFabricResult: async () => ({ ok: true, reason: "child_generating" }),
  conversationFabricPendingPrompt: () => "pending",
  conversationFabricCompletedPrompt: () => "completed",
  cleanupConversationFabricChildren: async () => true,
  listConversationFabricCampaigns: async () => [],
  getBridgeState: async () => ({ settings: { masterEnabled: false }, conversations: {} }),
  conversationId: () => "parent",
  serializeConversationFabric: async (_key, fn) => fn(),
  runFeedbackCycle: async () => ({ ok: true })
});
context.globalThis = context;

vm.runInContext(
  fs.readFileSync(path.join(__dirname, "worker_conversation_fabric_recovery.js"), "utf8"),
  context,
  { filename: "worker_conversation_fabric_recovery.js" }
);

(async () => {
  const sender = {
    id: "test-bridge",
    frameId: 0,
    tab: { id: 11, url: parentUrl }
  };
  const repeatedDelegate = {
    campaignId,
    control: {
      schema_version: 1,
      action: "delegate",
      children: [
        { id: "logic", role: "research", prompt: "already completed" }
      ]
    }
  };

  const direct = await context.applyConversationFabricControl(repeatedDelegate, sender);
  assert.equal(direct.ok, true);
  assert.equal(direct.reason, "conversation_fabric_completed");
  assert.equal(direct.feedbackPrompt, undefined, "terminal result must not be delivered by repeated delegate");
  assert.equal(direct.feedback_deferred_to_worker, true);

  assert.notEqual(await context.conversationFabricFeedbackForParent(), null);
  const acknowledged = await context.acknowledgeConversationFabricFeedback(repeatedDelegate, sender);
  assert.deepEqual(clone(acknowledged), {
    ok: true,
    reason: "conversation_fabric_feedback_acknowledged"
  });
  assert.equal(savedCampaign.feedback_delivered, true);
  assert.match(savedCampaign.feedback_delivered_at, /^\d{4}-\d{2}-\d{2}T/);
  assert.equal(saveCount, 1, "first terminal ACK must be persisted exactly once");
  assert.equal(
    await context.conversationFabricFeedbackForParent(),
    null,
    "durably acknowledged terminal feedback must not be selected for another delivery"
  );

  const repeatedAck = await context.acknowledgeConversationFabricFeedback(repeatedDelegate, sender);
  assert.equal(repeatedAck.ok, true);
  assert.equal(saveCount, 1, "repeated ACK must be idempotent and must not rewrite durable state");

  savedCampaign.feedback_delivered = false;
  delete savedCampaign.feedback_delivered_at;
  const mismatch = await context.acknowledgeConversationFabricFeedback(
    { ...repeatedDelegate, campaignId: "cf-fedcba9876543210" },
    sender
  );
  assert.equal(mismatch.ok, false);
  assert.equal(mismatch.reason, "conversation_fabric_campaign_mismatch");
  assert.equal(savedCampaign.feedback_delivered, false, "mismatched delegate must not acknowledge another campaign");

  const collectAck = await context.acknowledgeConversationFabricFeedback({
    campaignId,
    control: {
      schema_version: 1,
      action: "collect",
      campaign_id: campaignId
    }
  }, sender);
  assert.equal(collectAck.ok, true);
  assert.equal(savedCampaign.feedback_delivered, true, "collect ACK remains supported");

  console.log("Conversation Fabric terminal feedback idempotency tests passed.");
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
