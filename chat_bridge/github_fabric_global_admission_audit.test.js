"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const audit = require("./github_fabric_global_admission_audit.js");

const SHA_A = "a".repeat(40);
const SHA_B = "b".repeat(40);
const PARENT_A = "parent-" + "c".repeat(32);
const PARENT_B = "parent-" + "d".repeat(32);

function example() {
  return {
    previous: {
      schema_version: 1, parent_id: PARENT_A, mode: "legacy_dom", epoch: 1,
      pinned_head: SHA_A, observed_head: SHA_A,
      workers: [{ id: "mac", state: "retirement_claimed", retirement_receipt: SHA_A }],
      effects: [{
        id: "send_1", worker_id: "mac", epoch: 1, kind: "prompt_send",
        state: "confirmed_terminal", terminal_receipt: SHA_A
      }]
    },
    proposed: {
      schema_version: 1, parent_id: PARENT_A, mode: "github_first", epoch: 2,
      pinned_head: SHA_B, observed_head: SHA_B,
      workers: [{ id: "mac", state: "retirement_claimed", retirement_receipt: SHA_A }],
      effects: [{
        id: "send_1", worker_id: "mac", epoch: 1, kind: "prompt_send",
        state: "confirmed_terminal", terminal_receipt: SHA_A
      }, {
        id: "feedback_1", worker_id: "mac", epoch: 1, kind: "terminal_feedback",
        state: "confirmed_terminal", terminal_receipt: SHA_B
      }]
    },
    operator_retirement_attestation: true
  };
}

function checkBlocked(input, blocker) {
  const result = audit.inspectGlobalTransportAdmission(input);
  assert.equal(result.decision, "blocked");
  assert.equal(result.browser_effects_permitted, false);
  assert.equal(result.automatic_retry_permitted, false);
  assert.ok(Object.isFrozen(result) && Object.isFrozen(result.blockers));
  assert.equal(result.blockers.length, new Set(result.blockers).size);
  assert.ok(result.blockers.includes("unbounded_legacy_worker_population"));
  assert.ok(result.blockers.includes("missing_atomic_cross_device_effect_exclusion"));
  assert.ok(result.blockers.includes("trusted_external_retirement_proof_unavailable"));
  if (blocker) assert.ok(result.blockers.includes(blocker), JSON.stringify(result.blockers));
}

