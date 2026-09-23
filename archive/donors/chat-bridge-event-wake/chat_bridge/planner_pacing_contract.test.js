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

// Remote runtime text teaches the generic planner/executor split without duplicating the
// candidate-owned WAIT_TASK/event policy on every wake. Project-bound chats must not be
// told to leave their hard-bound repository merely to read Local Agent protocol docs.
assert.match(runtime.bootstrap_prompt, /ChatGPT plans/i);
assert.match(runtime.bootstrap_prompt, /AGENTS\.md/i);
assert.match(runtime.bootstrap_prompt, /cancel that exact task/i);
assert.match(runtime.wake_prompt, /Never launch local Codex/i);
assert.match(runtime.wake_prompt, /cancel an exact task/i);
for (const [name, prompt] of [
  ["bootstrap_prompt", runtime.bootstrap_prompt],
  ["wake_prompt", runtime.wake_prompt]
]) {
  assert.doesNotMatch(prompt, /WAIT_TASK/i, `${name} must not duplicate candidate-owned task-wait policy`);
  assert.doesNotMatch(prompt, /MichalMatu\/local-agent docs/i,
    `${name} must not require cross-repository protocol-document reads`);
}

// The candidate must remain correct even while the production chat-bridge-state branch
// serves stale or legacy pacing text. Capability-specific policy is appended by the
// candidate extension and therefore does not depend on mutating production runtime state.
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
  assert.match(prompt, /use \[LAB:WAIT_TASK=<task-id>\]/i,
    `${name} must append candidate-owned exact task waiting policy`);
  assert.match(prompt, /event-driven wake plus alarm fallback/i);
  assert.match(prompt, /Use NEXT only for time\/external checks/i);
  assert.match(prompt, /task_result_ready event is a wake hint only/i);
  assert.ok(
    prompt.lastIndexOf("WAIT_TASK") > prompt.indexOf(legacyMarker),
    `${name} must place candidate event-wake policy after legacy runtime pacing text`
  );
}

// Recurring prompts are a protocol surface with an explicit size budget. Bootstrap may be
// richer because it is one-time; ordinary and event wakes must stay compact.
const compactRuntime = {
  bootstrapPrompt: runtime.bootstrap_prompt,
  wakePrompt: runtime.wake_prompt,
  agents: normalizedAgents
};
const compactBootstrap = harness.evaluate(
  `buildBootstrapPrompt(${JSON.stringify(compactRuntime)}, ${JSON.stringify(conversation)})`
);
const compactWake = harness.evaluate(
  `buildWakePrompt(${JSON.stringify(compactRuntime)}, ${JSON.stringify({ ...conversation, bootstrapPending: false })})`
);
const compactEventWake = harness.evaluate(
  `buildEventWakePrompt(${JSON.stringify(compactRuntime)}, ${JSON.stringify({ ...conversation, bootstrapPending: false })}, { taskId: "build-17" })`
);
assert.ok(compactBootstrap.length <= 1600, `bootstrap payload too large: ${compactBootstrap.length}`);
assert.ok(compactWake.length <= 1100, `wake payload too large: ${compactWake.length}`);
assert.ok(compactEventWake.length <= 700, `event wake payload too large: ${compactEventWake.length}`);
assert.ok(!compactEventWake.includes(runtime.wake_prompt),
  "terminal event wake must not repeat generic recurring wake context");
assert.match(compactEventWake, /\[LA_EVENT=task_result_ready\]/);
assert.match(compactEventWake, /\[LA_TASK=build-17\]/);
assert.match(compactEventWake, /Read the exact result before deciding the next action/);

const autonomous = fs.readFileSync(path.join(__dirname, "..", "docs", "AUTONOMOUS_CHAT_LOOP.md"), "utf8");
assert.match(autonomous, /\[LAB:WAIT_TASK=<task-id>\]/);
assert.match(autonomous, /event-driven/i);
assert.match(autonomous, /scheduled reconciliation|alarm fallback/i);
assert.match(autonomous, /publish one repository-scoped `cancel_task` request/);
assert.match(autonomous, /event.*wake hint|wake hint.*event/i);
assert.doesNotMatch(autonomous, /After queueing, use one early autonomous re-check no sooner than about two minutes/i);

console.log("Chat Bridge planner pacing contract tests passed.");
