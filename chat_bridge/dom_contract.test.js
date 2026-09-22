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
    assert.equal(selector, '[data-message-author-role="assistant"]');
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
    assert.equal(selector, "[data-message-author-role]");
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
    assert.equal(selector, "[data-message-author-role]");
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
    assert.equal(selector, "[data-message-author-role]");
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
    assert.equal(selector, "[data-message-author-role]");
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
    assert.equal(selector, "[data-message-author-role]");
    return [triggeringUser, unrelatedRetryMessage];
  }
};
assert.equal(dom.findRecoverableAssistantError(unrelatedRetryRoot), null);

const interruptedStatus = element({
  text: "Connection interrupted. Waiting for the complete answer"
});
const interruptedTurn = element({
  attrs: {
    "data-turn": "assistant",
    "data-turn-id": "request-connection-interrupted"
  },
  query: { ".mask-shimmer-muted": interruptedStatus }
});
const interruptedRoot = {
  querySelectorAll(selector) {
    if (selector === '[data-turn="assistant"]') return [interruptedTurn];
    if (selector === '[data-message-author-role="assistant"]') return [];
    if (selector === "[data-message-author-role]") return [];
    return [];
  }
};
found = dom.findAssistantTransientState(interruptedRoot);
assert.ok(found);
assert.equal(found.kind, "connection_interrupted");
assert.equal(found.assistantIdentity, "request-connection-interrupted");
assert.match(found.statusText, /Waiting for the complete answer/);
assert.equal(dom.findRecoverableAssistantError(interruptedRoot), null);

const extendedThinkingStatus = element({
  text: "Our systems are thinking a bit more about this request before responding. You can retry with a faster model for a quicker response. Learn more"
});
const extendedThinkingTurn = element({
  attrs: {
    "data-turn": "assistant",
    "data-turn-id": "request-extended-thinking"
  },
  query: { "[data-streaming-response-status]": extendedThinkingStatus }
});
const extendedThinkingRoot = {
  querySelectorAll(selector) {
    if (selector === '[data-turn="assistant"]') return [extendedThinkingTurn];
    if (selector === '[data-message-author-role="assistant"]') return [];
    if (selector === "[data-message-author-role]") return [];
    return [];
  }
};
found = dom.findAssistantTransientState(extendedThinkingRoot);
assert.ok(found);
assert.equal(found.kind, "extended_thinking");
assert.equal(found.assistantIdentity, "request-extended-thinking");
assert.match(found.statusText, /retry with a faster model/);
assert.equal(dom.findRecoverableAssistantError(extendedThinkingRoot), null,
  "the faster-model action is informational and must never enter native Retry recovery");

const quotedStatusTurn = element({
  text: `${dom.CONNECTION_INTERRUPTED_TEXT} ${dom.EXTENDED_THINKING_TEXT}`,
  attrs: { "data-turn": "assistant", "data-turn-id": "quoted-status" }
});
const quotedStatusRoot = {
  querySelectorAll(selector) {
    return selector === '[data-turn="assistant"]' ? [quotedStatusTurn] : [];
  }
};
assert.equal(dom.findAssistantTransientState(quotedStatusRoot), null,
  "status text without the captured structural container must not classify a normal answer");

console.log("Chat Bridge DOM contract tests passed.");