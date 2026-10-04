"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = __dirname;
const parentUrl = "https://chatgpt.com/c/parent-1";

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function createHarness({ failSecondSubmit = false, managed = true } = {}) {
  const session = {};
  const created = [];
  const submitted = [];
  const observed = [];
  const closed = [];
  const injected = [];
  let nextTabId = 100;

  const context = vm.createContext({
    console,
    crypto: crypto.webcrypto,
    URL,
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
    setTimeout: (fn) => { fn(); return 1; },
    clearTimeout: () => {},
    chrome: {
      runtime: { id: "test-bridge" },
      storage: {
        session: {
          async get(key) {
            if (key === null) return clone(session);
            return { [key]: clone(session[key]) };
          },
          async set(patch) {
            Object.assign(session, clone(patch));
          }
        }
      },
      tabs: {
        async query() {
          return [{ id: 11, url: parentUrl }];
        }
      },
      scripting: {
        async executeScript(details) {
          injected.push(clone(details));
          return [];
        }
      }
    }
  });
  context.globalThis = context;

  vm.runInContext(
    fs.readFileSync(path.join(root, "control_protocol.js"), "utf8"),
    context,
    { filename: "control_protocol.js" }
  );
  vm.runInContext(
    fs.readFileSync(path.join(root, "conversation_fabric_protocol.js"), "utf8"),
    context,
    { filename: "conversation_fabric_protocol.js" }
  );

  const parentId = context.LocalAgentBridgeProtocol.conversationId(parentUrl);
  Object.assign(context, {
    CONTENT_PROTOCOL_VERSION: context.LocalAgentBridgeProtocol.CONTENT_PROTOCOL_VERSION,
    CONVERSATION_SPAWN_BROWSER_SCHEMA_VERSION: 1,
    normalizeConversationUrl: context.LocalAgentBridgeProtocol.normalizeConversationUrl,
    conversationId: context.LocalAgentBridgeProtocol.conversationId,
    async getBridgeState() {
      return {
        conversations: managed
          ? { [parentId]: { id: parentId, url: parentUrl, preferredTabId: 11 } }
          : {}
      };
    },
    async conversationSpawnSha256(text) {
      return crypto.createHash("sha256").update(String(text), "utf8").digest("hex");
    },
    async createConversationSpawnTab(intent) {
      const tabId = ++nextTabId;
      created.push({ tabId, intent: clone(intent) });
      return { ok: true, reason: "tab_created", tabId };
    },
    async submitConversationSpawnBootstrap(intent) {
      submitted.push(clone(intent));
      if (failSecondSubmit && submitted.length === 2) {
        return { ok: false, reason: "spawn_unexpected_route" };
      }
      return {
        ok: true,
        reason: "identity_discovered",
        childConversationUrl: `https://chatgpt.com/c/child-${intent.tab_id}`
      };
    },
    async reconcileConversationSpawn() {
      throw new Error("unexpected reconcile");
    },
    async observeConversationSpawnResult(intent) {
      observed.push(clone(intent));
      return {
        ok: true,
        reason: "child_result_ready",
        childConversationUrl: `https://chatgpt.com/c/child-${intent.tab_id}`,
        assistantIdentity: `assistant-${intent.tab_id}`,
        assistantText: `Result for tab ${intent.tab_id}.`,
        truncated: false
      };
    },
    async closeConversationSpawnTab(intent) {
      closed.push(clone(intent));
      return { ok: true, reason: "child_closed" };
    }
  });

  vm.runInContext(
    fs.readFileSync(path.join(root, "worker_conversation_fabric.js"), "utf8"),
    context,
    { filename: "worker_conversation_fabric.js" }
  );

  const sender = {
    id: "test-bridge",
    frameId: 0,
    url: parentUrl,
    tab: { id: 11, url: parentUrl }
  };
  const delegateControl = {
    schema_version: 1,
    action: "delegate",
    children: [
      { id: "audit", role: "research", prompt: "Audit one bounded concern." },
      { id: "verify", role: "verification", prompt: "Verify one independent concern." }
    ],
    marker: "synthetic-marker"
  };
  const delegateMessage = {
    type: "bridge:conversation-fabric-control",
    conversationUrl: parentUrl,
    fingerprint: "a1b2c3d4",
    assistantIdentity: "assistant-parent-turn",
    contentProtocolVersion: context.CONTENT_PROTOCOL_VERSION,
    control: delegateControl
  };

  return {
    context,
    session,
    created,
    submitted,
    observed,
    closed,
    injected,
    sender,
    delegateMessage
  };
}

