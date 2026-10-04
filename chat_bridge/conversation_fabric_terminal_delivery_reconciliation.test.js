const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const workerSource = fs.readFileSync(path.join(__dirname, "worker_delivery.js"), "utf8");
const PROMPT = "Conversation Fabric campaign cf-deadbeef completed.\n\nSynthesize the final parent answer now.";
const URL = "https://chatgpt.com/c/parent-1";

function makeHarness({
  latestUserText = PROMPT,
  earlierUserTexts = [],
  fabric = true,
  lastStatus = "delivery_unconfirmed"
} = {}) {
  const state = {
    settings: { masterEnabled: true },
    conversations: {
      parent: {
        id: "parent",
        url: URL,
        enabled: true,
        generation: 7,
        bindingRevision: 3,
        preferredTabId: 42,
        bootstrapPending: false,
        assistantBaseline: "assistant-before",
        lastStatus
      }
    }
  };
  const campaign = {
    id: "cf-deadbeef",
    parent_conversation_url: URL,
    state: "completed",
    feedback_delivered: false
  };
  let sendCalls = 0;
  let scriptCalls = 0;
  let saveCalls = 0;
  let scheduleCalls = 0;

  const userMessages = [...earlierUserTexts, latestUserText].map((text) => {
    const turn = {};
    return {
      innerText: text,
      textContent: text,
      closest: () => turn
    };
  });

  const context = {
    console,
    Date,
    Promise,
    URL: global.URL,
    setTimeout,
    clearTimeout,
    CONTENT_PROTOCOL_VERSION: 18,
    DELIVERY_TIMEOUT_MS: 25,
    RETRY_REASONS: new Set(),
    inFlightDeliveries: new Set(),
    activeDeliveries: new Map(),
    crypto: { randomUUID: () => "delivery-1" },
    location: { href: URL },
    document: {
      querySelectorAll: () => userMessages
    },
    stateModel: { isTransportReady: () => true },
    getBridgeState: async () => state,
    loadRuntimeConfig: async () => ({
      source: "remote",
      intervalMinutes: 5,
      busyRetryMinutes: 1
    }),
    findConversationTab: async () => ({ id: 42, url: URL }),
    updateConversationStatus: async () => {},
    clearConversationAlarm: async () => {},
    scheduleAfterMinutes: async () => { scheduleCalls += 1; },
    ensureContentScript: async () => ({ ok: true }),
    kickAssistantRecovery: async () => ({ ok: true, recoverableAssistantError: false }),
    conversationFabricFeedbackForParent: async () => fabric ? { campaign, prompt: PROMPT } : null,
    buildBootstrapPrompt: () => "bootstrap",
    buildWakePrompt: () => "wake",
    loadConversationFabricCampaign: async (campaignId) => campaignId === campaign.id ? campaign : null,
    saveConversationFabricCampaign: async () => { saveCalls += 1; },
    mutateState: async (mutator) => {
      const next = mutator(state);
      assert.equal(next, state);
      return state;
    },
    definitelyNoContentReceiver: () => false,
    chrome: {
      scripting: {
        executeScript: async (options) => {
          scriptCalls += 1;
          assert.equal(options.target.tabId, 42);
          assert.deepEqual(Array.from(options.target.frameIds), [0]);
          assert.equal(options.args[0], URL);
          assert.equal(options.args[1], PROMPT);
          return [{ result: options.func(...options.args) }];
        }
      },
      tabs: {
        sendMessage: async () => {
          sendCalls += 1;
          return { ok: true, reason: "sent", protocolVersion: 18 };
        }
      }
    }
  };

  vm.createContext(context);
  vm.runInContext(workerSource, context, { filename: "worker_delivery.js" });
  return {
    context,
    state,
    campaign,
    counts: () => ({ sendCalls, scriptCalls, saveCalls, scheduleCalls })
  };
}

async function testExactTerminalPromptIsReconciledWithoutReplay() {
  const harness = makeHarness();
  const result = await harness.context.deliverConversation("parent", false);
  assert.equal(result.ok, true);
  assert.equal(result.reason, "already_sent");
  assert.equal(result.status, "sent");
  assert.equal(harness.campaign.feedback_delivered, true);
  assert.match(harness.campaign.feedback_delivered_at, /^\d{4}-\d{2}-\d{2}T/);
  assert.equal(harness.state.conversations.parent.lastStatus, "sent");
  assert.deepEqual(harness.counts(), {
    sendCalls: 0,
    scriptCalls: 1,
    saveCalls: 1,
    scheduleCalls: 1
  });
}

async function testEarlierExactTerminalPromptSurvivesLaterOperatorTurn() {
  const harness = makeHarness({
    earlierUserTexts: [PROMPT],
    latestUserText: "gotowe wznowilem tez zbindowany chat bridge"
  });
  const result = await harness.context.deliverConversation("parent", false);
  assert.equal(result.ok, true);
  assert.equal(result.reason, "already_sent");
  assert.equal(result.status, "sent");
  assert.equal(harness.campaign.feedback_delivered, true);
  assert.deepEqual(harness.counts(), {
    sendCalls: 0,
    scriptCalls: 1,
    saveCalls: 1,
    scheduleCalls: 1
  });
}

async function testDifferentUserHistoryFallsBackToNormalDelivery() {
  const harness = makeHarness({
    earlierUserTexts: ["older operator message"],
    latestUserText: "operator wrote something else"
  });
  const result = await harness.context.deliverConversation("parent", false);
  assert.equal(result.ok, true);
  assert.equal(result.reason, "sent");
  assert.equal(harness.campaign.feedback_delivered, true);
  assert.deepEqual(harness.counts(), {
    sendCalls: 1,
    scriptCalls: 1,
    saveCalls: 1,
    scheduleCalls: 1
  });
}

async function testNormalWakeNeverUsesFabricReconciliation() {
  const harness = makeHarness({ fabric: false });
  const result = await harness.context.deliverConversation("parent", false);
  assert.equal(result.ok, true);
  assert.equal(result.reason, "sent");
  assert.deepEqual(harness.counts(), {
    sendCalls: 1,
    scriptCalls: 0,
    saveCalls: 0,
    scheduleCalls: 1
  });
}

async function testSendButtonRetryDoesNotClaimPriorUserTurn() {
  const harness = makeHarness({ lastStatus: "send_button_not_ready" });
  const result = await harness.context.deliverConversation("parent", false);
  assert.equal(result.ok, true);
  assert.equal(result.reason, "sent");
  assert.deepEqual(harness.counts(), {
    sendCalls: 1,
    scriptCalls: 0,
    saveCalls: 1,
    scheduleCalls: 1
  });
}

(async () => {
  await testExactTerminalPromptIsReconciledWithoutReplay();
  await testEarlierExactTerminalPromptSurvivesLaterOperatorTurn();
  await testDifferentUserHistoryFallsBackToNormalDelivery();
  await testNormalWakeNeverUsesFabricReconciliation();
  await testSendButtonRetryDoesNotClaimPriorUserTurn();
  console.log("conversation_fabric_terminal_delivery_reconciliation.test.js: OK");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});