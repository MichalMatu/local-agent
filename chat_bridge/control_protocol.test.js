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
assert.deepEqual(parse("Waiting for user.\n[LOCAL_AGENT_BRIDGE:PAUSE]"), {
  action: "pause",
  marker: "[LOCAL_AGENT_BRIDGE:PAUSE]"
});
assert.deepEqual(parse("Continue.\n[LOCAL_AGENT_BRIDGE:RESUME]"), {
  action: "resume",
  marker: "[LOCAL_AGENT_BRIDGE:RESUME]"
});
assert.deepEqual(parse("Long task.\n[LOCAL_AGENT_BRIDGE:INTERVAL=30]"), {
  action: "interval",
  mode: "fixed",
  minutes: 30,
  marker: "[LOCAL_AGENT_BRIDGE:INTERVAL=30]"
});
assert.deepEqual(parse("Return to runtime.\n[LOCAL_AGENT_BRIDGE:INTERVAL=AUTO]"), {
  action: "interval",
  mode: "auto",
  marker: "[LOCAL_AGENT_BRIDGE:INTERVAL=AUTO]"
});

assert.equal(parse("[LOCAL_AGENT_BRIDGE:INTERVAL=0]"), null);
assert.equal(parse("[LOCAL_AGENT_BRIDGE:INTERVAL=1441]"), null);
assert.equal(parse("[LOCAL_AGENT_BRIDGE:STOP]\nThis is only an example."), null);
assert.equal(parse("prefix [LOCAL_AGENT_BRIDGE:STOP]"), null);
assert.equal(parse("No control marker."), null);

assert.equal(
  protocol.normalizeConversationUrl("https://chatgpt.com/c/example?x=1#fragment"),
  "https://chatgpt.com/c/example"
);
assert.equal(protocol.normalizeConversationUrl("http://chatgpt.com/c/example"), "");
assert.equal(protocol.normalizeConversationUrl("https://example.com/c/example"), "");

const control = parse("Done.\n[LOCAL_AGENT_BRIDGE:STOP]");
const first = protocol.controlFingerprint(
  "https://chatgpt.com/c/example",
  "Done.\n[LOCAL_AGENT_BRIDGE:STOP]",
  control
);
const same = protocol.controlFingerprint(
  "https://chatgpt.com/c/example?ignored=1",
  "Done.\n[LOCAL_AGENT_BRIDGE:STOP]",
  control
);
const different = protocol.controlFingerprint(
  "https://chatgpt.com/c/example",
  "Different.\n[LOCAL_AGENT_BRIDGE:STOP]",
  control
);
assert.equal(first, same);
assert.notEqual(first, different);

console.log("Chat Bridge control protocol tests passed.");
