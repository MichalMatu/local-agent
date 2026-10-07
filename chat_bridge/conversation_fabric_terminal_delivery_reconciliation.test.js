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
  activeFabric = false,
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
  const sentPrompts = [];
  const localStorage = {};

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
    conversationId: (value) => value === URL ? "parent" : "",
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
    listConversationFabricCampaigns: async () => activeFabric
      ? [{ id: "cf-active", parent_conversation_url: URL, state: "running" }]
      : [],
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
      storage: {
        local: {
          get: async (key) => {
            if (key === null) return { ...localStorage };
            if (typeof key === "string") {
              return Object.hasOwn(localStorage, key) ? { [key]: localStorage[key] } : {};
            }
            return {};
          },
          set: async (patch) => { Object.assign(localStorage, patch); },
          remove: async (key) => { delete localStorage[key]; }
        }
      },
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
        sendMessage: async (_tabId, message) => {
          sendCalls += 1;
          sentPrompts.push(message.prompt);
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
    sentPrompts,
    localStorage,
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


async function testActiveFabricReservesParentFromNormalWake() {
  const harness = makeHarness({
    fabric: false,
    activeFabric: true,
    lastStatus: "sent"
  });
  const result = await harness.context.deliverConversation("parent", false);
  assert.equal(result.ok, false);
  assert.equal(result.reason, "conversation_fabric_parent_reserved");
  assert.equal(result.status, "conversation_fabric_parent_reserved");
  assert.deepEqual(harness.counts(), {
    sendCalls: 0,
    scriptCalls: 0,
    saveCalls: 0,
    scheduleCalls: 1
  });
}

async function testExplicitFabricPromptUsesSingleWriterEvenWhileCampaignIsActive() {
  const harness = makeHarness({
    fabric: false,
    activeFabric: true,
    lastStatus: "sent"
  });
  const prompt = "Conversation Fabric result inspection: child=verify";
  const result = await harness.context.runFeedbackCycle({
    conversationId: "parent",
    manual: true,
    promptOverride: prompt
  });
  assert.equal(result.ok, true);
  assert.equal(result.reason, "sent");
  assert.deepEqual(harness.sentPrompts, [prompt]);
  assert.deepEqual(harness.counts(), {
    sendCalls: 1,
    scriptCalls: 0,
    saveCalls: 0,
    scheduleCalls: 0
  });
}

async function testQueuedFabricFeedbackPreemptsNormalWakeAndIsAcknowledged() {
  const harness = makeHarness({
    fabric: false,
    activeFabric: false,
    lastStatus: "sent"
  });
  const prompt = "Conversation Fabric result inspection: child=verify";
  const queued = await harness.context.queueConversationFabricExplicitFeedback(URL, {
    id: "conversation_fabric_inspect:deadbeef",
    kind: "conversation_fabric_inspect",
    prompt
  });
  assert.equal(queued.prompt, prompt);

  const result = await harness.context.deliverConversation("parent", false);
  assert.equal(result.ok, true);
  assert.equal(result.explicitFabricFeedback, true);
  assert.deepEqual(harness.sentPrompts, [prompt]);
  assert.equal(await harness.context.conversationFabricExplicitFeedbackForParent(URL), null);
  assert.deepEqual(harness.counts(), {
    sendCalls: 1,
    scriptCalls: 0,
    saveCalls: 0,
    scheduleCalls: 1
  });
}

async function testQueuedFabricFeedbackWaitsBehindActiveParentReservation() {
  const harness = makeHarness({
    fabric: false,
    activeFabric: true,
    lastStatus: "sent"
  });
  const prompt = "Conversation Fabric result inspection: child=verify";
  await harness.context.queueConversationFabricExplicitFeedback(URL, {
    id: "conversation_fabric_inspect:reserved",
    kind: "conversation_fabric_inspect",
    prompt
  });

  const result = await harness.context.deliverConversation("parent", false);
  assert.equal(result.ok, false);
  assert.equal(result.reason, "conversation_fabric_parent_reserved");
  assert.deepEqual(harness.sentPrompts, []);
  assert.equal(
    (await harness.context.conversationFabricExplicitFeedbackForParent(URL))?.prompt,
    prompt,
    "active campaign must preserve explicit feedback without touching the parent"
  );
}

async function testSameFeedbackIdIsIdempotentAndConflictFailsClosed() {
  const harness = makeHarness({ fabric: false });
  const first = {
    id: "conversation_fabric_inspect:deadbeef",
    kind: "conversation_fabric_inspect",
    prompt: "inspect one"
  };
  await harness.context.queueConversationFabricExplicitFeedback(URL, first);
  await harness.context.queueConversationFabricExplicitFeedback(URL, { ...first });
  const queue = await harness.context.conversationFabricExplicitFeedbackQueue(URL);
  assert.equal(queue.items.length, 1);
  await assert.rejects(
    harness.context.queueConversationFabricExplicitFeedback(URL, { ...first, prompt: "inspect changed" }),
    /same-id feedback conflict/
  );
}

async function testSendButtonRetryReconcilesExactTerminalPromptAfterOperatorSubmit() {
  const harness = makeHarness({ lastStatus: "send_button_not_ready" });
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

async function testSendButtonRetryWithDifferentUserHistoryFallsBackToNormalDelivery() {
  const harness = makeHarness({
    lastStatus: "send_button_not_ready",
    latestUserText: "operator sent something else"
  });
  const result = await harness.context.deliverConversation("parent", false);
  assert.equal(result.ok, true);
  assert.equal(result.reason, "sent");
  assert.deepEqual(harness.counts(), {
    sendCalls: 1,
    scriptCalls: 1,
    saveCalls: 1,
    scheduleCalls: 1
  });
}

(async () => {
  await testExactTerminalPromptIsReconciledWithoutReplay();
  await testEarlierExactTerminalPromptSurvivesLaterOperatorTurn();
  await testDifferentUserHistoryFallsBackToNormalDelivery();
  await testNormalWakeNeverUsesFabricReconciliation();
  await testActiveFabricReservesParentFromNormalWake();
  await testExplicitFabricPromptUsesSingleWriterEvenWhileCampaignIsActive();
  await testQueuedFabricFeedbackPreemptsNormalWakeAndIsAcknowledged();
  await testQueuedFabricFeedbackWaitsBehindActiveParentReservation();
  await testSameFeedbackIdIsIdempotentAndConflictFailsClosed();
  await testSendButtonRetryReconcilesExactTerminalPromptAfterOperatorSubmit();
  await testSendButtonRetryWithDifferentUserHistoryFallsBackToNormalDelivery();
  console.log("conversation_fabric_terminal_delivery_reconciliation.test.js: OK");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});