"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const protocol = require("./control_protocol.js");
const runtime = require("./runtime.example.json");
const { createHarness } = require("./worker_test_harness.js");

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

// The candidate must remain correct even while the production chat-bridge-state branch
// still serves its pre-event-wake NEXT guidance. Capability-specific policy is appended by
// the candidate extension and therefore does not require mutating production runtime state.
const harness = createHarness();
const normalizedAgents = harness.runtimeAgents.map((agent) => ({
  repositoryId: agent.repository_id,
  repository: agent.repository,
  agentBinding: agent.agent_binding,
  executionEnabled: agent.execution_enabled
}));
const conversation = {
  id: "chat-1234abcd",
  repositoryId: "matrixhub",
  repository: "MichalMatu/MatrixHub",
  agentBinding: harness.MATRIX_BINDING,
  bootstrapPending: true
};
const legacyRuntime = {
  bootstrapPrompt: "LEGACY RUNTIME: poll healthy work with NEXT every few minutes.",
  wakePrompt: "LEGACY WAKE: continue polling with NEXT.",
  agents: normalizedAgents
};
const bootstrap = harness.evaluate(
  `buildBootstrapPrompt(${JSON.stringify(legacyRuntime)}, ${JSON.stringify(conversation)})`
);
const wake = harness.evaluate(
  `buildWakePrompt(${JSON.stringify(legacyRuntime)}, ${JSON.stringify({ ...conversation, bootstrapPending: false })})`
);
for (const [name, prompt, legacyMarker] of [
  ["candidate bootstrap", bootstrap, legacyRuntime.bootstrapPrompt],
  ["candidate wake", wake, legacyRuntime.wakePrompt]
]) {
  assert.ok(prompt.includes(legacyMarker), `${name} must preserve valid remote planner context`);
  assert.match(prompt, /prefer \[LAB:WAIT_TASK=<task-id>\]/i,
    `${name} must append candidate-owned exact task waiting policy`);
  assert.match(prompt, /Use NEXT only for genuinely time-based or external rechecks/i);
  assert.match(prompt, /task_result_ready event is only a wake hint/i);
  assert.ok(
    prompt.lastIndexOf("WAIT_TASK") > prompt.indexOf(legacyMarker),
    `${name} must place candidate event-wake policy after legacy runtime pacing text`
  );
}

const autonomous = fs.readFileSync(path.join(__dirname, "..", "docs", "AUTONOMOUS_CHAT_LOOP.md"), "utf8");
assert.match(autonomous, /\[LAB:WAIT_TASK=<task-id>\]/);
assert.match(autonomous, /event-driven/i);
assert.match(autonomous, /scheduled reconciliation|alarm fallback/i);
assert.match(autonomous, /publish one repository-scoped `cancel_task` request/);
assert.match(autonomous, /event.*wake hint|wake hint.*event/i);
assert.doesNotMatch(autonomous, /After queueing, use one early autonomous re-check no sooner than about two minutes/i);

console.log("Chat Bridge planner pacing contract tests passed.");
