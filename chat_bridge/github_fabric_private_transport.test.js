"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const privateReader = require("./github_fabric_private_transport.js");

const SOURCE = [
  "import json",
  "from local_agent.conversation.github_fabric_dispatch import build_github_fabric_dispatch",
  "from tests.test_github_fabric_dispatch import operator_request, admitted_children",
  "print(json.dumps(build_github_fabric_dispatch(operator_request(), admitted_children())))"
].join("\n");
const python = spawnSync(process.env.PYTHON || "python", ["-c", SOURCE], {
  cwd: path.join(__dirname, ".."), encoding: "utf8", maxBuffer: 200000, timeout: 30000
});
assert.equal(python.status, 0, python.stderr || "synthetic dispatch generation failed");
const dispatch = JSON.parse(python.stdout.trim());
const head = "e".repeat(40);
const secret = "github_pat_synthetic_readonly_only_123456";
const prefix = "https://api.github.com/repos/" + privateReader.REPOSITORY;

function jsonResponse(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status, headers: { "Content-Type": "application/vnd.github+json" }
  });
}

function metadata(name, data) {
  const encoded = Buffer.from(JSON.stringify(data), "utf8");
  return {
    type: "file", path: name, size: encoded.length, encoding: "base64",
    content: encoded.toString("base64").replace(/(.{60})/g, "$1\n")
  };
}

function mockTransport(overrides = {}) {
  const calls = [];
  const indexPath = ".agent/conversation/browser_dispatches/index.json";
  const recordPath = ".agent/conversation/browser_dispatches/" + dispatch.id + ".json";
  const state = {
    ref: { ref: "refs/heads/fabric-data", object: { type: "commit", sha: head } },
    index: { schema_version: 1, dispatch_ids: [dispatch.id] },
    record: structuredClone(dispatch),
    ...overrides
  };
  const fetchImpl = async (url, opts) => {
    calls.push({ url, opts });
    assert.ok(url.startsWith(prefix + "/"), "must not route token to another host or repo");
    assert.equal(opts.method, "GET");
    assert.equal(opts.redirect, "error");
    assert.equal(opts.credentials, "omit");
    assert.equal(opts.cache, "no-store");
    assert.equal(opts.headers.Authorization, "Bearer " + secret);
    if (url === prefix + "/git/ref/heads/fabric-data") return jsonResponse(state.ref);
    if (url === prefix + "/contents/" + indexPath + "?ref=" + head) {
      return jsonResponse(metadata(indexPath, state.index));
    }
    if (url === prefix + "/contents/" + recordPath + "?ref=" + head) {
      return jsonResponse(metadata(recordPath, state.record));
    }
    throw new Error("unexpected URL in private GitHub fixture");
  };
  return { fetchImpl, calls, state };
}

async function run() {
  const probe = mockTransport();
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    readToken: secret, expectedId: dispatch.id, fetchImpl: probe.fetchImpl
  }), /default-disabled/);
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: "", expectedId: dispatch.id, fetchImpl: probe.fetchImpl
  }), /authorization missing/);
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: "../escape", fetchImpl: probe.fetchImpl
  }), /expected dispatch identity invalid/);
  assert.equal(probe.calls.length, 0);

  const first = await privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id, fetchImpl: probe.fetchImpl
  });
  assert.equal(first.source, "authenticated_private_github");
  assert.equal(first.source_head_sha, head);
  assert.deepEqual(first.dispatch, dispatch);
  assert.deepEqual(probe.calls.map(x => x.url), [
    prefix + "/git/ref/heads/fabric-data",
    prefix + "/contents/.agent/conversation/browser_dispatches/index.json?ref=" + head,
    prefix + "/contents/.agent/conversation/browser_dispatches/" + dispatch.id + ".json?ref=" + head
  ]);
  const second = await privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id, fetchImpl: probe.fetchImpl
  });
  assert.deepEqual(second, first);
  assert.equal(probe.calls.length, 6);

  const changed = mockTransport();
  changed.state.record.children[0].spawn.bootstrap_text += "\nPRIVATE CHANGED";
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id, fetchImpl: changed.fetchImpl
  }), /bootstrap digest conflict/);
  const switched = mockTransport();
  switched.state.record.children[0].spawn.transaction_id = "spawn-" + "b".repeat(64);
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id, fetchImpl: switched.fetchImpl
  }), /spawn transaction conflict/);
  const unindexed = mockTransport({ index: { schema_version: 1, dispatch_ids: [] } });
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id, fetchImpl: unindexed.fetchImpl
  }), /not indexed/);
  assert.equal(unindexed.calls.length, 2);
  const stale = mockTransport({
    ref: { ref: "refs/heads/fabric-data", object: { type: "commit", sha: "notasha" } }
  });
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id, fetchImpl: stale.fetchImpl
  }), /origin ref rejected/);
  assert.equal(stale.calls.length, 1);

  const denied = await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id,
    fetchImpl: async () => jsonResponse({ message: "Unauthorized" }, 403)
  }), /source response rejected/);
  assert.equal(denied, undefined);
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id,
    fetchImpl: async () => { throw new Error("network error " + secret); }
  }), error => !String(error).includes(secret) && /network read failed/.test(String(error)));

  const oversized = new ReadableStream({
    start(controller) {
      controller.enqueue(new Uint8Array(9000));
      controller.enqueue(new Uint8Array(9000));
      controller.close();
    }
  });
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id,
    fetchImpl: async () => ({ status: 200, redirected: false, url: "", body: oversized })
  }), /exceeds bound/);
  const redirect = mockTransport();
  await assert.rejects(privateReader.readPrivateDispatchSnapshot({
    enabled: true, readToken: secret, expectedId: dispatch.id,
    fetchImpl: async () => ({
      status: 200, redirected: true, url: "https://evil.invalid/",
      body: jsonResponse({}).body
    })
  }), /response rejected/);
  assert.equal(redirect.calls.length, 0);

  // The source credentials never enter logs, runtime JSON, or child messages;
  // production worker does not import this model.
  assert.ok(privateReader.REPOSITORY.endsWith("local-agent-fabric-private"));
  assert.equal(typeof privateReader.spawn, "undefined");
  assert.equal(typeof privateReader.publish, "undefined");
  assert.equal(typeof privateReader.writeToken, "undefined");
  assert.equal(
    crypto.createHash("sha256").update(dispatch.children[0].spawn.bootstrap_text).digest("hex"),
    dispatch.children[0].spawn.bootstrap_digest.slice(7)
  );
  console.log("Disabled private GitHub Fabric pinned-read contract passed.");
}

run().catch(error => { console.error(error); process.exitCode = 1; });
