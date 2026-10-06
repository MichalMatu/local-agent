"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = __dirname;
const parentUrl = "https://chatgpt.com/c/control-diagnostics-parent";

function createHarness({ assistantText, workerResponse, managed = true }) {
  let intervalCallback = null;
  let controlCalls = 0;
  let retryDefers = 0;
  const submitted = [];

  class FakeTextArea {
    constructor() { this._value = ""; }
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

  const composer = new FakeTextArea();
  const userMessages = [];
  const sendButton = new FakeButton(() => {
    userMessages.push({
      innerText: composer.value,
      textContent: composer.value
    });
    submitted.push(composer.value);
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
        return userMessages;
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
          if (message.type === "bridge:conversation-fabric-diagnostic-context") {
            return managed
              ? { ok: true, reason: "conversation_fabric_diagnostic_ready" }
              : { ok: false, reason: "conversation_fabric_parent_not_managed" };
          }
          if (message.type !== "bridge:conversation-fabric-control") {
            throw new Error(`unexpected message type: ${message.type}`);
          }
          controlCalls += 1;
          return workerResponse;
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
    fs.readFileSync(path.join(root, "conversation_fabric_protocol.js"), "utf8"),
    context,
    { filename: "conversation_fabric_protocol.js" }
  );
  vm.runInContext(
    fs.readFileSync(path.join(root, "conversation_fabric_content.js"), "utf8"),
    context,
    { filename: "conversation_fabric_content.js" }
  );

  return {
    interval: () => intervalCallback,
    controlCalls: () => controlCalls,
    retryDefers: () => retryDefers,
    submitted
  };
}

async function flush() {
  await new Promise((resolve) => setImmediate(resolve));
}

(async () => {
  const delegate = {
    schema_version: 1,
    action: "delegate",
    children: [
      { id: "audit", role: "research", prompt: "Inspect one bounded concern." }
    ]
  };

  {
    const h = createHarness({
      assistantText: [
        "Delegating.",
        "<<<LOCAL_AGENT_CF",
        JSON.stringify(delegate),
        "LOCAL_AGENT_CF>>>",
        "this trailing prose makes the control unsupported"
      ].join("\n"),
      workerResponse: { ok: true }
    });
    await flush();
    assert.equal(h.controlCalls(), 0, "non-terminal visible control must be rejected before worker dispatch");
    assert.equal(h.submitted.length, 1);
    assert.match(h.submitted[0], /Conversation Fabric control rejected: reason=control_not_terminal/);
    assert.match(h.submitted[0], /final non-whitespace content/);
    assert.equal(h.retryDefers(), 0);

    h.interval()();
    await flush();
    assert.equal(h.controlCalls(), 0);
    assert.equal(h.submitted.length, 1, "same malformed assistant turn must not spam diagnostics");
  }

  {
    const h = createHarness({
      assistantText: [
        "Delegating.",
        "<<<LOCAL_AGENT_CF",
        JSON.stringify(delegate),
        "LOCAL_AGENT_CF>>>"
      ].join("\n"),
      workerResponse: {
        ok: false,
        reason: "conversation_fabric_parent_busy",
        error: "existing campaign is still active"
      }
    });
    await flush();
    assert.equal(h.controlCalls(), 1);
    assert.equal(h.submitted.length, 1);
    assert.match(h.submitted[0], /Conversation Fabric control rejected: reason=conversation_fabric_parent_busy/);
    assert.match(h.submitted[0], /existing campaign is still active/);
    assert.equal(h.retryDefers(), 0, "explicit worker rejection is an ACK, not a transport retry");

    h.interval()();
    await flush();
    assert.equal(h.controlCalls(), 1, "deterministic worker rejection must settle the assistant turn");
    assert.equal(h.submitted.length, 1);
  }

  {
    const h = createHarness({
      assistantText: [
        "<<<LOCAL_AGENT_CF",
        JSON.stringify(delegate),
        "LOCAL_AGENT_CF>>>",
        "trailing prose"
      ].join("\n"),
      workerResponse: { ok: true },
      managed: false
    });
    await flush();
    assert.equal(h.controlCalls(), 0);
    assert.equal(h.submitted.length, 0, "unmanaged chat must not receive local Fabric diagnostic turns");
    assert.equal(h.retryDefers(), 0);
  }

  console.log("Conversation Fabric control diagnostic tests passed.");
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
