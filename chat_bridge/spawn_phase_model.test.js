"use strict";

const assert = require("node:assert/strict");
const model = require("./spawn_phase_model.js");

const identity = Object.freeze({
  transaction_id: "spawn-" + "a".repeat(64),
  child_request_digest: "sha256:" + "b".repeat(64),
  bootstrap_digest: "sha256:" + "c".repeat(64)
});

const prepared = model.newPreparedClaim(identity);
assert.equal(prepared.phase, "prepared");
assert.equal(prepared.schema_version, 2);
assert.equal(model.reconcileClaim(null, identity).action, "prepare_new");
assert.equal(model.reconcileClaim(prepared, identity).action, "resume_before_arm");
assert.equal(model.assertBeforeComposerMutation(prepared, identity), true);
assert.equal(model.canRetry(prepared), true);
assert.throws(() => model.assertBeforeSend(prepared, identity), /submit_armed/);

const draft = model.advanceClaim(prepared, "draft_verified");
assert.equal(draft.phase, "draft_verified");
assert.equal(model.canRetry(draft), true);
assert.throws(() => model.assertBeforeComposerMutation(draft, identity), /prepared/);
assert.equal(model.advanceClaim(draft, "draft_verified"), draft);
assert.throws(() => model.advanceClaim(draft, "response_started"), /monotonic/);

const retry = model.retryClaim(draft);
assert.equal(retry.phase, "prepared");
assert.equal(retry.attempt, 2);
assert.equal(model.assertBeforeComposerMutation(retry, identity), true);

const armed = model.advanceClaim(draft, "submit_armed");
assert.equal(model.reconcileClaim(armed, identity).action, "reconcile_only");
assert.equal(model.canRetry(armed), false);
assert.equal(model.assertBeforeSend(armed, identity), true);
assert.throws(() => model.retryClaim(armed), /forbidden/);
assert.throws(() => model.advanceClaim(armed, "draft_verified"), /monotonic/);
assert.throws(() => model.assertBeforeComposerMutation(armed, identity), /prepared/);

const submitted = model.advanceClaim(armed, "submitted");
assert.equal(model.reconcileClaim(submitted, identity).action, "reconcile_only");
assert.throws(() => model.assertBeforeSend(submitted, identity), /submit_armed/);
assert.throws(() => model.retryClaim(submitted), /forbidden/);
const response = model.advanceClaim(submitted, "response_started");
assert.equal(model.reconcileClaim(response, identity).action, "reconcile_only");
assert.throws(() => model.retryClaim(response), /forbidden/);
assert.equal(model.advanceClaim(response, "response_started"), response);
assert.throws(() => model.advanceClaim(response, "prepared"), /monotonic/);
assert.throws(() => model.advanceClaim(response, "unknown"), /unknown/);

for (const changed of [
  { ...identity, transaction_id: "spawn-" + "d".repeat(64) },
  { ...identity, child_request_digest: "sha256:" + "d".repeat(64) },
  { ...identity, bootstrap_digest: "sha256:" + "d".repeat(64) }
]) {
  assert.throws(() => model.reconcileClaim(prepared, changed), /permanent/);
  assert.throws(() => model.assertBeforeSend(armed, changed), /permanent/);
}
for (const malformed of [
  { ...prepared, tab_id: 12 },
  { ...prepared, phase: "submitting" },
  { ...prepared, attempt: 0 },
  { ...prepared, attempt: 1.5 },
  { ...prepared, schema_version: 1 },
  { ...prepared, child_request_digest: "bad" }
]) {
  assert.throws(() => model.validateClaim(malformed));
}
assert.throws(() => model.newPreparedClaim({ ...identity, tab_id: 123, bootstrap_digest: "bad" }));
assert.throws(() => model.retryClaim({ ...draft, attempt: 32 }), /limit/);

console.log("Page-local spawn phase v2 model tests passed.");
