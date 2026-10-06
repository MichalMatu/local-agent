"use strict";

const assert = require("node:assert/strict");
const protocol = require("./conversation_fabric_protocol.js");

function block(payload, suffix = "") {
  return `Parent text\n${protocol.OPEN}${JSON.stringify(payload)}${protocol.CLOSE}${suffix}`;
}

const delegate = {
  schema_version: 1,
  action: "delegate",
  children: [
    { id: "audit", role: "research", prompt: "Inspect the bounded architecture." },
    { id: "verify", role: "verification", prompt: "Verify the independent invariants." }
  ]
};

{
  const parsed = protocol.parseConversationFabricControl(block(delegate, "\n"));
  assert.ok(parsed);
  assert.equal(parsed.action, "delegate");
  assert.deepEqual(parsed.children.map((child) => child.id), ["audit", "verify"]);
  assert.match(parsed.marker, /^<<<LOCAL_AGENT_CF/);
}

{
  const parsed = protocol.parseConversationFabricControl(block({
    schema_version: 1,
    action: "collect",
    campaign_id: "cf-0123456789abcdef"
  }));
  assert.ok(parsed);
  assert.equal(parsed.action, "collect");
  assert.equal(parsed.campaign_id, "cf-0123456789abcdef");
}

{
  const recent = protocol.parseConversationFabricControl(block({
    schema_version: 1,
    action: "inspect"
  }));
  assert.ok(recent);
  assert.deepEqual(
    { schema_version: recent.schema_version, action: recent.action },
    { schema_version: 1, action: "inspect" }
  );

  const campaign = protocol.parseConversationFabricControl(block({
    schema_version: 1,
    action: "inspect",
    campaign_id: "cf-0123456789abcdef"
  }));
  assert.equal(campaign.campaign_id, "cf-0123456789abcdef");

  const child = protocol.parseConversationFabricControl(block({
    schema_version: 1,
    action: "inspect",
    campaign_id: "cf-0123456789abcdef",
    child_id: "verify"
  }));
  assert.equal(child.child_id, "verify");
}

{
  const retire = protocol.parseConversationFabricControl(block({
    schema_version: 1,
    action: "retire",
    campaign_id: "cf-0123456789abcdef",
    child_id: "stuck-child"
  }));
  assert.ok(retire);
  assert.equal(retire.action, "retire");
  assert.equal(retire.child_id, "stuck-child");
}

assert.equal(protocol.parseConversationFabricControl(block(delegate, " trailing text")), null);
assert.equal(protocol.parseConversationFabricControl("ordinary assistant reply"), null);

{
  const absent = protocol.diagnoseConversationFabricControl("ordinary assistant reply");
  assert.equal(absent.present, false);
  assert.equal(absent.reason, "control_absent");

  const trailing = protocol.diagnoseConversationFabricControl(block(delegate, " trailing text"));
  assert.equal(trailing.present, true);
  assert.equal(trailing.ok, false);
  assert.equal(trailing.reason, "control_not_terminal");

  const missingClose = protocol.diagnoseConversationFabricControl(
    `${protocol.OPEN}${JSON.stringify(delegate)}`
  );
  assert.equal(missingClose.reason, "control_close_missing");
  assert.match(missingClose.detail, /literal closing delimiter LOCAL_AGENT_CF>>>/);
  assert.match(missingClose.detail, /Do not add a control_close field/);

  const invalidJson = protocol.diagnoseConversationFabricControl(
    `${protocol.OPEN}{not-json}${protocol.CLOSE}`
  );
  assert.equal(invalidJson.reason, "control_json_invalid");

  const invalidSchema = protocol.diagnoseConversationFabricControl(
    block({ schema_version: 1, action: "collect", campaign_id: "wrong" })
  );
  assert.equal(invalidSchema.reason, "control_schema_invalid");

  const redundantCloseField = protocol.diagnoseConversationFabricControl(
    block({ ...delegate, control_close: true })
  );
  assert.equal(redundantCloseField.ok, true);
  assert.equal(redundantCloseField.control.action, "delegate");
  assert.equal(Object.hasOwn(redundantCloseField.control, "control_close"), false);

  const invalidCloseField = protocol.diagnoseConversationFabricControl(
    block({ ...delegate, control_close: false })
  );
  assert.equal(invalidCloseField.reason, "control_schema_invalid");
  assert.match(invalidCloseField.detail, /unexpected keys: control_close/);

  const valid = protocol.diagnoseConversationFabricControl(block(delegate));
  assert.equal(valid.ok, true);
  assert.equal(valid.reason, "control_valid");
  assert.equal(valid.control.action, "delegate");
}

assert.equal(protocol.parseConversationFabricControl(block({ ...delegate, extra: true })), null);
assert.ok(protocol.parseConversationFabricControl(block({ ...delegate, control_close: true })));
assert.equal(protocol.parseConversationFabricControl(block({ ...delegate, control_close: false })), null);
assert.equal(protocol.parseConversationFabricControl(block({
  ...delegate,
  children: [...delegate.children, delegate.children[0]]
})), null);
assert.equal(protocol.parseConversationFabricControl(block({
  ...delegate,
  children: [{ id: "audit", role: "executor", prompt: "No." }]
})), null);
assert.equal(protocol.parseConversationFabricControl(block({
  ...delegate,
  children: [{ id: "audit", role: "research", prompt: "x".repeat(protocol.MAX_PROMPT_CHARS + 1) }]
})), null);
assert.equal(protocol.parseConversationFabricControl(block({
  schema_version: 1,
  action: "collect",
  campaign_id: "wrong"
})), null);
assert.equal(protocol.parseConversationFabricControl(block({
  schema_version: 1,
  action: "inspect",
  campaign_id: "cf-0123456789abcdef",
  child_id: "bad child id"
})), null);
assert.equal(protocol.parseConversationFabricControl(block({
  schema_version: 1,
  action: "retire",
  campaign_id: "wrong",
  child_id: "verify"
})), null);

console.log("Conversation Fabric protocol tests passed.");

assert.ok(protocol.parseConversationFabricControl("<<<LOCAL_AGENT_CF " + JSON.stringify(delegate) + " LOCAL_AGENT_CF>>>"), "rendered Markdown may collapse separator line breaks");

assert.equal(protocol.validateControl({ ...delegate, children: [{ id: "a", role: "research", prompt: {text: "invalid"} }] }), null);
