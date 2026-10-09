"use strict";

const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const { inspectEffectJournal } = require("./github_fabric_effect_journal_audit.js");

const PARENT = "parent-" + "a".repeat(32);
const GENESIS = "0".repeat(64);
const REQUEST = "b".repeat(64);
const EVENT_KEYS = [
  "sequence", "previous_digest", "digest", "parent_id", "effect_id",
  "worker_id", "transport", "epoch", "kind", "request_digest", "phase"
];
function blank() {
  return {
    schema_version: 1, parent_id: PARENT, fence_epoch: 2,
    expected_event_count: 0, expected_head_digest: GENESIS, events: []
  };
}
function append(journal, values = {}) {
  const sequence = journal.events.length + 1;
  const previous_digest = journal.expected_head_digest;
  const event = {
    sequence, previous_digest, parent_id: PARENT,
    effect_id: "send_1", worker_id: "mac", transport: "legacy_dom",
    epoch: 1, kind: "prompt_send", request_digest: REQUEST,
    phase: "prepared", ...values
  };
  const data = [
    "fabric-effect-journal-v1", event.sequence, event.previous_digest,
    event.parent_id, event.effect_id, event.worker_id, event.transport,
    event.epoch, event.kind, event.request_digest, event.phase
  ];
  event.digest = createHash("sha256").update(JSON.stringify(data), "utf8").digest("hex");
  journal.events.push(event);
  journal.expected_event_count = journal.events.length;
  journal.expected_head_digest = event.digest;
  return event;
}
async function blocked(journal, statuses) {
  const result = await inspectEffectJournal(journal);
  assert.equal(result.decision, "blocked");
  assert.equal(result.browser_effects_permitted, false);
  assert.equal(result.automatic_retry_permitted, false);
  assert.equal(result.last_digest, journal.expected_head_digest);
  assert.equal(result.event_count, journal.expected_event_count);
  assert.ok(Object.isFrozen(result) && Object.isFrozen(result.effects));
  if (statuses) {
    assert.deepEqual(result.effects.map(effect => effect.review_state), statuses);
  }
  for (const effect of result.effects) {
    assert.equal(effect.replay_permitted, false);
    assert.ok(Object.isFrozen(effect));
  }
}
async function rejects(journal, reason) {
  await assert.rejects(inspectEffectJournal(journal), reason);
}
async function run() {
  await blocked(blank(), []);
  const pending = blank();
  append(pending);
  await blocked(pending, ["suspended_requires_reconciliation"]);

  const uncertain = blank();
  append(uncertain);
  append(uncertain, { phase: "effect_started" });
  append(uncertain, { phase: "effect_unknown" });
  await blocked(uncertain, ["suspended_requires_reconciliation"]);

  const acknowledged = blank();
  append(acknowledged);
  append(acknowledged, { phase: "effect_started" });
  append(acknowledged, { phase: "ack_observed" });
  await blocked(acknowledged, ["ack_claim_for_review"]);
  assert.deepEqual((await inspectEffectJournal(acknowledged)).conflicts, []);

  const twoDevices = blank();
  append(twoDevices);
  append(twoDevices, { effect_id: "send_2", worker_id: "phone",
    transport: "github_first", epoch: 2, phase: "prepared" });
  append(twoDevices, { effect_id: "send_2", worker_id: "phone",
    transport: "github_first", epoch: 2, phase: "effect_started" });
  append(twoDevices, { effect_id: "send_2", worker_id: "phone",
    transport: "github_first", epoch: 2, phase: "effect_unknown" });
  await blocked(twoDevices, [
    "suspended_requires_reconciliation", "suspended_requires_reconciliation"
  ]);
  const competingClaims = await inspectEffectJournal(twoDevices);
  assert.deepEqual([...competingClaims.conflicts], [{
    kind: "duplicate_logical_request_effect",
    first_effect_id: "send_1",
    second_effect_id: "send_2"
  }], "two devices must not silently treat identical logical work as independent");

  const poisoned = structuredClone(acknowledged);
  poisoned.events[1].phase = "effect_unknown";
  await rejects(poisoned, /digest mismatch/);

  const truncated = structuredClone(acknowledged);
  truncated.events.pop();
  truncated.expected_event_count = truncated.events.length;
  await rejects(truncated, /anchored head digest mismatch/);

  const countConflict = structuredClone(acknowledged);
  countConflict.expected_event_count += 1;
  await rejects(countConflict, /envelope invalid/);

  const wrongHead = structuredClone(acknowledged);
  wrongHead.expected_head_digest = "f".repeat(64);
  await rejects(wrongHead, /anchored head digest mismatch/);

  const wrongOrder = structuredClone(acknowledged);
  [wrongOrder.events[0], wrongOrder.events[1]] =
    [wrongOrder.events[1], wrongOrder.events[0]];
  await rejects(wrongOrder, /identity, sequence or chain invalid/);

  const hiddenGap = structuredClone(acknowledged);
  hiddenGap.events.splice(1, 1);
  hiddenGap.expected_event_count -= 1;
  await rejects(hiddenGap, /identity, sequence or chain invalid/);

  const illegalCases = [
    [{ phase: "effect_unknown" }],
    [{ phase: "ack_observed" }],
    [{ phase: "prepared" }, { phase: "prepared" }],
    [{ phase: "prepared" }, { phase: "ack_observed" }],
    [{ phase: "prepared" }, { phase: "effect_started" },
      { phase: "effect_started" }],
    [{ phase: "prepared" }, { phase: "effect_unknown" },
      { phase: "ack_observed" }],
    [{ phase: "prepared" }, { phase: "effect_started" },
      { phase: "ack_observed" }, { phase: "effect_unknown" }],
    [{ phase: "prepared" }, { phase: "effect_started" },
      { phase: "effect_unknown" }, { phase: "effect_started" }],
    [{ phase: "prepared" }, { phase: "effect_started", worker_id: "phone" }],
    [{ phase: "prepared" }, { phase: "effect_started", epoch: 2 }],
    [{ phase: "prepared" }, { phase: "effect_started", request_digest: "f".repeat(64) }],
    [{ phase: "prepared" }, { phase: "effect_started", kind: "terminal_feedback" }],
    [{ phase: "prepared" }, { phase: "effect_started", transport: "github_first" }]
  ];
  for (const entries of illegalCases) {
    const journal = blank();
    for (const event of entries) append(journal, event);
    await rejects(journal, /preparation|illegal lifecycle transition/);
  }

  const future = blank();
  append(future, { epoch: 3 });
  await rejects(future, /identity, sequence or chain invalid/);

  const forgedParent = blank();
  append(forgedParent, { parent_id: "parent-" + "c".repeat(32) });
  await rejects(forgedParent, /identity, sequence or chain invalid/);

  const malformed = [
    j => { j.parent_id = 123; },
    j => { j.events[0].effect_id = 20; },
    j => { j.events[0].sequence = 1.1; },
    j => { j.events[0].phase = "applied"; },
    j => { j.events[0].previous_digest = "broken"; },
    j => { j.events[0].digest = "f".repeat(63); },
    j => { j.events[0].extra = "unexpected"; },
    j => { j.fence_epoch = 0; },
    j => { j.schema_version = "1"; },
    j => { j.expected_head_digest = null; }
  ];
  for (const mutate of malformed) {
    const journal = structuredClone(pending);
    mutate(journal);
    await rejects(journal, /invalid/);
  }

  const tooMany = blank();
  for (let i = 0; i < 257; i += 1) {
    append(tooMany, { effect_id: "effect_" + i });
  }
  await rejects(tooMany, /envelope invalid/);

  const moduleSource = fs.readFileSync(
    path.join(__dirname, "github_fabric_effect_journal_audit.js"), "utf8"
  );
  const serviceWorker = fs.readFileSync(path.join(__dirname, "service_worker.js"), "utf8");
  const manifest = fs.readFileSync(path.join(__dirname, "manifest.json"), "utf8");
  assert.doesNotMatch(serviceWorker + manifest, /github_fabric_effect_journal_audit/);
  assert.doesNotMatch(moduleSource,
    /chrome\.tabs|chrome\.scripting|fetch\(|sendMessage\(|Authorization|readToken/);
  assert.doesNotMatch(moduleSource,
    /browser_effects_permitted:\s*true|automatic_retry_permitted:\s*true/);
  assert.deepEqual(
    Object.keys(acknowledged.events[0]).sort(),
    EVENT_KEYS.sort(),
    "synthetic writer and reader must agree on strict event fields"
  );
  console.log("Private Fabric effect-journal loss/unknown/replay audit: PASS");
}
run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
