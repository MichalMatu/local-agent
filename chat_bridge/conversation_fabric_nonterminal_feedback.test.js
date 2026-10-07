"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

class FakeTextArea {
  constructor() {
    this._value = "";
  }
  get value() { return this._value; }
  set value(next) { this._value = String(next); }
  focus() {}
  dispatchEvent() {}
  closest(selector) { return selector === "form" ? form : null; }
}

class FakeButton {
  constructor(onClick) {
    this.disabled = false;
    this.isConnected = true;
    this._onClick = onClick;
  }
  click() { this._onClick(); }
}

const parentUrl = "https://chatgpt.com/c/nonterminal-feedback-parent";
const assistantText = "delegate-control";
const userMessage = { innerText: "", textContent: "" };
const composer = new FakeTextArea();
let intervalCallback = null;
let controlCalls = 0;
let feedbackAckCalls = 0;
let retryDefers = 0;

const sendButton = new FakeButton(() => {
  userMessage.innerText = composer.value;
  userMessage.textContent = composer.value;
  composer.value = "";
});
const form = { querySelector: () => sendButton };
const assistantMessage = {
  id: "assistant-turn",
  innerText: assistantText,
  textContent: assistantText,
  closest() { return this; },
  cloneNode() {
    return {
      textContent: assistantText,
      querySelectorAll() { return []; }
    };
  },
  getAttribute(name) { return name === "data-turn-key" ? "assistant-turn" : null; }
};

const document = {
  body: {},
  documentElement: {},
  visibilityState: "visible",
  querySelectorAll(selector) {
    if (selector.includes("stop-button")) return [];
    if (selector.includes('data-message-author-role="assistant"')) return [assistantMessage];
    if (selector.includes('data-message-author-role="user"') || selector.includes("data-user-message-bubble")) {
      return userMessage.innerText ? [userMessage] : [];
    }
    if (selector === "[data-turn-key]") return [assistantMessage];
    return [];
  },
  querySelector(selector) {
    if (selector === "#prompt-textarea") return composer;
    return null;
  },
  createRange() {
    return { selectNodeContents() {} };
  },
  execCommand() { return true; }
};

const context = vm.createContext({
  console,
  document,
  location: { href: parentUrl },
  HTMLTextAreaElement: FakeTextArea,
  HTMLInputElement: class FakeInput {},
  HTMLElement: class FakeElement {},
  HTMLButtonElement: FakeButton,
  Event: class FakeEvent {},
  InputEvent: class FakeInputEvent {},
  MutationObserver: class FakeMutationObserver {
    observe() {}
    disconnect() {}
  },
  setTimeout(fn) { fn(); return 1; },
  clearTimeout() {},
  setInterval(fn) { intervalCallback = fn; return 1; },
  clearInterval() {},
  window: { getSelection: () => null },
  chrome: {
    runtime: {
      async sendMessage(message) {
        if (message.type === "bridge:conversation-fabric-control") {
          controlCalls += 1;
          return {
            ok: true,
            reason: "conversation_fabric_started",
            campaignId: "cf-1234567890abcdef",
            feedbackPrompt: "campaign started feedback"
          };
        }
        if (message.type === "bridge:conversation-fabric-feedback") {
          feedbackAckCalls += 1;
          return { ok: false, reason: "conversation_fabric_running" };
        }
        throw new Error(`unexpected message type: ${message.type}`);
      }
    }
  }
});
context.globalThis = context;
context.LocalAgentBridgeProtocol = {
  CONTENT_PROTOCOL_VERSION: 1,
  normalizeConversationUrl: value => String(value || ""),
  controlFingerprint: () => "12345678",
  fnv1a32: () => "abcdef12"
};
context.LocalAgentConversationFabricProtocol = {
  MAX_PROMPT_CHARS: 20000,
  parseConversationFabricControl: () => ({
    action: "delegate",
    children: [{ id: "child", role: "research", prompt: "task" }]
  })
};
context.LocalAgentBridgeContentRetry = {
  createRetryGate() {
    return {
      canAttempt: () => true,
      defer() { retryDefers += 1; },
      reset() {}
    };
  }
};

vm.runInContext(
  fs.readFileSync(path.join(__dirname, "conversation_fabric_content.js"), "utf8"),
  context,
  { filename: "conversation_fabric_content.js" }
);

(async () => {
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(controlCalls, 1);
  assert.equal(feedbackAckCalls, 0, "started/pending feedback must not use terminal ACK");
  assert.equal(retryDefers, 0);
  assert.equal(userMessage.innerText, "", "nonterminal Fabric status must never become a parent user turn");
  assert.equal(composer.value, "", "nonterminal Fabric status must never leave a parent draft");

  assert.ok(intervalCallback, "content retry interval should be installed");
  intervalCallback();
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(controlCalls, 1, "settled nonterminal feedback must not resubmit the same control");
  assert.equal(feedbackAckCalls, 0);

  console.log("Conversation Fabric nonterminal feedback tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
