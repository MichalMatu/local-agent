"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const protocol = require("./control_protocol.js");
const runtime = require("./runtime.example.json");

const explicitShortWake = protocol.parseAssistantControl("[LAB:NEXT=30s]");
assert.equal(explicitShortWake?.action, "next");
assert.equal(explicitShortWake?.seconds, 30, "explicit short NEXT remains compatibility protocol");

for (const [name, prompt] of [
  ["bootstrap_prompt", runtime.bootstrap_prompt],
  ["wake_prompt", runtime.wake_prompt]
]) {
  assert.match(prompt, /do not poll (?:it )?at 30-second cadence/i, `${name} must reject 30-second healthy-task polling`);
  assert.match(prompt, /at least 2 minutes/i, `${name} must define the autonomous early recheck floor`);
  assert.match(prompt, /5-10 minutes/i, `${name} must define normal multi-minute build\/test pacing`);
  assert.match(prompt, /cancel .*task/i, `${name} must tell the planner to stop demonstrably doomed work`);
}

const autonomous = fs.readFileSync(path.join(__dirname, "..", "docs", "AUTONOMOUS_CHAT_LOOP.md"), "utf8");
assert.match(autonomous, /Do not use 30-second polling for healthy executor work/);
assert.match(autonomous, /\[LAB:NEXT=2m\]/);
assert.match(autonomous, /5-10 minute `NEXT` intervals/);
assert.match(autonomous, /publish one repository-scoped `cancel_task` request/);
assert.doesNotMatch(autonomous, /prefer one early re-check around 30 seconds/i);

console.log("Chat Bridge planner pacing contract tests passed.");