(async () => {
  {
    const h = createHarness();
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(h.injected.length, 1, "worker activation must refresh CF content in open ChatGPT tabs");
    assert.deepEqual(h.injected[0].target, { tabId: 11, frameIds: [0] });

    const started = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    assert.equal(started.ok, true, JSON.stringify(started));
    assert.equal(started.reason, "conversation_fabric_started");
    assert.match(started.campaignId, /^cf-[0-9a-f]{16}$/);
    assert.equal(h.created.length, 2);
    assert.equal(h.submitted.length, 2);
    assert.ok(h.submitted.every((intent) => intent.bootstrap_text.includes("Do not create Local Agent tasks")));
    assert.match(started.feedbackPrompt, /GitHub-managed wake/);
    assert.match(started.feedbackPrompt, /control_generation/);
    assert.doesNotMatch(started.feedbackPrompt, /\[LAB:/);
    assert.match(started.feedbackPrompt, /<<<LOCAL_AGENT_CF/);

    const duplicate = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    assert.equal(duplicate.ok, true);
    assert.equal(duplicate.campaignId, started.campaignId);
    assert.equal(h.created.length, 2, "duplicate parent control must not create more child tabs");

    const collected = await h.context.applyConversationFabricControl({
      type: "bridge:conversation-fabric-control",
      conversationUrl: parentUrl,
      fingerprint: "b1c2d3e4",
      assistantIdentity: "assistant-parent-collect",
      contentProtocolVersion: h.context.CONTENT_PROTOCOL_VERSION,
      control: {
        schema_version: 1,
        action: "collect",
        campaign_id: started.campaignId,
        marker: "synthetic-collect"
      }
    }, h.sender);
    assert.equal(collected.ok, true, JSON.stringify(collected));
    assert.equal(collected.reason, "conversation_fabric_completed");
    assert.equal(h.observed.length, 4, "each child result must be stable across two observations");
    assert.equal(h.closed.length, 2, "completed campaign must close exactly its two owned child tabs");
    assert.match(collected.feedbackPrompt, /Result for tab 101\./);
    assert.match(collected.feedbackPrompt, /Result for tab 102\./);

    const wrongSender = await h.context.applyConversationFabricControl(
      h.delegateMessage,
      { ...h.sender, url: "https://chatgpt.com/c/other", tab: { id: 11, url: "https://chatgpt.com/c/other" } }
    );
    assert.equal(wrongSender.ok, false);
    assert.equal(wrongSender.reason, "conversation_fabric_control_invalid");
  }

  {
    const h = createHarness({ managed: false });
    const result = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    assert.equal(result.ok, false, JSON.stringify(result));
    assert.equal(result.reason, "conversation_fabric_parent_not_managed");
    assert.equal(h.created.length, 0, "unmanaged ChatGPT tabs must not create Conversation Fabric children");
  }

  {
    const h = createHarness({ failSecondSubmit: true });
    const result = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    assert.equal(result.ok, false, JSON.stringify(result));
    assert.equal(result.reason, "conversation_fabric_failed");
    assert.equal(h.closed.length, 2, "partial failure must close both the completed child and current failed owned tab");
  }

  console.log("Conversation Fabric worker tests passed.");
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
