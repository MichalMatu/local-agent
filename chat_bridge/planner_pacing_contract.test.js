"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const protocol = require("./control_protocol.js");
const runtime = require("./runtime.example.json");

// Short LAB NEXT remains parseable only as legacy/operator compatibility. It is not
// the autonomous scheduling transport for GitHub-managed conversations.
const explicitShortWake = protocol.parseAssistantControl("[LAB:NEXT=30s]");
assert.equal(explicitShortWake?.action, "next");
assert.equal(explicitShortWake?.seconds, 30, "legacy short NEXT remains compatibility protocol");

for (const [name, prompt] of [
  ["bootstrap_prompt", runtime.bootstrap_prompt],
  ["wake_prompt", runtime.wake_prompt]
]) {
  assert.match(prompt, /do not poll (?:it )?at 30-second cadence/i, `${name} must reject 30-second healthy-task polling`);
  assert.match(prompt, /at least 2 minutes/i, `${name} must define the autonomous early recheck floor`);
  assert.match(prompt, /5-10 minutes/i, `${name} must define normal multi-minute build\/test pacing`);
  assert.match(prompt, /cancel .*task/i, `${name} must tell the planner to stop demonstrably doomed work`);
  assert.match(prompt, /conversation_controls/i, `${name} must route managed pacing through GitHub desired state`);
  assert.match(prompt, /LAB schedule markers.*legacy|legacy.*LAB schedule markers/i, `${name} must mark assistant LAB scheduling as legacy`);
}

const autonomous = fs.readFileSync(path.join(__dirname, "..", "docs", "AUTONOMOUS_CHAT_LOOP.md"), "utf8");
assert.match(autonomous, /GitHub is authoritative for:[\s\S]*STATUS[\s\S]*PAUSE[\s\S]*RESUME[\s\S]*NEXT[\s\S]*INTERVAL/);
assert.match(autonomous, /Every schedule mutation increments `control_generation`/);
assert.match(autonomous, /Do \*\*not\*\* emit assistant LAB schedule markers/);
assert.match(autonomous, /no sooner than about two minutes/i);
assert.match(autonomous, /5-10 minutes/i);
assert.match(autonomous, /repository-scoped cancellation|repository-scoped `cancel_task`|cancel that exact task/i);
assert.doesNotMatch(autonomous, /\[LAB:NEXT=2m\]/, "canonical planner docs must not prescribe LAB scheduling");
assert.doesNotMatch(autonomous, /prefer one early re-check around 30 seconds/i);

console.log("Chat Bridge planner pacing contract tests passed (GitHub-backed scheduling; LAB compatibility retained).");
