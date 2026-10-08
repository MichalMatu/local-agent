"use strict";

const assert = require("node:assert/strict");
const model = require("./spawn_phase_model.js");
const phases = require("./spawn_phase_storage.js");

const intent = Object.freeze({
  transaction_id: "spawn-" + "a".repeat(64),
  child_request_digest: "sha256:" + "b".repeat(64),
  bootstrap_digest: "sha256:" + "c".repeat(64)
});

function storage() {
  const values = new Map();
  const operations = [];
  return {
    values, operations,
    getItem(key) { operations.push("get"); return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { operations.push("set"); values.set(key, value); }
  };
}

async function run() {
  const store = storage();
  const first = phases.prepare(store, intent);
  assert.equal(first.action, "prepare_new");
  assert.equal(first.claim.phase, "prepared");
  assert.deepEqual(store.operations.slice(0, 3), ["get", "set", "get"],
    "a first claim must be persisted and read back before use");
  assert.equal(phases.prepare(store, intent).action, "resume_before_arm");

  let changes = 0;
  assert.equal(phases.mutatePreparedComposer(store, intent, () => ++changes), 1);
  assert.equal(changes, 1);
  const draft = phases.advance(store, intent, "draft_verified");
  assert.equal(draft.phase, "draft_verified");
  assert.throws(() => phases.mutatePreparedComposer(store, intent, () => ++changes), /prepared/);
  assert.equal(changes, 1);
  assert.equal(phases.prepare(store, intent).action, "resume_before_arm");

  const restarted = require("./spawn_phase_storage.js");
  assert.equal(restarted.read(store, intent).phase, "draft_verified",
    "recovery must derive from page-local state, not an in-memory claim");
  let sends = 0;
  assert.equal(await restarted.armAndSend(store, intent, async () => ++sends), 1);
  assert.equal(sends, 1);
  assert.equal(phases.read(store, intent).phase, "submitted");
  await assert.rejects(phases.armAndSend(store, intent, () => ++sends), /reconcile after arm/);
  assert.equal(sends, 1);
  assert.equal(phases.prepare(store, intent).action, "reconcile_only");
  assert.throws(() => phases.retry(store, intent), /forbidden/);

  const conflict = { ...intent, bootstrap_digest: "sha256:" + "d".repeat(64) };
  assert.throws(() => phases.prepare(store, conflict), /permanent/);
  assert.throws(() => phases.mutatePreparedComposer(store, conflict, () => ++changes), /permanent/);
  assert.equal(changes, 1);

  const onError = storage();
  phases.prepare(onError, intent);
  phases.advance(onError, intent, "draft_verified");
  let ambiguousSends = 0;
  await assert.rejects(phases.armAndSend(onError, intent, () => {
    ambiguousSends++;
    throw new Error("Send acknowledgement lost");
  }), /acknowledgement lost/);
  assert.equal(ambiguousSends, 1);
  assert.equal(phases.read(onError, intent).phase, "submit_armed");
  await assert.rejects(phases.armAndSend(onError, intent, () => ++ambiguousSends), /reconcile after arm/);
  assert.equal(ambiguousSends, 1);
  assert.equal(phases.prepare(onError, intent).action, "reconcile_only");

  // Concurrent triggers cannot invoke Send twice after the durable arm.
  const concurrent = storage();
  phases.prepare(concurrent, intent);
  phases.advance(concurrent, intent, "draft_verified");
  let resolveSend;
  let count = 0;
  const firstSend = phases.armAndSend(concurrent, intent, () => {
    count++;
    return new Promise(resolve => { resolveSend = resolve; });
  });
  await assert.rejects(phases.armAndSend(concurrent, intent, () => ++count), /reconcile after arm/);
  resolveSend("sent");
  assert.equal(await firstSend, "sent");
  assert.equal(count, 1);

  const asyncComposer = storage();
  phases.prepare(asyncComposer, intent);
  let asyncMutations = 0;
  assert.throws(
    () => phases.mutatePreparedComposer(asyncComposer, intent, async () => ++asyncMutations),
    /synchronous/
  );
  assert.equal(asyncMutations, 0, "reject async callback before executing DOM effects");

  const failedWrite = storage();
  failedWrite.setItem = () => { throw new Error("storage full"); };
  assert.throws(() => phases.prepare(failedWrite, intent), /storage full/);
  assert.equal(changes, 1, "storage failure must precede DOM effects");
  const failedReadback = storage();
  failedReadback.setItem = () => {};
  assert.throws(() => phases.prepare(failedReadback, intent), /readback mismatch/);
  const failedArm = storage();
  phases.prepare(failedArm, intent);
  phases.advance(failedArm, intent, "draft_verified");
  let sendCount = 0;
  failedArm.setItem = () => { throw new Error("arm not persisted"); };
  await assert.rejects(phases.armAndSend(failedArm, intent, () => ++sendCount), /arm not persisted/);
  assert.equal(sendCount, 0, "no Send without persisted submit_armed");

  const corrupted = storage();
  corrupted.values.set(phases.keyFor(intent), "{bad json");
  assert.throws(() => phases.prepare(corrupted, intent), /corrupted/);
  assert.throws(() => phases.mutatePreparedComposer(corrupted, intent, () => ++changes), /corrupted/);
  assert.equal(changes, 1);
  const badIdentity = { ...intent, transaction_id: "other" };
  assert.throws(() => phases.prepare(storage(), badIdentity), /identity/);

  // Exactly 32 explicit draft retries, never a silent unbounded loop.
  const retries = storage();
  phases.prepare(retries, intent);
  for (let attempt = 2; attempt <= 32; attempt++) {
    assert.equal(phases.retry(retries, intent).attempt, attempt);
  }
  assert.throws(() => phases.retry(retries, intent), /limit exceeded/);

  assert.equal(model.validateClaim(first.claim), first.claim);
  console.log("Inactive page-local spawn-v2 claim storage tests passed.");
}

run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
