"use strict";

const assert = require("node:assert/strict");
const cryptoModule = require("node:crypto");
const fs = require("node:fs");
if (!globalThis.crypto?.subtle) globalThis.crypto = cryptoModule.webcrypto;
const reader = require("./github_fabric_private_parent_ownership_reader.js");
const API = "https://api.github.com/repos/MichalMatu/local-agent-fabric-private";
const BASE = "projects/local-agent/parent_ownership/";
const PARENT = "https://chatgpt.com/c/parent-candidate-001";
const DISPATCH_1 = "fabric-" + "a".repeat(32);
const DISPATCH_2 = "fabric-" + "b".repeat(32);
const OWNER_1 = "1".repeat(32);
const OWNER_2 = "2".repeat(32);
const TOKEN = "private_scoped_token_for_synthetic_tests_123";
const HEAD = "a".repeat(40);
const TREE = "b".repeat(40);
const hash = value => cryptoModule.createHash("sha256").update(value).digest("hex");
const PARENT_ID = "parent-" + hash(JSON.stringify([
  "fabric-global-parent-mode-v1", PARENT
])).slice(0, 32);

function shaBlob(text) {
  const bytes = Buffer.from(text, "utf8");
  return cryptoModule.createHash("sha1").update(
    Buffer.concat([Buffer.from("blob " + bytes.length + "\0"), bytes])
  ).digest("hex");
}
function jsonText(value) { return JSON.stringify(value) + "\n"; }
function response(value, status = 200) {
  return new Response(JSON.stringify(value), { status });
}
function parent(epoch, phase, dispatchId, ownerId) {
  return {
    schema_version: 1, kind: "private_parent_ownership_candidate_v1",
    id: PARENT_ID, parent_conversation_url: PARENT,
    fence_epoch: epoch, owner_id: ownerId, dispatch_id: dispatchId,
    phase, completion: ({ active: "none", completed: "verified",
      unknown_frozen: "unresolved" })[phase]
  };
}
function epochPath(epoch) {
  return BASE + "epochs/" + PARENT_ID + "/" + String(epoch).padStart(4, "0") + ".json";
}
function fixture(epoch = 1, phase = "active") {
  const records = new Map();
  const current = parent(epoch, phase, epoch === 1 ? DISPATCH_1 : DISPATCH_2,
    epoch === 1 ? OWNER_1 : OWNER_2);
  const history = {
    schema_version: 1, parent_id: PARENT_ID,
    entries: epoch === 1
      ? [{ epoch: 1, dispatch_id: DISPATCH_1, owner_id: OWNER_1 }]
      : [{ epoch: 1, dispatch_id: DISPATCH_1, owner_id: OWNER_1 },
        { epoch: 2, dispatch_id: DISPATCH_2, owner_id: OWNER_2 }]
  };
  records.set(BASE + "index.json", { schema_version: 1, parent_ids: [PARENT_ID] });
  records.set(BASE + PARENT_ID + ".json", current);
  records.set(BASE + "history/" + PARENT_ID + ".json", history);
  records.set(epochPath(1), parent(1, "active", DISPATCH_1, OWNER_1));
  if (epoch === 2) records.set(epochPath(2), parent(2, "active", DISPATCH_2, OWNER_2));
  const calls = [];
  const state = { records, blobs: new Map(), entries: [], calls, failedStatus: 0,
    head: HEAD, tree: TREE, treeTruncated: false, tamper: false };
  function resign() {
    state.blobs.clear();
    for (const [path, value] of state.records) {
      state.blobs.set(path, shaBlob(jsonText(value)));
    }
    const dirs = ["projects/local-agent/parent_ownership",
      "projects/local-agent/parent_ownership/history",
      "projects/local-agent/parent_ownership/epochs",
      "projects/local-agent/parent_ownership/epochs/" + PARENT_ID];
    state.entries = [
      ...dirs.map(path => ({ path, type: "tree", mode: "040000", sha: "f".repeat(40) })),
      ...[...state.blobs].map(([path, sha]) =>
        ({ path, type: "blob", mode: "100644", sha }))
    ];
  }
  resign();
  async function fetchImpl(url, options) {
    calls.push(url);
    assert.ok(url.startsWith(API + "/"));
    assert.equal(options.method, "GET");
    assert.equal(options.credentials, "omit");
    assert.equal(options.redirect, "error");
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers.Authorization, "Bearer " + TOKEN);
    assert.ok(options.signal instanceof AbortSignal);
    if (state.failedStatus) return response({ message: "denied" }, state.failedStatus);
    if (url === API + "/git/ref/heads/fabric-data") {
      return response({ ref: "refs/heads/fabric-data",
        object: { type: "commit", sha: state.head } });
    }
    if (url === API + "/git/commits/" + HEAD) {
      return response({ tree: { sha: state.tree } });
    }
    if (url === API + "/git/trees/" + TREE + "?recursive=1") {
      return response({ sha: state.tree, truncated: state.treeTruncated, tree: state.entries });
    }
    const prefix = API + "/contents/";
    if (url.startsWith(prefix) && url.endsWith("?ref=" + HEAD)) {
      const path = url.slice(prefix.length, -("?ref=" + HEAD).length);
      const value = state.records.get(path);
      if (value === undefined) throw Error("unexpected Contents path");
      const bytes = Buffer.from(jsonText(value), "utf8");
      return response({
        type: "file", path, encoding: "base64",
        sha: state.blobs.get(path), size: bytes.length,
        content: bytes.toString("base64")
      });
    }
    throw Error("Unexpected GitHub request");
  }
  const read = (extra = {}) => reader.readPrivateParentOwnershipSnapshot({
    enabled: true, readToken: TOKEN, parentConversationUrl: PARENT,
    expectedOwnerId: epoch === 1 ? OWNER_1 : OWNER_2,
    expectedDispatchId: epoch === 1 ? DISPATCH_1 : DISPATCH_2,
    expectedEpoch: epoch, fetchImpl, ...extra
  });
  return { state, read, resign };
}

