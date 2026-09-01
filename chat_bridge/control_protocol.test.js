"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");

function parse(text) {
  return protocol.parseAssistantControl(text);
}

assert.deepEqual(parse("Done.\n\n[LOCAL_AGENT_BRIDGE:STOP]"), {
  action: "stop",
  marker: "[LOCAL_AGENT_BRIDGE:STOP]"
});
assert.deepEqual(parse("Done.\n[LAB:STOP]"), {
  action: "stop",
  marker: "[LAB:STOP]"
});
assert.deepEqual(parse("Waiting for user.\n[LAB:PAUSE]"), {
  action: "pause",
  marker: "[LAB:PAUSE]"
});
assert.deepEqual(parse("Continue.\n[LAB:RESUME]"), {
  action: "resume",
  marker: "[LAB:RESUME]"
});
assert.deepEqual(parse("Long task.\n[LOCAL_AGENT_BRIDGE:INTERVAL=30]"), {
  action: "interval",
  mode: "fixed",
  minutes: 30,
  marker: "[LOCAL_AGENT_BRIDGE:INTERVAL=30]"
});
assert.deepEqual(parse("Long task.\n[LAB:INTERVAL=30m]"), {
  action: "interval",
  mode: "fixed",
  minutes: 30,
  marker: "[LAB:INTERVAL=30m]"
});
assert.deepEqual(parse("Return to runtime.\n[LAB:INTERVAL=AUTO]"), {
  action: "interval",
  mode: "auto",
  marker: "[LAB:INTERVAL=AUTO]"
});
assert.deepEqual(parse("Check soon.\n[LAB:NEXT=30s]"), {
  action: "next",
  seconds: 30,
  marker: "[LAB:NEXT=30s]"
});
assert.deepEqual(parse("Check later.\n[LOCAL_AGENT_BRIDGE:NEXT=10m]"), {
  action: "next",
  seconds: 600,
  marker: "[LOCAL_AGENT_BRIDGE:NEXT=10m]"
});

assert.equal(parse("[LAB:NEXT=29s]"), null);
assert.equal(parse("[LAB:NEXT=1441m]"), null);
assert.equal(parse("[LOCAL_AGENT_BRIDGE:INTERVAL=0]"), null);
assert.equal(parse("[LOCAL_AGENT_BRIDGE:INTERVAL=1441]"), null);
assert.equal(parse("[LAB:STOP]\nThis is only an example."), null);
assert.equal(parse("prefix [LAB:STOP]"), null);
assert.equal(parse("No control marker."), null);

assert.equal(
  protocol.normalizeConversationUrl("https://chatgpt.com/c/example?x=1#fragment"),
  "https://chatgpt.com/c/example"
);
assert.equal(
  protocol.normalizeConversationUrl("https://chat.openai.com/c/example"),
  "https://chatgpt.com/c/example"
);
assert.equal(protocol.normalizeConversationUrl("https://chatgpt.com/"), "");
assert.equal(protocol.normalizeConversationUrl("http://chatgpt.com/c/example"), "");
assert.equal(protocol.normalizeConversationUrl("https://example.com/c/example"), "");
assert.equal(protocol.conversationId("https://chatgpt.com/c/example").startsWith("chat-"), true);

const control = parse("Done.\n[LAB:STOP]");
const first = protocol.controlFingerprint(
  "https://chatgpt.com/c/example",
  "Done.\n[LAB:STOP]",
  control,
  "assistant-4"
);
const same = protocol.controlFingerprint(
  "https://chat.openai.com/c/example?ignored=1",
  "Done.\n[LAB:STOP]",
  control,
  "assistant-4"
);
const laterSameText = protocol.controlFingerprint(
  "https://chatgpt.com/c/example",
  "Done.\n[LAB:STOP]",
  control,
  "assistant-5"
);
assert.equal(first, same);
assert.notEqual(first, laterSameText);

console.log("Chat Bridge control protocol tests passed.");
