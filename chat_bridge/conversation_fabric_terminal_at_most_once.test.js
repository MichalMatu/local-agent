const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const guardSource = fs.readFileSync(
  path.join(__dirname, "worker_conversation_fabric_delivery_guard.js"),
  "utf8"
);

const URL = "https://chatgpt.com/c/parent-at-most-once";
const CAMPAIGN_ID = "cf-deadbeefdeadbeef";

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function makeHarness({
  existingClaim = null,
  baseResult = { ok: false, reason: "delivery_unconfirmed", status: "delivery_unconfirmed" },
  fabric = true
} = {}) {
  const campaign = {
    schema_version: 1,
    id: CAMPAIGN_ID,
    parent_conversation_url: URL,
    state: "completed",
    feedback_delivered: false,
    ...(existingClaim ? { feedback_delivery_claim: clone(existingClaim) } : {})
  };
  const state = {
    conversations: {
      parent: { id: "parent", url: URL }
    }
  };
  let saveCalls = 0;
  let baseDeliverCalls = 0;
  let baseFeedbackCalls = 0;
  let uuidCounter = 0;

  const context = {
    console,
    Date,
    Map,
    Set,
    Promise,
    crypto: { randomUUID: () => `claim-${++uuidCounter}` },
    getBridgeState: async () => state,
    loadConversationFabricCampaign: async (campaignId) =>
      campaignId === CAMPAIGN_ID ? campaign : null,
    saveConversationFabricCampaign: async (value) => {
      assert.equal(value, campaign);
      saveCalls += 1;
      return campaign;
    },
    conversationFabricFeedbackForParent: async (parentUrl) => {
      baseFeedbackCalls += 1;
      if (!fabric || parentUrl !== URL || campaign.feedback_delivered) return null;
      return {
        campaign: clone(campaign),
        prompt: `Conversation Fabric campaign ${CAMPAIGN_ID} completed.`
      };
    },
    deliverConversation: async () => {
      baseDeliverCalls += 1;
      // The real worker asks for Fabric feedback inside deliverConversation. Calling the
      // live global here makes the harness exercise the guard's overridden selector.
      await context.conversationFabricFeedbackForParent(URL);
      return clone(baseResult);
    }
  };

  vm.createContext(context);
  vm.runInContext(guardSource, context, {
    filename: "worker_conversation_fabric_delivery_guard.js"
  });

  return {
    context,
    campaign,
    counts: () => ({ saveCalls, baseDeliverCalls, baseFeedbackCalls })
  };
}

async function testSurvivingClaimAfterRestartIsConsumedWithoutAnotherSend() {
  const h = makeHarness({
    existingClaim: {
      id: "claim-before-restart",
      state: "claimed",
      started_at: "2026-10-04T13:00:00.000Z",
      parent_conversation_url: URL
    }
  });
  const result = await h.context.deliverConversation("parent", false);

  assert.equal(result.ok, true);
  assert.equal(result.reason, "conversation_fabric_feedback_assumed_delivered");
  assert.equal(h.campaign.feedback_delivered, true);
  assert.equal(h.campaign.feedback_delivery_assumed, true);
  assert.equal(h.campaign.feedback_delivery_claim.state, "assumed_delivered");
  assert.equal(h.campaign.feedback_delivery_claim.reason, "delivery_claim_recovered_after_restart");
  assert.equal(h.counts().baseDeliverCalls, 0, "restart recovery must not cross the send boundary again");
}

async function testAmbiguousFreshSendBecomesDurablyAtMostOnce() {
  const h = makeHarness();
  const result = await h.context.deliverConversation("parent", false);

  assert.equal(result.ok, false);
  assert.equal(result.reason, "delivery_unconfirmed");
  assert.equal(h.campaign.feedback_delivered, true);
  assert.equal(h.campaign.feedback_delivery_assumed, true);
  assert.equal(h.campaign.feedback_delivery_claim.state, "assumed_delivered");
  assert.equal(h.campaign.feedback_delivery_claim.reason, "delivery_unconfirmed");
  assert.equal(h.counts().baseDeliverCalls, 1);
  assert.ok(h.counts().saveCalls >= 2, "claim and assumed-delivered receipt must both be durable");
}

async function testDefiniteNoSendClearsClaimAndAllowsRetry() {
  const h = makeHarness({
    baseResult: { ok: false, reason: "composer_not_found", status: "composer_not_found" }
  });
  const result = await h.context.deliverConversation("parent", false);

  assert.equal(result.ok, false);
  assert.equal(result.reason, "composer_not_found");
  assert.equal(h.campaign.feedback_delivered, false);
  assert.equal(h.campaign.feedback_delivery_claim, undefined);
  assert.equal(h.campaign.feedback_delivery_assumed, undefined);
  assert.equal(h.counts().baseDeliverCalls, 1);
}

async function testConfirmedSendKeepsAuditableClaimAndDurableReceipt() {
  const h = makeHarness({
    baseResult: { ok: true, reason: "sent", status: "sent" }
  });
  const result = await h.context.deliverConversation("parent", false);

  assert.equal(result.ok, true);
  assert.equal(h.campaign.feedback_delivered, true);
  assert.equal(h.campaign.feedback_delivery_assumed, undefined);
  assert.equal(h.campaign.feedback_delivery_claim.state, "confirmed");
  assert.match(h.campaign.feedback_delivered_at, /^\d{4}-\d{2}-\d{2}T/);
}

async function testNormalNonFabricDeliveryIsUntouched() {
  const h = makeHarness({ fabric: false, baseResult: { ok: true, reason: "sent", status: "sent" } });
  const result = await h.context.deliverConversation("parent", false);

  assert.equal(result.ok, true);
  assert.equal(h.campaign.feedback_delivered, false);
  assert.equal(h.campaign.feedback_delivery_claim, undefined);
  assert.equal(h.counts().baseDeliverCalls, 1);
}

(async () => {
  await testSurvivingClaimAfterRestartIsConsumedWithoutAnotherSend();
  await testAmbiguousFreshSendBecomesDurablyAtMostOnce();
  await testDefiniteNoSendClearsClaimAndAllowsRetry();
  await testConfirmedSendKeepsAuditableClaimAndDurableReceipt();
  await testNormalNonFabricDeliveryIsUntouched();
  console.log("conversation_fabric_terminal_at_most_once.test.js: OK");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
