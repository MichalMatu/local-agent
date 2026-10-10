"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");

const source = fs.readFileSync(__dirname + "/worker_github_fabric_private_live.js", "utf8");
const parent = "https://chatgpt.com/c/private-trial-parent";
const childUrl = "https://chatgpt.com/c/private-trial-child";
const dispatchId = "fabric-" + "a".repeat(32);
const token = "github_pat_scoped_only_in_extension";
const intent = {
  schema_version: 1, transaction_id: "spawn-" + "b".repeat(64),
  child_request_digest: "sha256:" + "c".repeat(64),
  bootstrap_digest: "sha256:" + "d".repeat(64),
  bootstrap_text: "Bounded test child bootstrap", tab_id: null
};
const dispatch = {
  id: dispatchId, parent_conversation_url: parent,
  children: [{ request_id: "child-1" }]
};

function fixture({ unknownSend = false, enabled = true, existingLocal = null, existingSession = null } = {}) {
  const local = existingLocal || {};
  const session = existingSession || {};
  const counts = { claim: 0, tabs: 0, submit: 0, reconcile: 0, ack: 0, result: 0, legacy: 0 };
  let ready = false;
  const storage = data => ({
    async get(key) {
      return typeof key === "string"
        ? Object.hasOwn(data, key) ? { [key]: data[key] } : {}
        : structuredClone(data);
    },
    async set(value) { Object.assign(data, structuredClone(value)); },
    async remove(key) { delete data[key]; }
  });
  const ctx = {
    crypto: webcrypto, console,
    chrome: {
      storage: { local: storage(local), session: storage(session) },
      tabs: { async get(id) { return { id, url: parent }; } }
    },
    LocalAgentPrivateFabricTransport: {
      async readPrivateDispatchSnapshot({ expectedId, readToken, enabled }) {
        assert.equal(expectedId, dispatchId);
        assert.equal(readToken, token);
        assert.equal(enabled, true);
        return { dispatch, source_head_sha: "e".repeat(40) };
      }
    },
    LocalAgentPrivateFabricReceipts: {
      async claimBrowserChild({ ownerId, writeToken }) {
        assert.equal(ownerId.length, 32);
        assert.equal(writeToken, token);
        counts.claim++;
        return { status: "created" };
      },
      async publishBrowserAck({ childConversationUrl }) {
        assert.equal(childConversationUrl, childUrl);
        counts.ack++;
        return { status: "created" };
      },
      async publishBrowserResult({ assistantText, childConversationUrl }) {
        assert.equal(childConversationUrl, childUrl);
        assert.equal(assistantText, "BRIDGE_TEST_FINISHED");
        counts.result++;
        return { status: "created", path: "projects/local-agent/workflows/workflow-001/receipts/result.json" };
      }
    },
    githubFabricDispatchModel: {
      toConversationSpawnIntent: () => structuredClone(intent)
    },
    async getBridgeState() {
      return {
        settings: { masterEnabled: enabled },
        conversations: { parent: { enabled: true, url: parent, preferredTabId: 44 } }
      };
    },
    conversationId: () => "parent",
    normalizeConversationUrl: value => value,
    async fetchRuntime() { return { source: "remote" }; },
    githubControlModel: {
      findConversationControl: () => ({ enabled: true }),
      controlMatchesConversation: () => true
    },
    async listConversationFabricCampaigns() { return []; },
    async requireConversationSpawnBootstrapDigest() {},
    async createConversationSpawnTab() {
      counts.tabs++;
      return { ok: true, tabId: 55 };
    },
    async submitConversationSpawnBootstrap(current) {
      counts.submit++;
      assert.equal(current.tab_id, 55);
      return unknownSend ? { ok: false, reason: "spawn_submission_ambiguous" }
        : { ok: true, childConversationUrl: childUrl };
    },
    async reconcileConversationSpawn() {
      counts.reconcile++;
      return { ok: false, reason: "spawn_submission_ambiguous" };
    },
    async stableConversationFabricResult() {
      return ready
        ? { ok: true, reason: "child_result_ready", childConversationUrl: childUrl,
            assistantIdentity: "assistant-1", assistantText: "BRIDGE_TEST_FINISHED" }
        : { ok: true, reason: "child_generating", childConversationUrl: childUrl };
    },
    async applyConversationFabricControl() {
      counts.legacy++;
      return { ok: true, reason: "legacy_allowed" };
    }
  };
  vm.createContext(ctx);
  vm.runInContext(source, ctx, { filename: "worker_github_fabric_private_live.js" });
  return { ctx, counts, local, session, setReady: () => { ready = true; } };
}

