"use strict";

const assert = require("node:assert/strict");
const { createRetryGate } = require("./content_retry.js");

const retry = createRetryGate({ baseMs: 5000, maxMs: 30000 });
const signature = "assistant-control-a";

assert.equal(retry.canAttempt(signature, 0), true);
assert.equal(retry.defer(signature, 0), 5000);
assert.equal(retry.canAttempt(signature, 4999), false);
assert.equal(retry.canAttempt(signature, 5000), true);

assert.equal(retry.defer(signature, 5000), 10000);
assert.equal(retry.canAttempt(signature, 14999), false);
assert.equal(retry.canAttempt(signature, 15000), true);

assert.equal(retry.defer(signature, 15000), 20000);
assert.equal(retry.canAttempt(signature, 34999), false);
assert.equal(retry.canAttempt(signature, 35000), true);

assert.equal(retry.defer(signature, 35000), 30000);
assert.deepEqual(retry.snapshot(), {
  signature,
  failures: 4,
  notBefore: 65000
});
assert.equal(retry.canAttempt(signature, 64999), false);
assert.equal(retry.canAttempt(signature, 65000), true, "four failures must not exhaust retries");
assert.equal(retry.defer(signature, 65000), 30000, "backoff remains bounded after four failures");
assert.equal(retry.canAttempt(signature, 95000), true, "retry remains live indefinitely");

assert.equal(retry.canAttempt("assistant-control-b", 100), true, "new assistant content resets old backoff");
assert.deepEqual(retry.snapshot(), {
  signature: "assistant-control-b",
  failures: 0,
  notBefore: 0
});

retry.defer("assistant-control-b", 100);
retry.reset("assistant-control-b");
assert.equal(retry.canAttempt("assistant-control-b", 100), true);
assert.equal(retry.snapshot().failures, 0);

assert.throws(() => createRetryGate({ baseMs: 0, maxMs: 1 }), /invalid retry gate bounds/);
assert.throws(() => createRetryGate({ baseMs: 100, maxMs: 99 }), /invalid retry gate bounds/);

console.log("Chat Bridge content retry policy tests passed.");
