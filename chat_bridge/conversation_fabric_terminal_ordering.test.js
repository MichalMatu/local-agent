"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const parentUrl = "https://chatgpt.com/c/terminal-ordering-parent";
const oldCampaignId = "cf-aaaaaaaaaaaaaaaa";
const oldCampaignKey = `conversation-fabric-campaign:${oldCampaignId}`;

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

(async () => {
  const storage = {
    [oldCampaignKey]: {
      schema_version: 1,
      id: oldCampaignId,
      state: "completed",
      parent_conversation_url: parentUrl,
      parent_tab_id: 11,
      assistant_identity: "assistant-old",
      fingerprint: "11111111",
      created_at: "2026-10-04T10:00:00.000Z",
      children: [],
      results: [],
      failed_children: [],
      feedback_delivered: false,
      cleanup_pending: false
    }
  };
  let digest = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
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
    setTimeout: (fn) => { fn(); return 1; },
    clearTimeout: () => {},
    chrome: {
      runtime: { id: "test-bridge" },
      storage: {
        local: {
          async get(key) {
            if (key === null) return clone(storage);
            return { [key]: clone(storage[key]) };
          },
          async set(patch) { Object.assign(storage, clone(patch)); },
          async remove(key) { delete storage[key]; }
        }
      }
    },
    async conversationSpawnSha256() { return digest; }
  });
  context.globalThis = context;
  context.LocalAgentConversationFabricProtocol = {
    SCHEMA_VERSION: 1,
    MAX_CHILDREN: 4,
    CAMPAIGN_ID_RE: /^cf-[0-9a-f]{16}$/,
    CHILD_ID_RE: /^[A-Za-z0-9._-]{1,64}$/,
    validateControl(value) { return value; }
  };

  for (const file of ["worker_conversation_fabric.js", "worker_conversation_fabric_recovery.js"]) {
    vm.runInContext(
      fs.readFileSync(path.join(__dirname, file), "utf8"),
      context,
      { filename: file }
    );
  }

  const authority = {
    conversationUrl: parentUrl,
    parentTabId: 11,
    assistantIdentity: "assistant-new",
    fingerprint: "22222222",
    control: {
      action: "delegate",
      children: [{ id: "new-child", role: "research", prompt: "bounded task" }]
    }
  };

  const blocked = await context.delegateConversationFabric(authority);
  assert.equal(blocked.ok, false);
  assert.equal(blocked.reason, "conversation_fabric_terminal_feedback_pending");
  assert.equal(blocked.campaignId, oldCampaignId);
  assert.deepEqual(Object.keys(storage), [oldCampaignKey], "blocked delegation must not create a newer campaign");

  // Re-processing the exact originating delegate remains idempotent: it may surface the
  // existing campaign instead of being mistaken for a different newer delegation.
  digest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
  const sameCampaign = await context.delegateConversationFabric(authority);
  assert.equal(sameCampaign.ok, true);
  assert.equal(sameCampaign.reason, "conversation_fabric_completed");
  assert.equal(sameCampaign.campaignId, oldCampaignId);

  console.log("Conversation Fabric terminal ordering tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
