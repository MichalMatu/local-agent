(function initEffectJournalAudit(root, factory) {
  const api = factory();
  root.LocalAgentFabricEffectJournalAudit = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createEffectJournalAudit() {
  "use strict";

  // Pure, unimported forensic verification. Hash linkage detects changes to a
  // pinned journal; it NEVER authenticates the writer or authorizes Chrome Send.
  const PARENT_RE = /^parent-[0-9a-f]{32}$/;
  const SHA256_RE = /^[0-9a-f]{64}$/;
  const ID_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;
  const PHASES = new Set(["prepared", "effect_started", "ack_observed", "effect_unknown"]);
  const KINDS = new Set([
    "child_tab", "content_prepare", "prompt_send", "result_reuse",
    "terminal_feedback", "owned_tab_cleanup"
  ]);
  const MAX_EVENTS = 256;
  const GENESIS = "0".repeat(64);

  function exactKeys(value, fields) {
    return value !== null && typeof value === "object" && !Array.isArray(value) &&
      Object.keys(value).sort().join(",") === [...fields].sort().join(",");
  }

  function validEpoch(epoch) {
    return Number.isSafeInteger(epoch) && epoch > 0;
  }

  function validEvent(event) {
    return exactKeys(event, [
      "sequence", "previous_digest", "digest", "parent_id", "effect_id",
      "worker_id", "transport", "epoch", "kind", "request_digest", "phase"
    ]) &&
      Number.isSafeInteger(event.sequence) && event.sequence >= 1 &&
      typeof event.previous_digest === "string" && SHA256_RE.test(event.previous_digest) &&
      typeof event.digest === "string" && SHA256_RE.test(event.digest) &&
      typeof event.parent_id === "string" && PARENT_RE.test(event.parent_id) &&
      typeof event.effect_id === "string" && ID_RE.test(event.effect_id) &&
      typeof event.worker_id === "string" && ID_RE.test(event.worker_id) &&
      typeof event.transport === "string" &&
      ["legacy_dom", "github_first"].includes(event.transport) &&
      validEpoch(event.epoch) && typeof event.kind === "string" && KINDS.has(event.kind) &&
      typeof event.request_digest === "string" && SHA256_RE.test(event.request_digest) &&
      typeof event.phase === "string" && PHASES.has(event.phase);
  }

  function canonicalEvent(event) {
    return JSON.stringify([
      "fabric-effect-journal-v1", event.sequence, event.previous_digest,
      event.parent_id, event.effect_id, event.worker_id, event.transport,
      event.epoch, event.kind, event.request_digest, event.phase
    ]);
  }

  async function sha256(bytes) {
    if (!globalThis.crypto?.subtle) {
      throw new Error("Effect journal digest verifier unavailable");
    }
    const value = new Uint8Array(await globalThis.crypto.subtle.digest("SHA-256", bytes));
    return Array.from(value, byte => byte.toString(16).padStart(2, "0")).join("");
  }

  function nextPhase(previous, phase) {
    return (previous === "prepared" &&
        (phase === "effect_started" || phase === "effect_unknown")) ||
      (previous === "effect_started" &&
        (phase === "ack_observed" || phase === "effect_unknown"));
  }

  async function inspectEffectJournal(journal) {
    if (!exactKeys(journal, ["schema_version", "parent_id", "fence_epoch", "expected_event_count", "expected_head_digest", "events"]) ||
        journal.schema_version !== 1 || typeof journal.parent_id !== "string" ||
        !PARENT_RE.test(journal.parent_id) || !validEpoch(journal.fence_epoch) ||
        !Number.isSafeInteger(journal.expected_event_count) ||
        journal.expected_event_count < 0 || journal.expected_event_count > MAX_EVENTS ||
        typeof journal.expected_head_digest !== "string" ||
        !SHA256_RE.test(journal.expected_head_digest) ||
        !Array.isArray(journal.events) ||
        journal.events.length !== journal.expected_event_count) {
      throw new Error("Effect journal envelope invalid");
    }
    const states = new Map();
    let previousDigest = GENESIS;
    for (let index = 0; index < journal.events.length; index += 1) {
      const event = journal.events[index];
      if (!validEvent(event) || event.sequence !== index + 1 ||
          event.parent_id !== journal.parent_id ||
          event.epoch > journal.fence_epoch ||
          event.previous_digest !== previousDigest) {
        throw new Error("Effect journal entry identity, sequence or chain invalid");
      }
      const actualDigest = await sha256(new TextEncoder().encode(canonicalEvent(event)));
      if (actualDigest !== event.digest) {
        throw new Error("Effect journal event digest mismatch");
      }
      const existing = states.get(event.effect_id);
      if (!existing) {
        if (event.phase !== "prepared") {
          throw new Error("Effect journal event lacks initial preparation");
        }
        states.set(event.effect_id, {
          effect_id: event.effect_id,
          worker_id: event.worker_id,
          transport: event.transport,
          epoch: event.epoch,
          kind: event.kind,
          request_digest: event.request_digest,
          phase: event.phase
        });
      } else {
        if (existing.worker_id !== event.worker_id ||
            existing.transport !== event.transport ||
            existing.epoch !== event.epoch ||
            existing.kind !== event.kind ||
            existing.request_digest !== event.request_digest ||
            !nextPhase(existing.phase, event.phase)) {
          throw new Error("Effect journal identity conflict or illegal lifecycle transition");
        }
        existing.phase = event.phase;
      }
      previousDigest = event.digest;
    }

    if (previousDigest !== journal.expected_head_digest) {
      throw new Error("Effect journal anchored head digest mismatch");
    }

    const effects = Object.freeze(Array.from(states.values(), state => Object.freeze({
      effect_id: state.effect_id,
      phase: state.phase,
      review_state: state.phase === "ack_observed"
        ? "ack_claim_for_review"
        : "suspended_requires_reconciliation",
      replay_permitted: false
    })));
    return Object.freeze({
      schema_version: 1,
      parent_id: journal.parent_id,
      fence_epoch: journal.fence_epoch,
      last_digest: previousDigest,
      event_count: journal.events.length,
      decision: "blocked",
      browser_effects_permitted: false,
      automatic_retry_permitted: false,
      effects
    });
  }

  return Object.freeze({ inspectEffectJournal });
});
