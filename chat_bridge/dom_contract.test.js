"use strict";
const assert = require("node:assert/strict");
const dom = require("./dom_contract.js");

function element({ text = "", attrs = {}, query = {}, queryAll = {} } = {}) {
  return {
    innerText: text,
    textContent: text,
    id: attrs.id || "",
    getAttribute(name) {
      return Object.hasOwn(attrs, name) ? attrs[name] : null;
    },
    querySelector(selector) {
      return query[selector] || null;
    },
    querySelectorAll(selector) {
      return queryAll[selector] || [];
    }
  };
}

const button = element({ text: " Start   new chat " });
const error = element({
  text: "You've reached the maximum length for this conversation, but you can keep talking by starting a new chat. Start new chat",
  queryAll: { button: [button] }
});
const message = element({
  attrs: {
    "data-message-author-role": "assistant",
    "data-message-id": "23ce695f-ebce-4b62-ae56-7eed597d913f"
  },
  query: { ".text-token-text-error": error }
});
const root = {
  querySelectorAll(selector) {
    if (selector === '[data-turn-key]') return [];
    assert.equal(selector, '[data-message-author-role="assistant"], [data-conversation-role="assistant"]');
    return [message];
  }
};

let found = dom.findConversationExhaustion(root);
assert.ok(found);
assert.equal(found.button, button);
assert.equal(found.assistantIdentity, "23ce695f-ebce-4b62-ae56-7eed597d913f");

const missingButtonRoot = {
  querySelectorAll() {
    return [element({
      query: {
        ".text-token-text-error": element({
          text: "You've reached the maximum length for this conversation.",
          queryAll: { button: [element({ text: "Retry" })] }
        })
      }
    })];
  }
};
assert.equal(dom.findConversationExhaustion(missingButtonRoot), null);

const unrelatedErrorRoot = {
  querySelectorAll() {
    return [element({
      query: {
        ".text-token-text-error": element({
          text: "Something went wrong.",
          queryAll: { button: [element({ text: "Start new chat" })] }
        })
      }
    })];
  }
};
assert.equal(dom.findConversationExhaustion(unrelatedErrorRoot), null);
assert.equal(dom.normalizedText("  Start\n new   chat "), "Start new chat");

const retryButton = element({
  text: "Retry",
  attrs: { "data-testid": "regenerate-thread-error-button" }
});
const timeoutError = element({
  text: "Message delivery timed out. Please try again. Retry",
  query: {
    'button[data-testid="regenerate-thread-error-button"]': retryButton
  },
  queryAll: { button: [retryButton] }
});
const timeoutMessage = element({
  attrs: {
    "data-message-author-role": "assistant",
    "data-message-id": "51eb8ef7-78e7-4143-8971-eec2b5b593c8"
  },
  query: { ".text-token-text-error": timeoutError }
});
const triggeringUser = element({
  text: "Bridge wake",
  attrs: {
    "data-message-author-role": "user",
    "data-message-id": "bridge-user"
  }
});
const timeoutRoot = {
  querySelectorAll(selector) {
    assert.equal(selector, '[data-message-author-role], [data-conversation-role="assistant"], [data-user-message-bubble]');
    return [triggeringUser, timeoutMessage];
  }
};

found = dom.findRecoverableAssistantError(timeoutRoot);
assert.ok(found);
assert.equal(found.kind, "message_delivery_timeout");
assert.equal(found.button, retryButton);
assert.equal(found.assistantIdentity, "51eb8ef7-78e7-4143-8971-eec2b5b593c8");
assert.match(found.errorText, /Message delivery timed out/);

const newerUser = element({
  text: "A later operator message",
  attrs: {
    "data-message-author-role": "user",
    "data-message-id": "later-user"
  }
});
const staleAfterUserRoot = {
  querySelectorAll(selector) {
    assert.equal(selector, '[data-message-author-role], [data-conversation-role="assistant"], [data-user-message-bubble]');
    return [triggeringUser, timeoutMessage, newerUser];
  }
};
assert.equal(dom.findRecoverableAssistantError(staleAfterUserRoot), null);

const newerAssistant = element({
  text: "Later successful response",
  attrs: {
    "data-message-author-role": "assistant",
    "data-message-id": "later-assistant"
  }
});
const staleAfterAssistantRoot = {
  querySelectorAll(selector) {
    assert.equal(selector, '[data-message-author-role], [data-conversation-role="assistant"], [data-user-message-bubble]');
    return [triggeringUser, timeoutMessage, newerAssistant];
  }
};
assert.equal(dom.findRecoverableAssistantError(staleAfterAssistantRoot), null);