async function run() {
  assert.equal(await reader.parentId(PARENT), PARENT_ID);
  const one = fixture();
  assert.equal((await one.read()).status, "matching_active_candidate");
  assert.equal((await one.read()).observed_epoch, 1);
  const approved = await one.read();
  assert.equal(approved.source_head_sha, HEAD);
  assert.equal(approved.parent_id, PARENT_ID);
  assert.equal(approved.browser_effects_permitted, false);
  assert.equal(approved.source, "authenticated_private_parent_candidate_observation");
  assert.equal(Object.keys(approved).includes("owner_id"), false);
  assert.ok(!JSON.stringify(approved).includes(TOKEN));
  assert.equal((await one.read({ expectedOwnerId: OWNER_2 })).status,
    "competing_or_stale_candidate");
  assert.equal((await one.read({ expectedEpoch: 2 })).status,
    "competing_or_stale_candidate");
  assert.equal((await one.read({ expectedDispatchId: DISPATCH_2 })).status,
    "competing_or_stale_candidate");
  const two = fixture(2);
  assert.equal((await two.read()).status, "matching_active_candidate");
  assert.equal((await two.read({ expectedOwnerId: OWNER_1 })).status,
    "competing_or_stale_candidate");
  assert.equal((await two.read({ expectedEpoch: 1 })).status,
    "competing_or_stale_candidate");
  assert.equal((await fixture(1, "completed").read()).status,
    "matching_completed_candidate");
  assert.equal((await fixture(2, "unknown_frozen").read()).status,
    "matching_frozen_candidate");

  const notEnabled = fixture();
  await assert.rejects(notEnabled.read({ enabled: false }), /default-disabled/);
  await assert.rejects(notEnabled.read({ readToken: null }), /read token invalid/);
  for (const url of ["http://chatgpt.com/c/id", PARENT + "/",
    PARENT + "?token=unsafe", "https://chatgpt.com/c/../escape"]) {
    await assert.rejects(notEnabled.read({ parentConversationUrl: url }),
      /expected identity invalid/);
  }
  await assert.rejects(notEnabled.read({ expectedOwnerId: [OWNER_1] }),
    /expected identity invalid/);
  await assert.rejects(notEnabled.read({ expectedEpoch: true }),
    /expected identity invalid/);
  await assert.rejects(notEnabled.read({ expectedDispatchId: "bad" }),
    /expected identity invalid/);
  assert.equal(notEnabled.state.calls.length, 0, "bad admission never uses GitHub");

  const missing = fixture();
  missing.state.records.clear();
  missing.state.entries = [];
  assert.equal((await missing.read()).status, "unregistered");

  const unrelated = fixture();
  unrelated.state.records.set(BASE + "index.json", {
    schema_version: 1, parent_ids: ["parent-" + "0".repeat(32)]
  });
  const other = "parent-" + "0".repeat(32);
  unrelated.state.records.delete(BASE + PARENT_ID + ".json");
  unrelated.state.records.delete(BASE + "history/" + PARENT_ID + ".json");
  unrelated.state.records.delete(epochPath(1));
  unrelated.state.records.set(BASE + other + ".json",
    { ...parent(1, "active", DISPATCH_1, OWNER_1), id: other });
  unrelated.state.records.set(BASE + "history/" + other + ".json", {
    schema_version: 1, parent_id: other, entries: [{
      epoch: 1, dispatch_id: DISPATCH_1, owner_id: OWNER_1
    }]
  });
  unrelated.resign();
  assert.equal((await unrelated.read()).status, "unregistered");

  async function invalid(mutator, error) {
    const f = fixture(2);
    mutator(f);
    await assert.rejects(f.read(), error);
  }
  await invalid(f => {
    f.state.records.get(BASE + "index.json").parent_ids.push(PARENT_ID);
    f.resign();
  }, /index invalid/);
  await invalid(f => {
    f.state.records.get(BASE + PARENT_ID + ".json").fence_epoch = 1;
    f.resign();
  }, /current owner conflicts/);
  await invalid(f => {
    f.state.records.get(BASE + PARENT_ID + ".json").phase = "completed";
    f.resign();
  }, /ownership record invalid/);
  await invalid(f => {
    f.state.records.get(BASE + "history/" + PARENT_ID + ".json")
      .entries[1].owner_id = OWNER_1;
    f.resign();
  }, /epoch identity conflict/);
  await invalid(f => {
    f.state.records.get(epochPath(1)).owner_id = OWNER_2;
    f.resign();
  }, /immutable epoch witness conflict/);
  await invalid(f => {
    f.state.records.delete(epochPath(1));
    f.resign();
  }, /epoch witness count conflict/);
  await invalid(f => {
    f.state.records.set(epochPath(3), parent(2, "active", DISPATCH_2, OWNER_2));
    f.resign();
  }, /epoch witness count conflict/);
  await invalid(f => {
    f.state.records.delete(BASE + "history/" + PARENT_ID + ".json");
    f.resign();
  }, /indexed record\/history missing/);
  await invalid(f => {
    f.state.records.set(BASE + "parent-" + "0".repeat(32) + ".json",
      parent(1, "active", DISPATCH_1, OWNER_1));
    f.resign();
  }, /orphan owner/);
  await invalid(f => {
    f.state.records.set(BASE + "secrets.json", { unsafe: true });
    f.resign();
  }, /unexpected or duplicate tree entry/);
  await invalid(f => {
    f.state.entries.push({ ...f.state.entries.find(
      entry => entry.path === BASE + PARENT_ID + ".json") });
  }, /unexpected or duplicate tree entry/);
  await invalid(f => {
    f.state.entries.find(entry => entry.path === epochPath(1)).mode = "120000";
  }, /unexpected or duplicate tree entry/);
  await invalid(f => {
    f.state.treeTruncated = true;
  }, /tree incomplete/);
  await invalid(f => {
    f.state.head = "not-a-SHA";
  }, /ref invalid/);
  await invalid(f => {
    f.state.records.get(BASE + PARENT_ID + ".json").owner_id = OWNER_1;
    // Do not update signed tree/Contents blob SHA.
  }, /pinned blob digest mismatch/);
  const denied = fixture();
  denied.state.failedStatus = 403;
  await assert.rejects(denied.read(), /response rejected/);
  const errorFixture = fixture();
  await assert.rejects(errorFixture.read({
    fetchImpl: async () => { throw Error("token " + TOKEN); }
  }), error => !String(error).includes(TOKEN) && /network unavailable/.test(String(error)));

  const responseSource = fs.readFileSync(require("node:path").join(__dirname, "service_worker.js"), "utf8");
  assert.ok(!responseSource.includes("github_fabric_private_parent_ownership_reader.js"),
    "candidate reader must not be imported by installed service worker");
  assert.equal(typeof reader.authorizeSend, "undefined");
  assert.equal(typeof reader.commit, "undefined");
  assert.equal(typeof reader.spawn, "undefined");
  assert.equal(typeof reader.publish, "undefined");
  console.log("Private parent ownership pinned read-only candidate tests passed.");
}
run().catch(error => { console.error(error); process.exitCode = 1; });