async function test() {
  const staged = fixture();
  let snapshot = await staged.ctx.privateFabricDraftStatus();
  assert.equal(snapshot.ok, true);
  assert.equal(snapshot.tokenSaved, false);
  assert.equal(snapshot.dispatchId, "");
  assert.equal((await staged.ctx.operatorSavePrivateFabricDispatch({ dispatchId: "invalid" })).ok, false);
  snapshot = await staged.ctx.operatorSavePrivateFabricDispatch({ dispatchId });
  assert.equal(snapshot.dispatchId, dispatchId);
  assert.equal(snapshot.tokenSaved, false);
  snapshot = await staged.ctx.operatorSavePrivateFabricToken({ writeToken: token });
  assert.equal(snapshot.tokenSaved, true);
  assert.equal(snapshot.tokenLastFour, token.slice(-4));
  assert.ok(!JSON.stringify(staged.local).includes(token), "saved token must never enter local storage");
  assert.ok(!JSON.stringify(snapshot).includes(token), "status must never expose token");

  // Closing the popup and suspending/restarting the worker must not clear the
  // independently saved ID or Chrome-session credential.
  const reopened = fixture({ existingLocal: staged.local, existingSession: staged.session });
  snapshot = await reopened.ctx.privateFabricDraftStatus();
  assert.equal(snapshot.dispatchId, dispatchId);
  assert.equal(snapshot.tokenSaved, true);
  const submitted = await reopened.ctx.operatorStartPrivateFabricTrial({});
  assert.equal(submitted.phase, "running");
  assert.equal(reopened.counts.submit, 1);
  assert.equal((await reopened.ctx.operatorForgetPrivateFabricToken()).ok, false);
  reopened.setReady();
  await reopened.ctx.pollPrivateFabricTrial();
  assert.equal((await reopened.ctx.privateFabricDraftStatus()).tokenSaved, false);
  assert.equal(reopened.counts.result, 1);
  assert.equal((await reopened.ctx.operatorStartPrivateFabricTrial({})).ok, false);
  await reopened.ctx.retirePrivateFabricTrial();
  assert.equal((await reopened.ctx.operatorForgetPrivateFabricToken()).ok, true);

  const afterBrowserRestart = fixture({ existingLocal: staged.local, existingSession: {} });
  snapshot = await afterBrowserRestart.ctx.privateFabricDraftStatus();
  assert.equal(snapshot.dispatchId, dispatchId);
  assert.equal(snapshot.tokenSaved, false);

  const f = fixture();
  let value = await f.ctx.operatorStartPrivateFabricTrial({
    dispatchId, writeToken: token
  });
  assert.equal(value.ok, true);
  assert.equal(value.phase, "running");
  assert.equal(f.counts.submit, 1);
  assert.equal(f.counts.claim, 1);
  assert.equal(f.counts.ack, 1);
  assert.equal(f.counts.result, 0);
  assert.ok(!JSON.stringify(f.local).includes(token), "token may not persist in local storage");
  assert.ok(JSON.stringify(f.session).includes(token), "token is extension-session only");
  let fenced = await f.ctx.applyConversationFabricControl({
    conversationUrl: parent, control: { action: "delegate" }
  });
  assert.equal(fenced.reason, "github_first_parent_fenced");
  assert.equal(f.counts.legacy, 0);
  value = await f.ctx.operatorStartPrivateFabricTrial({ dispatchId, writeToken: token });
  assert.equal(value.phase, "running");
  assert.equal(f.counts.submit, 1, "repeated popup click must not repeat Submit");
  f.setReady();
  value = await f.ctx.pollPrivateFabricTrial();
  assert.equal(value.phase, "completed");
  assert.equal(f.counts.result, 1);
  assert.equal(f.session.privateFabricLiveTokenV1, undefined);
  await f.ctx.pollPrivateFabricTrial();
  assert.equal(f.counts.result, 1, "no result replay after completion");
  assert.equal(f.counts.submit, 1);
  assert.equal((await f.ctx.retirePrivateFabricTrial()).phase, "retired");
  fenced = await f.ctx.applyConversationFabricControl({
    conversationUrl: parent, control: { action: "delegate" }
  });
  assert.equal(fenced.reason, "legacy_allowed");
  assert.equal(f.counts.legacy, 1);

  const ambiguous = fixture({ unknownSend: true });
  value = await ambiguous.ctx.operatorStartPrivateFabricTrial({
    dispatchId, writeToken: token
  });
  assert.equal(value.phase, "submission_unknown");
  await ambiguous.ctx.pollPrivateFabricTrial();
  await ambiguous.ctx.operatorStartPrivateFabricTrial({ dispatchId, writeToken: token });
  assert.equal(ambiguous.counts.submit, 1,
    "unknown Send must not be repeated by alarm or explicit popup action");
  assert.ok(ambiguous.counts.reconcile >= 2);
  assert.equal(ambiguous.counts.ack, 0);
  assert.equal((await ambiguous.ctx.retirePrivateFabricTrial()).ok, false);

  const disabled = fixture({ enabled: false });
  value = await disabled.ctx.operatorStartPrivateFabricTrial({
    dispatchId, writeToken: token
  });
  assert.equal(value.ok, false);
  assert.equal(disabled.counts.claim, 0);
  assert.equal(disabled.counts.tabs, 0);
  assert.equal(disabled.counts.submit, 0);
  assert.equal(Object.keys(disabled.local).length, 0);

  console.log("Private GitHub-first worker real-controller fake UI no-replay contract passed.");
}

test().catch(error => { console.error(error); process.exitCode = 1; });