const timeoutWithoutRetryMessage = element({
  attrs: { "data-message-author-role": "assistant" },
  query: {
    ".text-token-text-error": element({
      text: "Message delivery timed out. Please try again."
    })
  }
});
const timeoutWithoutRetryRoot = {
  querySelectorAll(selector) {
    assert.equal(selector, '[data-message-author-role], [data-conversation-role="assistant"], [data-user-message-bubble]');
    return [triggeringUser, timeoutWithoutRetryMessage];
  }
};
assert.equal(dom.findRecoverableAssistantError(timeoutWithoutRetryRoot), null);

const unrelatedRetryMessage = element({
  attrs: { "data-message-author-role": "assistant" },
  query: {
    ".text-token-text-error": element({
      text: "Something went wrong. Retry",
      query: {
        'button[data-testid="regenerate-thread-error-button"]': retryButton
      },
      queryAll: { button: [retryButton] }
    })
  }
});
const unrelatedRetryRoot = {
  querySelectorAll(selector) {
    assert.equal(selector, '[data-message-author-role], [data-conversation-role="assistant"], [data-user-message-bubble]');
    return [triggeringUser, unrelatedRetryMessage];
  }
};
assert.equal(dom.findRecoverableAssistantError(unrelatedRetryRoot), null);


const currentExhaustionTurn = element({ attrs: { "data-turn-key": "turn-current-exhaustion" } });
const currentExhaustionMessage = element({
  attrs: { "data-conversation-role": "assistant" },
  query: { ".text-token-text-error": error }
});
currentExhaustionMessage.closest = (selector) => selector === "[data-turn-key]" ? currentExhaustionTurn : null;
const currentExhaustionRoot = {
  querySelectorAll(selector) {
    if (selector === '[data-message-author-role="assistant"], [data-conversation-role="assistant"]') {
      return [currentExhaustionMessage];
    }
    return [];
  }
};
found = dom.findConversationExhaustion(currentExhaustionRoot);
assert.ok(found);
assert.equal(found.assistantIdentity, "turn-current-exhaustion");

const mixedGroupedOldTurn = element({ attrs: { "data-turn-key": "mixed-grouped-old" } });
const mixedGroupedOldAssistant = element({ attrs: { "data-conversation-role": "assistant" }, text: "old" });
mixedGroupedOldAssistant.closest = (selector) => selector === "[data-turn-key]" ? mixedGroupedOldTurn : null;
const mixedGroupedUser = element({ attrs: { "data-user-message-bubble": "" }, text: "user" });
const mixedGroupedNewTurn = element({ attrs: { "data-turn-key": "mixed-grouped-new" }, query: { '[data-message-author-role="user"], [data-user-message-bubble]': mixedGroupedUser } });
mixedGroupedOldAssistant.compareDocumentPosition = (other) => other === mixedGroupedNewTurn ? 4 : 0;
mixedGroupedNewTurn.compareDocumentPosition = (other) => other === mixedGroupedOldAssistant ? 2 : 0;
const mixedGroupedRoot = {
  querySelectorAll(selector) {
    if (selector === '[data-message-author-role="assistant"], [data-conversation-role="assistant"]') return [mixedGroupedOldAssistant];
    if (selector === '[data-turn-key]') return [mixedGroupedOldTurn, mixedGroupedNewTurn];
    return [];
  }
};
assert.deepEqual(dom.messageElements(mixedGroupedRoot, "assistant"), [mixedGroupedOldAssistant, mixedGroupedNewTurn]);

const currentUser = element({
  text: "Bridge wake",
  attrs: { "data-user-message-bubble": "" }
});
const currentTimeoutTurn = element({ attrs: { "data-turn-key": "turn-current-timeout" } });
const currentTimeoutMessage = element({
  attrs: { "data-conversation-role": "assistant" },
  query: { ".text-token-text-error": timeoutError }
});
currentTimeoutMessage.closest = (selector) => selector === "[data-turn-key]" ? currentTimeoutTurn : null;
const currentTimeoutRoot = {
  querySelectorAll(selector) {
    if (selector === '[data-message-author-role], [data-conversation-role="assistant"], [data-user-message-bubble]') {
      return [currentUser, currentTimeoutMessage];
    }
    return [];
  }
};
found = dom.findRecoverableAssistantError(currentTimeoutRoot);
assert.ok(found);
assert.equal(found.assistantIdentity, "turn-current-timeout");
assert.equal(dom.messageRole(currentUser), "user");
assert.equal(dom.messageRole(currentTimeoutMessage), "assistant");

