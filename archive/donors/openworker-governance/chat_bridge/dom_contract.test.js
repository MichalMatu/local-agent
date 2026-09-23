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

console.log("Chat Bridge DOM contract tests passed.");
