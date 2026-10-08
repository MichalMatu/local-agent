"use strict";

// Cross-language, synthetic-only publication -> browser read-only intake proof.
// This test never opens Chrome or accesses a network, and proves no spawn action.
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const dispatchModel = require("./github_fabric_dispatch_model.js");
const intakeModel = require("./github_fabric_intake_model.js");

const source = [
  "import json",
  "from tests.test_github_fabric_dispatch import operator_request, admitted_children",
  "from local_agent.conversation.github_fabric_publication import preflight_synthetic_publication",
  "op = operator_request()",
  "children = admitted_children()",
  "args = dict(enabled=True, writer_authorized=True, expected_head_sha='a'*40)",
  "first = preflight_synthetic_publication(op, children, existing_record=None, existing_index=None, **args)",
  "second = preflight_synthetic_publication(op, children, existing_record=first.payload, existing_index=None, **args)",
  "print(json.dumps({'dispatch': first.payload, 'record_path': first.path, 'index': second.payload, 'index_path': second.path}))"
].join("\n");

const result = spawnSync(process.env.PYTHON || "python", ["-c", source], {
  cwd: path.resolve(__dirname, ".."),
  encoding: "utf8",
  timeout: 30000,
  maxBuffer: 256 * 1024
});
assert.equal(result.status, 0, "Python fixture preflight must succeed: " + result.stderr);

const fixture = JSON.parse(result.stdout.trim());
const dispatch = dispatchModel.validateDispatch(fixture.dispatch);
const index = intakeModel.validateIndex(fixture.index);
assert.equal(fixture.record_path,
  ".agent/conversation/browser_dispatches/" + dispatch.id + ".json");
assert.equal(fixture.index_path, ".agent/conversation/browser_dispatches/index.json");
assert.deepEqual(index.dispatch_ids, [dispatch.id]);

for (const child of dispatch.children) {
  const intent = dispatchModel.toConversationSpawnIntent(child);
  assert.equal(intent.tab_id, null);
  const digest = "sha256:" + crypto.createHash("sha256")
    .update(intent.bootstrap_text, "utf8").digest("hex");
  assert.equal(intent.bootstrap_digest, digest);
}

const seen = {};
const fingerprint = crypto.createHash("sha256")
  .update(dispatchModel.canonicalJson(dispatch), "utf8").digest("hex");
const first = intakeModel.reconcileSeenDispatch(seen, dispatch.id, fingerprint);
assert.equal(first.status, "stored");
assert.equal(intakeModel.reconcileSeenDispatch(first.seen, dispatch.id, fingerprint).status, "replayed");
assert.equal(Object.keys(first.seen).length, 1);

console.log("Synthetic Python publication to JS read-only intake contract passed.");
