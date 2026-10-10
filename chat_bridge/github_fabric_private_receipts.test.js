"use strict";

const assert = require("node:assert/strict");
const receipts = require("./github_fabric_private_receipts.js");

const dispatch = {
  schema_version: 1, operation: "delegate", id: "fabric-" + "a".repeat(32),
  request_id: "operator-request-001", request_digest: "sha256:" + "b".repeat(64),
  campaign_id: "cf-" + "c".repeat(16),
  parent_conversation_url: "https://chatgpt.com/c/example-parent",
  children: [{
    id: "child-verify", request_id: "child-verify", role: "verification",
    spawn: {
      schema_version: 1, transaction_id: "spawn-" + "d".repeat(64),
      child_request_digest: "sha256:" + "e".repeat(64),
      bootstrap_digest: "sha256:" + "f".repeat(64),
      bootstrap_text: "Verified bounded child bootstrap."
    }
  }]
};
const token = "github_pat_test_private_receipt_token";
const childRequestId = "child-verify";
const childConversationUrl = "https://chatgpt.com/c/test-owned-child";

function response(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status, headers: { "Content-Type": "application/json" }
  });
}
function fakeGitHub({ lostAck = false } = {}) {
  const records = new Map();
  const calls = [];
  let lost = lostAck;
  const fetchImpl = async (url, opts) => {
    assert.ok(url.startsWith(receipts.API + "/contents/projects/local-agent/"));
    assert.equal(opts.headers.Authorization, "Bearer " + token);
    assert.equal(opts.redirect, "error");
    assert.equal(opts.credentials, "omit");
    assert.equal(opts.cache, "no-store");
    calls.push({ url, method: opts.method });
    const path = url.slice((receipts.API + "/contents/").length).split("?")[0];
    if (opts.method === "GET") {
      assert.ok(url.endsWith("?ref=fabric-data"));
      const value = records.get(path);
      if (!value) return response({ message: "Not Found" }, 404);
      const encoded = Buffer.from(JSON.stringify(value), "utf8");
      return response({
        type: "file", path, encoding: "base64",
        content: encoded.toString("base64"), size: encoded.length
      });
    }
    assert.equal(opts.method, "PUT");
    const body = JSON.parse(opts.body);
    assert.equal(body.branch, "fabric-data");
    const value = JSON.parse(Buffer.from(body.content, "base64").toString("utf8"));
    if (records.has(path)) return response({ message: "conflict" }, 422);
    records.set(path, value);
    if (lost) {
      lost = false;
      throw new Error("transport interrupted after accepted PUT with secret " + token);
    }
    return response({ content: { path } }, 201);
  };
  return { records, calls, fetchImpl };
}

async function test() {
  const empty = fakeGitHub();
  await assert.rejects(receipts.publishBrowserAck({
    writeToken: token, fetchImpl: empty.fetchImpl, dispatch,
    childRequestId, childConversationUrl
  }), /disabled/);
  assert.equal(empty.calls.length, 0);

  await assert.rejects(receipts.publishBrowserAck({
    enabled: true, writeToken: token, fetchImpl: empty.fetchImpl, dispatch,
    childRequestId: "../secret", childConversationUrl
  }), /identity invalid/);
  assert.equal(empty.calls.length, 0);

  const source = fakeGitHub();
  const args = {
    enabled: true, writeToken: token, fetchImpl: source.fetchImpl,
    dispatch, childRequestId, childConversationUrl
  };
  await assert.rejects(receipts.publishBrowserResult({
    ...args, assistantIdentity: "reply-001", assistantText: "E2E finished"
  }), /requires matching durable ACK/);
  const ack = await receipts.publishBrowserAck(args);
  assert.equal(ack.status, "created");
  assert.equal((await receipts.publishBrowserAck(args)).status, "replay");
  assert.equal(source.calls.filter(x => x.method === "PUT").length, 1);
  const terminal = await receipts.publishBrowserResult({
    ...args, assistantIdentity: "reply-001", assistantText: "E2E finished"
  });
  assert.equal(terminal.status, "created");
  assert.equal((await receipts.publishBrowserResult({
    ...args, assistantIdentity: "reply-001", assistantText: "E2E finished"
  })).status, "replay");
  assert.equal(source.records.size, 2);

  await assert.rejects(receipts.publishBrowserResult({
    ...args, assistantIdentity: "reply-001", assistantText: "Different result"
  }), /immutable identity conflict/);
  await assert.rejects(receipts.publishBrowserAck({
    ...args, childConversationUrl: "https://chatgpt.com/c/wrong-tab"
  }), /immutable identity conflict/);

  const ambiguous = fakeGitHub({ lostAck: true });
  const converged = await receipts.publishBrowserAck({ ...args, fetchImpl: ambiguous.fetchImpl });
  assert.equal(converged.status, "converged");
  assert.equal(ambiguous.calls.filter(x => x.method === "PUT").length, 1);

  const unavailable = fakeGitHub();
  const original = unavailable.fetchImpl;
  unavailable.fetchImpl = async (url, opts) =>
    opts.method === "PUT" ? (() => { throw Error("lost response " + token); })() :
      original(url, opts);
  const unknown = await receipts.publishBrowserAck({
    ...args, fetchImpl: unavailable.fetchImpl
  });
  assert.equal(unknown.status, "ambiguous");
  assert.equal(unavailable.calls.filter(x => x.method === "PUT").length, 0);

  console.log("Private Fabric browser receipt CAS/no-replay contract passed.");
}

test().catch(error => { console.error(error); process.exitCode = 1; });
