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

function childIdForIntent(intent) {
  const match = String(intent?.bootstrap_text || "").match(/^child_id=([^\n]+)$/m);
  return match ? match[1] : "";
}

function createHarness({
  failChildId = "",
  failReason = "spawn_unexpected_route",
  ambiguousChildId = "",
  reconcilePlan = {},
  resultTextByChild = {},
  allowActiveClose = false,
  managed = true,
  storage = {}
} = {}) {
  const session = storage;
  const created = [];
  const submitted = [];
  const childrenAtSubmit = [];
  const observed = [];
  const closed = [];
  const closedTabIds = new Set();
  const injected = [];
  const reconcileQueues = Object.fromEntries(
    Object.entries(reconcilePlan).map(([id, values]) => [id, [...values]])
  );
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
        local: {
          async get(key) {
            if (key === null) return clone(session);
            return { [key]: clone(session[key]) };
          },
          async set(patch) {
            Object.assign(session, clone(patch));
          },
          async remove(key) { delete session[key]; }
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
        settings: { masterEnabled: true },
        conversations: managed
          ? { [parentId]: { id: parentId, url: parentUrl, preferredTabId: 11, enabled: true } }
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
      const activeCampaign = Object.entries(session).find(([key]) =>
        key.startsWith("conversation-fabric-campaign:")
      )?.[1];
      childrenAtSubmit.push(Number(activeCampaign?.children?.length || 0));
      submitted.push(clone(intent));
      const childId = childIdForIntent(intent);
      if (ambiguousChildId && childId === ambiguousChildId) {
        return {
          ok: false,
          reason: "spawn_submission_ambiguous",
          route: "provisional_timeout"
        };
      }
      if (failChildId && childId === failChildId) {
        return {
          ok: false,
          reason: failReason,
          error: `synthetic failure for ${failChildId}`
        };
      }
      return {
        ok: true,
        reason: "identity_discovered",
        childConversationUrl: `https://chatgpt.com/c/child-${intent.tab_id}`
      };
    },
    async reconcileConversationSpawn(intent) {
      const childId = childIdForIntent(intent);
      const queue = reconcileQueues[childId] || [];
      if (!queue.length) throw new Error(`unexpected reconcile for ${childId}`);
      const reason = queue.shift();
      if (reason === "identity_discovered") {
        return {
          ok: true,
          reason,
          childConversationUrl: `https://chatgpt.com/c/child-${intent.tab_id}`
        };
      }
      return { ok: false, reason };
    },
    async observeConversationSpawnResult(intent) {
      observed.push(clone(intent));
      const childId = childIdForIntent(intent);
      return {
        ok: true,
        reason: "child_result_ready",
        childConversationUrl: `https://chatgpt.com/c/child-${intent.tab_id}`,
        assistantIdentity: `assistant-${intent.tab_id}`,
        assistantText: String(resultTextByChild[childId] || `Result for tab ${intent.tab_id}.`),
        truncated: false
      };
    },
    async closeConversationSpawnTab(intent) {
      if (!allowActiveClose) {
        assert.ok(
          Object.values(session).some(value =>
            String(value?.id || "").startsWith("cf-") && ["completed", "failed"].includes(value.state)
          ),
          "terminal evidence must be saved before tabs close"
        );
      }
      if (closedTabIds.has(intent.tab_id)) return { ok: true, reason: "child_already_closed" };
      closedTabIds.add(intent.tab_id);
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
    childrenAtSubmit,
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
    assert.equal(h.injected.length, 0, "content refresh belongs to the shared Bridge transport");

    const started = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    assert.equal(started.ok, true, JSON.stringify(started));
    assert.equal(started.reason, "conversation_fabric_started");
    assert.match(started.campaignId, /^cf-[0-9a-f]{16}$/);
    assert.equal(h.created.length, 2);
    assert.equal(h.submitted.length, 2);
    assert.ok(h.submitted.every((intent) => intent.bootstrap_text.includes("Do not create Local Agent tasks")));
    assert.match(started.feedbackPrompt, /existing GitHub control poll/);
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
    const staleCleanup = await h.context.loadConversationFabricCampaign(started.campaignId);
    const delivered = clone(staleCleanup);
    delivered.feedback_delivered = true;
    await h.context.saveConversationFabricCampaign(delivered);
    staleCleanup.cleanup_pending = false;
    await h.context.saveConversationFabricCampaign(staleCleanup);
    assert.equal(
      (await h.context.loadConversationFabricCampaign(started.campaignId)).feedback_delivered,
      true,
      "late cleanup must not erase the receipt of concurrent terminal feedback delivery"
    );

    const vaultRecords = Object.entries(h.session)
      .filter(([key]) => key.startsWith("conversation-fabric-result:"))
      .map(([, value]) => value);
    assert.equal(vaultRecords.length, 2, "every stable child result must have an independent vault record");
    assert.ok(vaultRecords.every(value => /^[0-9a-f]{64}$/.test(value.text_sha256)));

    const inspectCampaign = await h.context.applyConversationFabricControl({
      ...h.delegateMessage,
      fingerprint: "inspect-campaign",
      assistantIdentity: "assistant-inspect-campaign",
      control: {
        schema_version: 1,
        action: "inspect",
        campaign_id: started.campaignId,
        marker: "synthetic-inspect"
      }
    }, h.sender);
    assert.equal(inspectCampaign.ok, true, JSON.stringify(inspectCampaign));
    assert.equal(inspectCampaign.reason, "conversation_fabric_inspect");
    assert.match(inspectCampaign.feedbackPrompt, /Vault records:/);
    assert.match(inspectCampaign.feedbackPrompt, /child=audit/);

    const auditVaultKey = Object.keys(h.session).find(key =>
      key.startsWith(`conversation-fabric-result:${started.campaignId}:audit`)
    );
    assert.ok(auditVaultKey);
    const campaignKey = `conversation-fabric-campaign:${started.campaignId}`;
    delete h.session[campaignKey];
    const inspectArchivedChild = await h.context.applyConversationFabricControl({
      ...h.delegateMessage,
      fingerprint: "inspect-vault-only",
      assistantIdentity: "assistant-inspect-vault-only",
      control: {
        schema_version: 1,
        action: "inspect",
        campaign_id: started.campaignId,
        child_id: "audit",
        marker: "synthetic-inspect-child"
      }
    }, h.sender);
    assert.equal(inspectArchivedChild.ok, true, JSON.stringify(inspectArchivedChild));
    assert.match(inspectArchivedChild.feedbackPrompt, /state=vault-only/);
    assert.match(inspectArchivedChild.feedbackPrompt, /Result for tab 101\./);
    assert.ok(h.session[auditVaultKey], "campaign pruning/removal must not remove the independent result vault");

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
    const h = createHarness({ allowActiveClose: true });
    const started = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    assert.equal(started.ok, true, JSON.stringify(started));
    const createdBefore = h.created.length;
    const submittedBefore = h.submitted.length;

    const retired = await h.context.applyConversationFabricControl({
      ...h.delegateMessage,
      fingerprint: "retire-verify",
      assistantIdentity: "assistant-retire-verify",
      control: {
        schema_version: 1,
        action: "retire",
        campaign_id: started.campaignId,
        child_id: "verify",
        marker: "synthetic-retire"
      }
    }, h.sender);
    assert.equal(retired.ok, true, JSON.stringify(retired));
    assert.equal(retired.reason, "conversation_fabric_child_retired");
    assert.equal(retired.hadCapturedResult, false);
    assert.equal(h.created.length, createdBefore, "retire must not create a replacement tab");
    assert.equal(h.submitted.length, submittedBefore, "retire must not replay any bootstrap");
    assert.deepEqual(
      h.closed.map(intent => intent.tab_id).sort(),
      [101, 102],
      "explicit retire plus terminal cleanup closes only the original exact owned tabs"
    );
    const terminal = await h.context.loadConversationFabricCampaign(started.campaignId);
    const verify = terminal.children.find(child => child.id === "verify");
    assert.equal(verify.state, "failed");
    assert.equal(verify.failure.reason, "operator_retired");
    assert.equal(verify.failure.retryable, true);
    assert.equal(terminal.results.length, 1, "non-retired sibling result is still captured");
    assert.match(retired.feedbackPrompt, /retryable missing coverage/);
  }

  {
    const h = createHarness({
      ambiguousChildId: "verify",
      reconcilePlan: {
        verify: ["spawn_submission_ambiguous", "identity_discovered"]
      }
    });
    const started = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    assert.equal(started.ok, true, JSON.stringify(started));
    assert.equal(started.reason, "conversation_fabric_started");
    assert.equal(h.created.length, 2, "ambiguous submission must keep the original child tab");
    assert.equal(h.submitted.length, 2, "each child bootstrap must be submitted exactly once");

    const running = await h.context.loadConversationFabricCampaign(started.campaignId);
    assert.deepEqual(
      Array.from(running.children, child => child.state),
      ["submitted", "submission_ambiguous"]
    );
    assert.equal(running.failed_children.length, 0, "ambiguous routing is not a startup failure");
    assert.match(started.feedbackPrompt, /Route\/identity confirmation is still pending for: verify/);

    const collected = await h.context.applyConversationFabricControl({
      type: "bridge:conversation-fabric-control",
      conversationUrl: parentUrl,
      fingerprint: "a2b3c4d5",
      assistantIdentity: "assistant-ambiguous-collect",
      contentProtocolVersion: h.context.CONTENT_PROTOCOL_VERSION,
      control: {
        schema_version: 1,
        action: "collect",
        campaign_id: started.campaignId,
        marker: "synthetic-ambiguous-collect"
      }
    }, h.sender);
    assert.equal(collected.ok, true, JSON.stringify(collected));
    assert.equal(collected.reason, "conversation_fabric_completed");
    assert.equal(h.created.length, 2, "recovery must not create a replacement child");
    assert.equal(h.submitted.length, 2, "recovery must never replay the ambiguous bootstrap");
    const completed = await h.context.loadConversationFabricCampaign(started.campaignId);
    assert.equal(completed.results.length, 2);
    assert.equal(completed.failed_children.length, 0);
    const recovered = completed.children.find(child => child.id === "verify");
    assert.equal(recovered.state, "submitted");
    assert.equal(recovered.recovered_submission_ambiguity, true);
  }

  {
    const h = createHarness({
      failChildId: "tests",
      failReason: "spawn_page_not_ready"
    });
    const fourChildMessage = {
      ...h.delegateMessage,
      fingerprint: "c1d2e3f4",
      assistantIdentity: "assistant-four-child-partial-failure",
      control: {
        schema_version: 1,
        action: "delegate",
        marker: "synthetic-four-child-marker",
        children: [
          { id: "logic", role: "research", prompt: "Audit runtime logic." },
          { id: "architecture", role: "integration", prompt: "Audit architecture." },
          { id: "tests", role: "verification", prompt: "Audit verification." },
          { id: "races", role: "verification", prompt: "Audit lifecycle races." }
        ]
      }
    };
    const started = await h.context.applyConversationFabricControl(fourChildMessage, h.sender);
    assert.equal(started.ok, true, JSON.stringify(started));
    assert.equal(started.reason, "conversation_fabric_started");
    assert.equal(h.created.length, 4, "one failed child must not prevent later children from starting");
    assert.ok(
      h.childrenAtSubmit.every(count => count === 4),
      "all requested child records must be durable before the first submit side effect"
    );

    const campaign = await h.context.loadConversationFabricCampaign(started.campaignId);
    assert.deepEqual(
      Array.from(campaign.children, child => child.state),
      ["submitted", "submitted", "failed", "submitted"]
    );
    const failed = campaign.children.find(child => child.id === "tests");
    assert.equal(failed.attempts, 6, "initial submit plus five bounded retries must be recorded");
    assert.equal(failed.last_reason, "spawn_page_not_ready");
    assert.match(failed.last_error, /synthetic failure for tests/);
    assert.equal(campaign.failed_children.length, 1);
    assert.equal(campaign.failed_children[0].id, "tests");
    assert.equal(campaign.failed_children[0].attempt, 6);
    assert.equal(campaign.partial_failure, true);
    assert.match(started.feedbackPrompt, /started 3\/4 reasoning child tab/);
    assert.match(started.feedbackPrompt, /tests: spawn_page_not_ready/);
    assert.equal(h.closed.length, 0, "partial startup failure must not close already-running children");

    const collected = await h.context.applyConversationFabricControl({
      type: "bridge:conversation-fabric-control",
      conversationUrl: parentUrl,
      fingerprint: "d1e2f3a4",
      assistantIdentity: "assistant-four-child-collect",
      contentProtocolVersion: h.context.CONTENT_PROTOCOL_VERSION,
      control: {
        schema_version: 1,
        action: "collect",
        campaign_id: started.campaignId,
        marker: "synthetic-four-child-collect"
      }
    }, h.sender);
    assert.equal(collected.ok, true, JSON.stringify(collected));
    assert.equal(collected.reason, "conversation_fabric_completed");
    assert.equal(h.observed.length, 6, "three successful children require stable double observation");
    assert.equal(h.closed.length, 4, "terminal cleanup closes all owned tabs only after results are captured");
    assert.match(collected.feedbackPrompt, /completed with partial child failures/);
    assert.match(collected.feedbackPrompt, /child tests \(verification\) FAILED/);
    assert.match(collected.feedbackPrompt, /reason=spawn_page_not_ready/);
    assert.match(collected.feedbackPrompt, /Result for tab 101\./);
    assert.match(collected.feedbackPrompt, /Result for tab 102\./);
    assert.match(collected.feedbackPrompt, /Result for tab 104\./);
    const completed = await h.context.loadConversationFabricCampaign(started.campaignId);
    assert.equal(completed.state, "completed");
    assert.equal(completed.results.length, 3);
    assert.equal(completed.failed_children.length, 1);
  }

  {
    const h = createHarness();
    const simultaneous = await Promise.all([
      h.context.applyConversationFabricControl(h.delegateMessage, h.sender),
      h.context.applyConversationFabricControl(h.delegateMessage, h.sender)
    ]);
    assert.ok(simultaneous.every(result => result.ok));
    assert.equal(h.created.length, 2, "concurrent duplicate controls must not create extra children");
    const another = await h.context.applyConversationFabricControl(
      { ...h.delegateMessage, assistantIdentity: "new-delegation" },
      h.sender
    );
    assert.equal(another.reason, "conversation_fabric_parent_busy");
    const restarted = createHarness({ storage: h.session });
    const duplicate = await restarted.context.applyConversationFabricControl(
      restarted.delegateMessage,
      restarted.sender
    );
    assert.equal(duplicate.campaignId, simultaneous[0].campaignId);
    assert.equal(restarted.created.length, 0, "worker restart must preserve campaign ownership and dedupe");
  }

  {
    const h = createHarness();
    const started = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    const campaign = await h.context.loadConversationFabricCampaign(started.campaignId);
    campaign.state = "failed";
    campaign.failure = "submission_ambiguous";
    await h.context.saveConversationFabricCampaign(campaign);
    const result = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    assert.equal(result.ok, false);
    assert.equal(result.reason, "conversation_fabric_failed");
    assert.equal(h.created.length, 2, "failed or interrupted delegations must never replay automatically");
  }

  {
    const h = createHarness();
    h.context.getBridgeState = async () => ({ settings: { masterEnabled: false }, conversations: {} });
    const result = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    assert.equal(result.reason, "conversation_fabric_parent_not_managed");
    assert.equal(h.created.length, 0);
  }

  {
    const h = createHarness();
    const started = await h.context.applyConversationFabricControl(h.delegateMessage, h.sender);
    const campaign = await h.context.loadConversationFabricCampaign(started.campaignId);
    campaign.state = "failed";
    campaign.cleanup_pending = true;
    campaign.children = [...campaign.children, ...campaign.children];
    await h.context.saveConversationFabricCampaign(campaign);
    const result = await h.context.applyConversationFabricControl(
      { ...h.delegateMessage, assistantIdentity: "new-delegation" },
      h.sender
    );
    assert.equal(result.reason, "conversation_fabric_capacity");
    assert.equal(h.created.length, 2, "unclosed failed child tabs must continue to consume the global capacity");
  }

  console.log("Conversation Fabric worker tests passed.");
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
