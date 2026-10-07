"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const stored = {};
const validParent = "https://chatgpt.com/c/fabric-diag-parent";
const validSender = { id: "extension-id", frameId: 0, tab: { id: 42, url: validParent } };
const protocol = require("./control_protocol.js");
let queue = Promise.resolve();

const context = vm.createContext({
  chrome: {
    runtime: { id: "extension-id" },
    storage: {
      local: {
        async get(key) { return { [key]: stored[key] }; },
        async set(items) { Object.assign(stored, items); }
      }
    }
  },
  protocol,
  normalizeConversationUrl: (value) => value === validParent ? value : "",
  conversationId: (_url) => "chat-01234567",
  conversationFabricDiagnosticContext: async (message, sender) =>
    sender?.id === "extension-id" &&
    sender?.frameId === 0 &&
    sender?.tab?.id === 42 &&
    sender?.tab?.url === validParent &&
    message?.contentProtocolVersion === 25 &&
    message?.conversationUrl === validParent
      ? { ok: true }
      : { ok: false, reason: "invalid_sender" },
  serializeConversationFabric: (_key, action) => {
    const pending = queue.then(action);
    queue = pending.catch(() => undefined);
    return pending;
  }
});
vm.runInContext(fs.readFileSync(require.resolve("./worker_conversation_fabric_diagnostics.js"), "utf8"), context);

const record = (event, reason, sender = validSender) =>
  context.reportConversationFabricDiagnostic({
    conversationUrl: validParent,
    contentProtocolVersion: 25,
    event,
    reason,
    bootstrap_text: "secret bootstrap text must not persist",
    agent_binding: "never record this authority"
  }, sender);

(async () => {
  assert.equal((await record("control_rejected", "control_schema_invalid")).ok, true);
  const current = await context.conversationFabricDiagnosticSnapshot();
  assert.equal(current["chat-01234567"].event, "control_rejected");
  assert.equal(current["chat-01234567"].reason, "control_schema_invalid");
  assert.match(current["chat-01234567"].at, /^\d{4}-\d\d-\d\dT/);
  assert.doesNotMatch(JSON.stringify(stored), /secret bootstrap|agent_binding/);

  assert.equal((await record("control_worker_rejected", "conversation_fabric_parent_busy")).ok, true);
  assert.equal(
    (await context.conversationFabricDiagnosticSnapshot())["chat-01234567"].reason,
    "conversation_fabric_parent_busy"
  );
  assert.equal((await record("control_transport_failed", "message_failed", { id: "external" })).ok, false);
  assert.equal((await record("arbitrary_exec", "disallowed")).ok, false);
  assert.equal((await record("control_rejected", "invalid reason with spaces")).ok, false);
  assert.equal(
    (await context.conversationFabricDiagnosticSnapshot())["chat-01234567"].event,
    "control_worker_rejected"
  );

  const recent = Object.fromEntries(Array.from({ length: 128 }, (_, i) => [
    "chat-" + i.toString(16).padStart(8, "0"),
    { event: "control_accepted", reason: "accepted", at: new Date(i * 1000).toISOString() }
  ]));
  stored.bridgeConversationFabricDiagnosticsV1 = recent;
  await record("control_accepted", "conversation_fabric_started");
  assert.equal(Object.keys(await context.conversationFabricDiagnosticSnapshot()).length, 128);
  assert.equal(
    (await context.conversationFabricDiagnosticSnapshot())["chat-01234567"].reason,
    "conversation_fabric_started"
  );
  assert.deepEqual(
    Object.keys(stored).filter((key) => key.startsWith("conversation-fabric-campaign:")),
    []
  );
  console.log("Conversation Fabric diagnostic evidence tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
