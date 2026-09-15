"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const protocol = require("./control_protocol.js");

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
const manifest = JSON.parse(fs.readFileSync(path.join(root, "manifest.json"), "utf8"));
assert.ok(manifest.permissions.includes("nativeMessaging"), "manifest must request nativeMessaging");

const serviceWorker = fs.readFileSync(path.join(root, "service_worker.js"), "utf8");
const eventIndex = serviceWorker.indexOf('"worker_event_wake.js"');
const nativeIndex = serviceWorker.indexOf('"native_events.js"');
const diagnosticsIndex = serviceWorker.indexOf('"worker_event_diagnostics.js"');
const controlsIndex = serviceWorker.indexOf('"worker_controls.js"');
assert.ok(eventIndex >= 0, "service worker must load event wake state");
assert.ok(nativeIndex > eventIndex, "native transport must load after event wake state");
assert.ok(diagnosticsIndex > nativeIndex, "event diagnostics must load after native transport primitives");
assert.ok(controlsIndex > diagnosticsIndex, "assistant controls must load after event diagnostics");

const nativeSource = fs.readFileSync(path.join(root, "native_events.js"), "utf8");
assert.match(nativeSource, /chrome\.runtime\.connectNative\(NATIVE_HOST_NAME\)/);
assert.match(nativeSource, /Object\.values\(eventState\.watches\)\.some/);
assert.match(nativeSource, /nativeWatchIsActive\(watch, bridgeState\)/);
assert.match(nativeSource, /bridgeState\.settings\.masterEnabled/);
assert.match(nativeSource, /conversation\?\.enabled/);
assert.match(nativeSource, /if \(!nativeTransportWanted \|\| nativePort\) return/);
assert.doesNotMatch(nativeSource, /exec|shell|terminal/i, "native event transport must not expose execution commands");

const eventWake = fs.readFileSync(path.join(root, "worker_event_wake.js"), "utf8");
assert.match(eventWake, /event\.repository === watch\.repository/);
assert.match(eventWake, /delete state\.watches\[watch\.conversationId\]/);

const delivery = fs.readFileSync(path.join(root, "worker_delivery.js"), "utf8");
assert.match(delivery, /pendingEventWake\(chatId\)/);
assert.match(delivery, /buildEventWakePrompt\(runtime, conversation, pending\)/);
assert.match(delivery, /if \(pending && response\?\.ok\)/);
assert.match(delivery, /consumePendingEventWake\(chatId, pending\.eventId\)/);

console.log("Chat Bridge event wake protocol tests passed.");