function run() {
  const validContinuity = audit.inspectGlobalTransportAdmission(example());
  assert.deepEqual([...validContinuity.blockers], [
    "unbounded_legacy_worker_population",
    "missing_atomic_cross_device_effect_exclusion",
    "trusted_external_retirement_proof_unavailable",
    "independent_security_and_live_acceptance_pending"
  ], "consistent claims alone must still block, without inventing history corruption");

  // Even a unanimous claimed retirement and terminal receipts are not a
  // verified exclusion mechanism: old/offline versions can still act.
  checkBlocked(example());
  const emptyInventory = example();
  emptyInventory.previous.workers = [];
  emptyInventory.previous.effects = [];
  emptyInventory.proposed.workers = [];
  emptyInventory.proposed.effects = [];
  checkBlocked(emptyInventory);

  for (const state of ["active", "offline", "unknown"]) {
    const input = example();
    input.previous.workers[0].state = state;
    checkBlocked(input, "active_offline_or_unknown_legacy_worker");
  }
  for (const state of ["prepared", "in_flight", "unknown"]) {
    const input = example();
    input.previous.effects[0].state = state;
    input.previous.effects[0].terminal_receipt = null;
    checkBlocked(input, "pending_or_unknown_browser_effect");
  }
  const ambiguousTerminal = example();
  ambiguousTerminal.proposed.effects[0].terminal_receipt = null;
  checkBlocked(ambiguousTerminal, "pending_or_unknown_browser_effect");

  const lostWorker = example();
  lostWorker.proposed.workers = [];
  lostWorker.proposed.effects = [];
  checkBlocked(lostWorker, "legacy_worker_inventory_regression");

  const droppedEffect = example();
  droppedEffect.proposed.effects = [];
  checkBlocked(droppedEffect, "effect_history_discarded");

  const rewrittenEffect = example();
  rewrittenEffect.proposed.effects[0].kind = "terminal_feedback";
  checkBlocked(rewrittenEffect, "effect_identity_rewritten");

  const rewrittenWorker = example();
  rewrittenWorker.proposed.workers[0].retirement_receipt = SHA_B;
  checkBlocked(rewrittenWorker, "legacy_retirement_receipt_changed");

  // Previously observed retirement evidence must not silently disappear,
  // even if a later snapshot calls the worker active rather than retired.
  const droppedRetirementReceipt = example();
  droppedRetirementReceipt.previous.workers[0].state = "active";
  droppedRetirementReceipt.proposed.workers[0].state = "active";
  droppedRetirementReceipt.proposed.workers[0].retirement_receipt = null;
  checkBlocked(droppedRetirementReceipt, "legacy_retirement_receipt_changed");

  const changedTerminalReceipt = example();
  changedTerminalReceipt.proposed.effects[0].terminal_receipt = SHA_B;
  checkBlocked(changedTerminalReceipt, "terminal_effect_evidence_mutated");

  const changedTerminalState = example();
  changedTerminalState.proposed.effects[0].state = "unknown";
  changedTerminalState.proposed.effects[0].terminal_receipt = null;
  checkBlocked(changedTerminalState, "terminal_effect_evidence_mutated");

  const previouslyUnknown = example();
  previouslyUnknown.previous.effects[0].state = "unknown";
  previouslyUnknown.previous.effects[0].terminal_receipt = null;
  checkBlocked(previouslyUnknown, "unknown_effect_reclassified_without_proof");

  const inFlightReset = example();
  inFlightReset.previous.effects[0].state = "in_flight";
  inFlightReset.previous.effects[0].terminal_receipt = null;
  inFlightReset.proposed.effects[0].state = "prepared";
  inFlightReset.proposed.effects[0].terminal_receipt = null;
  checkBlocked(inFlightReset, "in_flight_effect_reset");

  const claimWithoutReceipt = example();
  claimWithoutReceipt.proposed.workers[0].retirement_receipt = null;
  checkBlocked(claimWithoutReceipt, "retirement_claim_without_receipt");

  const twoDevices = example();
  twoDevices.previous.workers.push({
    id: "phone_offline", state: "offline", retirement_receipt: null
  });
  twoDevices.proposed.workers.push({
    id: "phone_offline", state: "offline", retirement_receipt: null
  });
  checkBlocked(twoDevices, "active_offline_or_unknown_legacy_worker");

  const mismatchedParent = example();
  mismatchedParent.proposed.parent_id = PARENT_B;
  checkBlocked(mismatchedParent, "parent_identity_conflict");
  const reversed = example();
  reversed.previous.mode = "github_first";
  checkBlocked(reversed, "unsupported_mode_transition");
  const epochReplay = example();
  epochReplay.proposed.epoch = 1;
  checkBlocked(epochReplay, "non_monotonic_fence_epoch");
  const epochJump = example();
  epochJump.proposed.epoch = 4;
  checkBlocked(epochJump, "non_monotonic_fence_epoch");
  const stale = example();
  stale.previous.observed_head = SHA_B;
  checkBlocked(stale, "stale_or_conflicting_source_snapshot");
  const noAttestation = example();
  noAttestation.operator_retirement_attestation = false;
  checkBlocked(noAttestation, "operator_retirement_attestation_missing");

  const malformedCases = [
    x => { x.previous.epoch = 1.5; },
    x => { x.previous.parent_id = "wrong"; },
    x => { x.previous.pinned_head = "x".repeat(40); },
    x => { x.proposed.workers[0].retirement_receipt = 10; },
    x => { x.previous.effects[0].kind = "unrecognized_side_effect"; },
    x => { x.previous.effects[0].state = "unknown"; },
    x => { x.proposed.effects[0].epoch = 3; },
    x => { x.proposed.effects[0].worker_id = "other"; },
    x => { x.previous.workers.push(x.previous.workers[0]); },
    x => { x.proposed.effects.push(x.proposed.effects[0]); },
    x => { x.previous.workers = Array.from({ length: 65 }, (_, i) => ({
      id: "worker_" + i, state: "retirement_claimed", retirement_receipt: SHA_A
    })); },
    x => { x.proposed.effects = Array.from({ length: 257 }, (_, i) => ({
      id: "effect_" + i, worker_id: "mac", epoch: 1,
      kind: "prompt_send", state: "unknown", terminal_receipt: null
    })); },
    x => { x.proposed.extra_unreviewed_field = true; },
    x => { x.operator_retirement_attestation = "true"; }
  ];
  for (const mutate of malformedCases) {
    const input = example();
    mutate(input);
    assert.throws(() => audit.inspectGlobalTransportAdmission(input),
      /admission|attestation/i);
  }

  for (const state of ["prepared", "in_flight", "unknown", "confirmed_terminal"]) {
    const effect = { ...example().previous.effects[0], state,
      terminal_receipt: state === "confirmed_terminal" ? SHA_A : null };
    const result = audit.recoveryForEffect(effect);
    assert.equal(result.replay_permitted, false);
    assert.equal(result.state,
      state === "confirmed_terminal" ? "terminal_evidence_for_review" :
        "suspended_requires_reconciliation");
  }
  const unproven = { ...example().previous.effects[0], terminal_receipt: null };
  assert.equal(audit.recoveryForEffect(unproven).replay_permitted, false);

  const source = fs.readFileSync(path.join(__dirname,
    "github_fabric_global_admission_audit.js"), "utf8");
  const worker = fs.readFileSync(path.join(__dirname, "service_worker.js"), "utf8");
  const manifest = fs.readFileSync(path.join(__dirname, "manifest.json"), "utf8");
  assert.doesNotMatch(worker + manifest, /github_fabric_global_admission_audit/);
  assert.doesNotMatch(source, /chrome\.tabs|chrome\.scripting|fetch\(|sendMessage\(|Authorization|readToken/);
  assert.doesNotMatch(source, /browser_effects_permitted:\s*true|automatic_retry_permitted:\s*true/);
  console.log("Global transport cutover source-only deny audit: PASS");
}

run();
