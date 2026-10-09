(function initGlobalAdmissionAudit(root, factory) {
  const api = factory();
  root.LocalAgentGlobalTransportAdmissionAudit = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createGlobalAdmissionAudit() {
  "use strict";

  // Source-only diagnostics. This module is intentionally NOT imported by the
  // production extension. GitHub records and local storage cannot revoke
  // browser effects from older, offline, or non-participating DOM workers.
  const PARENT_RE = /^parent-[0-9a-f]{32}$/;
  const SHA_RE = /^[0-9a-f]{40}$/;
  const ID_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;
  const EFFECT_KINDS = new Set([
    "child_tab", "content_prepare", "prompt_send", "result_reuse",
    "terminal_feedback", "owned_tab_cleanup"
  ]);
  const EFFECT_STATES = new Set([
    "prepared", "in_flight", "unknown", "confirmed_terminal"
  ]);
  const WORKER_STATES = new Set([
    "active", "offline", "unknown", "retirement_claimed"
  ]);
  const MAX_WORKERS = 64;
  const MAX_EFFECTS = 256;

  function object(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  function exactKeys(value, expected) {
    return object(value) &&
      Object.keys(value).sort().join(",") === [...expected].sort().join(",");
  }

  function validEpoch(value) {
    return Number.isSafeInteger(value) && value > 0;
  }

  function validWorker(worker) {
    return exactKeys(worker, ["id", "state", "retirement_receipt"]) &&
      typeof worker.id === "string" && ID_RE.test(worker.id) &&
      WORKER_STATES.has(worker.state) &&
      (worker.retirement_receipt === null ||
        (typeof worker.retirement_receipt === "string" &&
          SHA_RE.test(worker.retirement_receipt)));
  }

  function validEffect(effect) {
    return exactKeys(effect, ["id", "worker_id", "epoch", "kind", "state", "terminal_receipt"]) &&
      typeof effect.id === "string" && ID_RE.test(effect.id) &&
      typeof effect.worker_id === "string" && ID_RE.test(effect.worker_id) &&
      validEpoch(effect.epoch) &&
      EFFECT_KINDS.has(effect.kind) && EFFECT_STATES.has(effect.state) &&
      (effect.terminal_receipt === null ||
        (typeof effect.terminal_receipt === "string" && SHA_RE.test(effect.terminal_receipt))) &&
      (effect.state === "confirmed_terminal" || effect.terminal_receipt === null);
  }

  function validateSnapshot(snapshot) {
    if (!exactKeys(snapshot, [
      "schema_version", "parent_id", "mode", "epoch", "pinned_head",
      "observed_head", "workers", "effects"
    ]) || snapshot.schema_version !== 1 ||
        typeof snapshot.parent_id !== "string" || !PARENT_RE.test(snapshot.parent_id) ||
        !["legacy_dom", "github_first"].includes(snapshot.mode) ||
        !validEpoch(snapshot.epoch) ||
        typeof snapshot.pinned_head !== "string" || !SHA_RE.test(snapshot.pinned_head) ||
        typeof snapshot.observed_head !== "string" || !SHA_RE.test(snapshot.observed_head) ||
        !Array.isArray(snapshot.workers) || snapshot.workers.length > MAX_WORKERS ||
        !Array.isArray(snapshot.effects) || snapshot.effects.length > MAX_EFFECTS ||
        !snapshot.workers.every(validWorker) || !snapshot.effects.every(validEffect)) {
      throw new Error("Global transport admission snapshot invalid");
    }
    const workerIds = new Set(snapshot.workers.map(worker => worker.id));
    const effectIds = snapshot.effects.map(effect => effect.id);
    if (workerIds.size !== snapshot.workers.length ||
        new Set(effectIds).size !== effectIds.length ||
        snapshot.effects.some(effect =>
          !workerIds.has(effect.worker_id) || effect.epoch > snapshot.epoch)) {
      throw new Error("Global transport admission identities invalid");
    }
    return snapshot;
  }

  function recoveryForEffect(effect) {
    if (!validEffect(effect)) {
      throw new Error("Legacy browser effect evidence invalid");
    }
    return Object.freeze({
      effect_id: effect.id,
      state: effect.state === "confirmed_terminal" && effect.terminal_receipt
        ? "terminal_evidence_for_review"
        : "suspended_requires_reconciliation",
      replay_permitted: false
    });
  }

  function inspectGlobalTransportAdmission(input) {
    if (!exactKeys(input, ["previous", "proposed", "operator_retirement_attestation"])) {
      throw new Error("Global transport admission input invalid");
    }
    const previous = validateSnapshot(input.previous);
    const proposed = validateSnapshot(input.proposed);
    if (typeof input.operator_retirement_attestation !== "boolean") {
      throw new Error("Global transport retirement attestation invalid");
    }
    const blockers = [];
    if (previous.parent_id !== proposed.parent_id) blockers.push("parent_identity_conflict");
    if (previous.mode !== "legacy_dom" || proposed.mode !== "github_first") {
      blockers.push("unsupported_mode_transition");
    }
    if (!validEpoch(previous.epoch + 1) || proposed.epoch !== previous.epoch + 1) {
      blockers.push("non_monotonic_fence_epoch");
    }
    if (previous.pinned_head !== previous.observed_head ||
        proposed.pinned_head !== proposed.observed_head) {
      blockers.push("stale_or_conflicting_source_snapshot");
    }
    if (previous.workers.some(worker => worker.state !== "retirement_claimed") ||
        proposed.workers.some(worker => worker.state !== "retirement_claimed")) {
      blockers.push("active_offline_or_unknown_legacy_worker");
    }
    if (previous.effects.some(effect =>
          effect.state !== "confirmed_terminal" || !effect.terminal_receipt) ||
        proposed.effects.some(effect =>
          effect.state !== "confirmed_terminal" || !effect.terminal_receipt)) {
      blockers.push("pending_or_unknown_browser_effect");
    }
    if (!input.operator_retirement_attestation) {
      blockers.push("operator_retirement_attestation_missing");
    }

    // Even a complete declared inventory, terminal receipts and a human
    // attestation cannot prove that every older/offline extension is unable
    // to resume or race between a local read and an actual Chrome effect.
    // An independently trusted GLOBAL effect enforcement and old-session
    // revocation mechanism does not exist in this source revision.
    blockers.push("unbounded_legacy_worker_population");
    blockers.push("missing_atomic_cross_device_effect_exclusion");
    blockers.push("trusted_external_retirement_proof_unavailable");
    blockers.push("independent_security_and_live_acceptance_pending");

    return Object.freeze({
      schema_version: 1,
      parent_id: proposed.parent_id,
      candidate_epoch: proposed.epoch,
      decision: "blocked",
      browser_effects_permitted: false,
      automatic_retry_permitted: false,
      blockers: Object.freeze(blockers)
    });
  }

  return Object.freeze({
    inspectGlobalTransportAdmission,
    recoveryForEffect
  });
});