const groupedUserSelector = '[data-message-author-role="user"], [data-user-message-bubble]';
const groupedUser = element({ attrs: { "data-user-message-bubble": "" }, text: "[LAB:PAUSE]" });
const groupedTimeoutTurn = element({
  attrs: { "data-turn-key": "turn-grouped-timeout" },
  query: {
    [groupedUserSelector]: groupedUser,
    ".text-token-text-error": timeoutError
  }
});
const groupedTimeoutRoot = {
  querySelectorAll(selector) {
    if (selector === '[data-message-author-role="assistant"], [data-conversation-role="assistant"]') return [];
    if (selector === '[data-message-author-role], [data-conversation-role="assistant"], [data-user-message-bubble]') return [groupedUser];
    if (selector === '[data-turn-key]') return [groupedTimeoutTurn];
    return [];
  }
};
found = dom.findRecoverableAssistantError(groupedTimeoutRoot);
assert.ok(found, "grouped turn without assistant-role marker must still expose structured timeout recovery");
assert.equal(found.assistantIdentity, "turn-grouped-timeout");
assert.deepEqual(dom.messageElements(groupedTimeoutRoot, "assistant"), [groupedTimeoutTurn]);

const groupedExhaustionTurn = element({
  attrs: { "data-turn-key": "turn-grouped-exhaustion" },
  query: {
    [groupedUserSelector]: groupedUser,
    ".text-token-text-error": error
  }
});
const groupedExhaustionRoot = {
  querySelectorAll(selector) {
    if (selector === '[data-message-author-role="assistant"], [data-conversation-role="assistant"]') return [];
    if (selector === '[data-turn-key]') return [groupedExhaustionTurn];
    return [];
  }
};
found = dom.findConversationExhaustion(groupedExhaustionRoot);
assert.ok(found, "grouped turn without assistant-role marker must still expose structured exhaustion");
assert.equal(found.assistantIdentity, "turn-grouped-exhaustion");


const mixedLegacyAssistantTurn = element({ attrs: { "data-turn-key": "turn-mixed-legacy" } });
const mixedLegacyAssistant = element({
  text: "Older legacy answer",
  attrs: {
    "data-message-author-role": "assistant",
    "data-message-id": "mixed-legacy-assistant"
  }
});
mixedLegacyAssistant.closest = (selector) => selector === "[data-turn-key]" ? mixedLegacyAssistantTurn : null;
const mixedCurrentTurn = element({ attrs: { "data-turn-key": "turn-mixed-current" } });
const mixedCurrentTimeout = element({
  attrs: { "data-conversation-role": "assistant" },
  query: { ".text-token-text-error": timeoutError }
});
mixedCurrentTimeout.closest = (selector) => selector === "[data-turn-key]" ? mixedCurrentTurn : null;
const mixedRoot = {
  querySelectorAll(selector) {
    if (selector === '[data-message-author-role], [data-conversation-role="assistant"], [data-user-message-bubble]') {
      return [triggeringUser, mixedLegacyAssistant, mixedCurrentTimeout];
    }
    if (selector === '[data-message-author-role="assistant"], [data-conversation-role="assistant"]') {
      return [mixedLegacyAssistant, mixedCurrentTimeout];
    }
    return [];
  }
};
found = dom.findRecoverableAssistantError(mixedRoot);
assert.ok(found, "new current-role timeout must outrank an older legacy-role assistant turn");
assert.equal(found.assistantIdentity, "turn-mixed-current");
assert.equal(dom.messageElements(mixedRoot, "assistant").at(-1), mixedCurrentTimeout);

const duplicateTurn = element({ attrs: { "data-turn-key": "turn-duplicate" } });
const duplicateOuter = element({ attrs: { "data-message-author-role": "assistant" } });
const duplicateInner = element({ attrs: { "data-conversation-role": "assistant" } });
duplicateOuter.closest = duplicateInner.closest = (selector) => selector === "[data-turn-key]" ? duplicateTurn : null;
const duplicateRoot = {
  querySelectorAll(selector) {
    if (selector === '[data-message-author-role="assistant"], [data-conversation-role="assistant"]') {
      return [duplicateOuter, duplicateInner, mixedCurrentTimeout];
    }
    return [];
  }
};
assert.deepEqual(dom.messageElements(duplicateRoot, "assistant"), [duplicateOuter, mixedCurrentTimeout]);

const persistedIdentityTurn = element({ attrs: { "data-turn-key": "turn-persisted" } });
const persistedIdentityMessage = element({
  attrs: {
    "data-message-author-role": "assistant",
    "data-message-id": "assistant-v8-persisted"
  }
});
persistedIdentityMessage.closest = (selector) => selector === "[data-turn-key]" ? persistedIdentityTurn : null;
assert.equal(
  dom.assistantIdentity(persistedIdentityMessage, 7),
  "assistant-v8-persisted",
  "data-message-id must remain authoritative when present so persisted baselines/dedupe survive upgrade"
);

console.log("Chat Bridge DOM contract tests passed.");