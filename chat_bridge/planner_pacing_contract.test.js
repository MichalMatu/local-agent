"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const protocol = require("./control_protocol.js");
const runtime = require("./runtime.example.json");

const explicitShortWake = protocol.parseAssistantControl("[LAB:NEXT=30s]");
assert.equal(explicitShortWake?.action, "next");
assert.equal(explicitShortWake?.seconds, 30, "explicit short NEXT remains compatibility protocol");

const waitTask = protocol.parseAssistantControl("[LAB:WAIT_TASK=build-17]");
assert.equal(waitTask?.action, "wait_task");
assert.equal(waitTask?.taskId, "build-17");

for (const [name, prompt] of [
  ["bootstrap_prompt", runtime.bootstrap_prompt],
  ["wake_prompt", runtime.wake_prompt]
]) {
  assert.match(prompt, /WAIT_TASK=<exact-task-id>/, `${name} must prefer exact task-result waiting`);
  assert.match(prompt, /alarm (?:as )?(?:reconciliation )?fallback|alarm fallback/i,
    `${name} must preserve bounded scheduled reconciliation`);
  assert.match(prompt, /Use NEXT only/i, `${name} must reserve NEXT for genuine time-based rechecks`);
  assert.match(prompt, /cancel .*task/i, `${name} must tell the planner to stop demonstrably doomed work`);
  assert.match(prompt, /exact terminal result|inspect the exact terminal result/i,
    `${name} must keep task-result events non-authoritative`);
}

const autonomous = fs.readFileSync(path.join(__dirname, "..", "docs", "AUTONOMOUS_CHAT_LOOP.md"), "utf8");
assert.match(autonomous, /\[LAB:WAIT_TASK=<task-id>\]/);
assert.match(autonomous, /event-driven/i);
assert.match(autonomous, /scheduled reconciliation|alarm fallback/i);
assert.match(autonomous, /publish one repository-scoped `cancel_task` request/);
assert.match(autonomous, /event.*wake hint|wake hint.*event/i);
assert.doesNotMatch(autonomous, /After queueing, use one early autonomous re-check no sooner than about two minutes/i);

console.log("Chat Bridge planner pacing contract tests passed.");
