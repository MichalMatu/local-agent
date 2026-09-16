(function initLocalAgentBridgeContentRetry(root, factory) {
  const api = factory();
  root.LocalAgentBridgeContentRetry = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function createContentRetryApi() {
  "use strict";

  function createRetryGate({ baseMs = 5000, maxMs = 30000 } = {}) {
    if (!Number.isFinite(baseMs) || baseMs <= 0 || !Number.isFinite(maxMs) || maxMs < baseMs) {
      throw new Error("invalid retry gate bounds");
    }

    let signature = "";
    let failures = 0;
    let notBefore = 0;

    function select(nextSignature) {
      const value = String(nextSignature || "");
      if (value !== signature) {
        signature = value;
        failures = 0;
        notBefore = 0;
      }
      return signature;
    }

    function canAttempt(nextSignature, nowMs = Date.now()) {
      select(nextSignature);
      return Number(nowMs) >= notBefore;
    }

    function defer(nextSignature, nowMs = Date.now()) {
      select(nextSignature);
      failures += 1;
      const delayMs = Math.min(baseMs * (2 ** Math.min(failures - 1, 3)), maxMs);
      notBefore = Number(nowMs) + delayMs;
      return delayMs;
    }

    function reset(nextSignature = signature) {
      signature = String(nextSignature || "");
      failures = 0;
      notBefore = 0;
    }

    function snapshot() {
      return Object.freeze({ signature, failures, notBefore });
    }

    return Object.freeze({ canAttempt, defer, reset, snapshot });
  }

  function normalizeDeliveryText(value) {
    return String(value || "").trim().replace(/\s+/g, " ");
  }

  function deliveryTurnSignature(turn) {
    if (!turn || typeof turn !== "object") return "";
    const identity = String(turn.identity || "");
    const text = normalizeDeliveryText(turn.text);
    return identity || text ? `${identity}\n${text}` : "";
  }

  function isNewDeliveryTurn(previousTurn, currentTurn) {
    const currentSignature = deliveryTurnSignature(currentTurn);
    return Boolean(currentSignature && currentSignature !== deliveryTurnSignature(previousTurn));
  }

  function isNewMatchingDeliveryTurn(previousTurn, currentTurn, expectedText) {
    if (!currentTurn || normalizeDeliveryText(currentTurn.text) !== normalizeDeliveryText(expectedText)) {
      return false;
    }
    return isNewDeliveryTurn(previousTurn, currentTurn);
  }

  function deliveryWasAccepted({
    previousTurn,
    currentTurn,
    expectedText,
    composerAccepted = false,
    assistantGenerating = false
  } = {}) {
    if (isNewMatchingDeliveryTurn(previousTurn, currentTurn, expectedText)) return true;
    if (!composerAccepted) return false;
    if (isNewDeliveryTurn(previousTurn, currentTurn)) return true;
    return Boolean(assistantGenerating);
  }

  return Object.freeze({
    createRetryGate,
    normalizeDeliveryText,
    deliveryTurnSignature,
    isNewDeliveryTurn,
    isNewMatchingDeliveryTurn,
    deliveryWasAccepted
  });
});
