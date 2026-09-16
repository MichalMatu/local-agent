"use strict";

const assert = require("node:assert/strict");
const {
  deliveryWasAccepted,
  isNewDeliveryTurn
} = require("./content_retry.js");

const previous = { identity: "user-old", text: "previous prompt" };
const exact = { identity: "user-new", text: "expected prompt" };
const transformed = { identity: "user-new", text: "Rendered expected prompt" };

assert.equal(isNewDeliveryTurn(previous, exact), true);
assert.equal(isNewDeliveryTurn(exact, exact), false);

assert.equal(
  deliveryWasAccepted({
    previousTurn: previous,
    currentTurn: exact,
    expectedText: "expected prompt",
    composerAccepted: false,
    assistantGenerating: false
  }),
  true,
  "exact matching turn confirms without fallback evidence"
);

assert.equal(
  deliveryWasAccepted({
    previousTurn: previous,
    currentTurn: transformed,
    expectedText: "expected prompt",
    composerAccepted: true,
    assistantGenerating: false
  }),
  true,
  "renderer text changes are accepted only after the composer was accepted"
);

assert.equal(
  deliveryWasAccepted({
    previousTurn: previous,
    currentTurn: transformed,
    expectedText: "expected prompt",
    composerAccepted: false,
    assistantGenerating: false
  }),
  false,
  "different rendered text without composer acceptance must fail closed"
);

assert.equal(
  deliveryWasAccepted({
    previousTurn: previous,
    currentTurn: previous,
    expectedText: "expected prompt",
    composerAccepted: true,
    assistantGenerating: true
  }),
  true,
  "cleared/replaced composer plus assistant generation confirms even when user-turn selectors lag"
);

assert.equal(
  deliveryWasAccepted({
    previousTurn: previous,
    currentTurn: previous,
    expectedText: "expected prompt",
    composerAccepted: true,
    assistantGenerating: false
  }),
  false,
  "composer acceptance alone is not enough to consume a pending wake"
);

console.log("Chat Bridge delivery acceptance evidence tests passed.");
