"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const protocol = require("./control_protocol.js");
const { createHarness } = require("./worker_test_harness.js");

assert.deepEqual(protocol.parseAssistantControl("Queued. [LAB:WAIT_TASK=build-17]"), {
  action: "wait_task",
  taskId: "build-17",
  marker: "[LAB:WAIT_TASK=build-17]"
});
assert.deepEqual(protocol.parseAssistantControl("[LOCAL_AGENT_BRIDGE:WAIT_TASK=test.a:b_2]"), {
  action: "wait_task",
  taskId: "test.a:b_2",
  marker: "[LOCAL_AGENT_BRIDGE:WAIT_TASK=test.a:b_2]"
});
assert.equal(protocol.parseAssistantControl("[LAB:WAIT_TASK=]"), null);
assert.equal(protocol.parseAssistantControl("[LAB:WAIT_TASK=../escape]"), null);
assert.equal(protocol.parseAssistantControl(`[LAB:WAIT_TASK=${"a".repeat(161)}]`), null);
assert.ok(
  protocol.COMMAND_CATALOG.some((entry) => entry.marker === "WAIT_TASK=<task-id>"),
  "WAIT_TASK must be advertised in the command catalog"
);

const root = __dirname;
const read = (name) => fs.readFileSync(path.join(root, name), "utf8");
const manifest = JSON.parse(read("manifest.json"));
assert.ok(manifest.permissions.includes("nativeMessaging"), "manifest must request nativeMessaging");

const serviceWorker = read("service_worker.js");
const bindingIndex = serviceWorker.indexOf('"worker_binding.js"');
const stateModelIndex = serviceWorker.indexOf('"event_wake_state.js"');
const eventIndex = serviceWorker.indexOf('"worker_event_wake.js"');
const scheduleIndex = serviceWorker.indexOf('"worker_schedule.js"');
const nativeIndex = serviceWorker.indexOf('"native_events.js"');
const diagnosticsIndex = serviceWorker.indexOf('"worker_event_diagnostics.js"');
const controlsIndex = serviceWorker.indexOf('"worker_controls.js"');
assert.ok(stateModelIndex > bindingIndex, "pure event state model must load after shared binding dependencies");
assert.ok(eventIndex > stateModelIndex, "persisted event routing must load after its pure state model");
assert.ok(scheduleIndex > eventIndex, "scheduler must consume event routing without a reverse dependency");
assert.ok(nativeIndex > scheduleIndex, "native transport orchestration must load after routing and scheduling");
assert.ok(diagnosticsIndex > nativeIndex, "event diagnostics must load after native transport primitives");
assert.ok(controlsIndex > diagnosticsIndex, "assistant controls must load after event diagnostics");

const eventWake = read("worker_event_wake.js");
assert.match(eventWake, /LocalAgentEventWakeState/);
assert.match(eventWake, /persistNativeTaskEvent/);
assert.doesNotMatch(eventWake, /reconcileNativeEventTransport/,
  "persisted event routing must not call the native transport layer");
assert.doesNotMatch(eventWake, /scheduleAt\(/,
  "persisted event routing must not own alarm scheduling");
assert.doesNotMatch(eventWake, /buildEventWakePrompt/,
  "persisted event routing must not own planner prompt construction");

const stateSource = read("event_wake_state.js");
assert.doesNotMatch(stateSource, /chrome\./,
  "event wake state validation must remain a pure Chrome-independent model");
assert.match(stateSource, /sanitizeDiagnostics/);
assert.match(stateSource, /MAX_FUTURE_SKEW_MS/);

const nativeSource = read("native_events.js");
assert.match(nativeSource, /chrome\.runtime\.connectNative\(NATIVE_HOST_NAME\)/);
assert.match(nativeSource, /NATIVE_HANDSHAKE_TIMEOUT_MS/);
assert.match(nativeSource, /persistNativeTaskEvent/);
assert.match(nativeSource, /scheduleAt\(/);
assert.match(nativeSource, /eventWakeModel\.watchMatchesConversation/);
assert.doesNotMatch(nativeSource, /exec|shell|terminal/i,
  "native event transport must not expose execution commands");

const bindingSource = read("worker_binding.js");
assert.match(bindingSource, /protocol\.COMMAND_CATALOG/,
  "bootstrap control guidance must derive from the formal protocol catalog");
assert.match(bindingSource, /buildEventWakePrompt/,
  "binding/prompt policy module must own event wake prompt construction");

const harness = createHarness();
const scheduleSummary = harness.evaluate("assistantScheduleControlSummary()");
for (const command of protocol.COMMAND_CATALOG.filter(
  (entry) => entry.privilege === "assistant" && entry.category === "schedule"
)) {
  assert.match(scheduleSummary, new RegExp(`\\[LAB:${command.marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\]`),
    `bootstrap schedule guidance must advertise ${command.marker} from the protocol catalog`);
}

const delivery = read("worker_delivery.js");
assert.match(delivery, /pendingEventWake\(chatId\)/);
assert.match(delivery, /buildEventWakePrompt\(runtime, conversation, pending\)/);
assert.match(delivery, /if \(pending && response\?\.ok\)/);
assert.match(delivery, /consumePendingEventWake\(chatId, pending\.eventId\)/);
assert.match(delivery, /reconcileNativeEventTransport\(\)/,
  "delivery orchestration must explicitly reconcile the native transport after consumption");

console.log("Chat Bridge event wake protocol and module-boundary tests passed.");
