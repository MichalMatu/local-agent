"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const protocol = require("./control_protocol.js");

const ROOT = __dirname;
const read = (name) => fs.readFileSync(path.join(ROOT, name), "utf8");

assert.ok(
  Number.isInteger(protocol.CONTENT_PROTOCOL_VERSION) && protocol.CONTENT_PROTOCOL_VERSION > 0,
  "shared CONTENT_PROTOCOL_VERSION must be a positive integer"
);
assert.equal(protocol.CONTENT_PROTOCOL_VERSION, 21, "strict Fabric draft ownership and exact-owned cleanup require content protocol v21");
for (const name of ["content.js", "worker_base.js", "popup.js", "worker_test_harness.js"]) {
  assert.doesNotMatch(
    read(name),
    /const CONTENT_PROTOCOL_VERSION = \d+;/,
    `${name} must consume the shared control_protocol CONTENT_PROTOCOL_VERSION`
  );
}

const workerBase = read("worker_base.js");
const guardSource = read("exhaustion_guard.js");
const harness = read("worker_test_harness.js");
const workerGuardVersion = Number(workerBase.match(/const EXHAUSTION_GUARD_VERSION = (\d+);/)?.[1]);
const contentGuardVersion = Number(guardSource.match(/const GUARD_VERSION = (\d+);/)?.[1]);
const harnessGuardVersion = Number(harness.match(/const EXHAUSTION_GUARD_VERSION = (\d+);/)?.[1]);
assert.equal(workerGuardVersion, contentGuardVersion, "worker and content guard protocol versions must match");
assert.equal(harnessGuardVersion, workerGuardVersion, "test harness guard protocol must match production worker");
assert.equal(workerGuardVersion, 8, "Conversation Fabric must not change the assistant guard DOM contract");
assert.match(
  read("content.js"),
  /const stableId = latest\.getAttribute\("data-message-id"\) \|\| turnKey \|\|/,
  "content assistant identity must preserve v8 data-message-id precedence across reinjection"
);

const manifest = JSON.parse(read("manifest.json"));
assert.equal(manifest.version, "0.8.7", "browser-native Conversation Fabric must have an unambiguous Bridge version");
const scripts = manifest.content_scripts?.[0]?.js || [];
const bridgeProtocolIndex = scripts.indexOf("control_protocol.js");
const fabricProtocolIndex = scripts.indexOf("conversation_fabric_protocol.js");
const retryIndex = scripts.indexOf("content_retry.js");
const resultIndex = scripts.indexOf("spawn_result_content.js");
const fabricContentIndex = scripts.indexOf("conversation_fabric_content.js");
const contentIndex = scripts.indexOf("content.js");
assert.ok(bridgeProtocolIndex >= 0, "manifest must load control_protocol.js");
assert.ok(fabricProtocolIndex > bridgeProtocolIndex, "Conversation Fabric protocol must load after the base protocol");
assert.ok(retryIndex > fabricProtocolIndex, "content retry policy must load after Conversation Fabric protocol");
assert.ok(resultIndex > retryIndex, "child result content must load after retry policy");
assert.ok(fabricContentIndex > resultIndex, "Conversation Fabric parent controller must load after child result content");
assert.ok(contentIndex > fabricContentIndex, "normal Bridge content must remain loaded after isolated Conversation Fabric content");

assert.match(
  workerBase,
  /importScripts\("control_protocol\.js", "bridge_state\.js", "github_control_model\.js"\)/,
  "worker base must load the GitHub control model before worker modules"
);
assert.match(workerBase, /GITHUB_CONTROL_ALARM_NAME/, "worker base must own the GitHub poll alarm identity");

const transport = read("worker_transport.js");
assert.match(
  transport,
  /files: \["control_protocol\.js", "conversation_fabric_protocol\.js", "content_retry\.js", "spawn_result_content\.js", "conversation_fabric_content\.js", "content\.js"\]/,
  "normal Bridge dynamic reinjection must preserve the existing content path"
);
assert.match(
  transport,
  /content_script_unavailable" \|\| content\.reason === "content_script_protocol_mismatch/,
  "stale reachable content protocols must be refreshable"
);

const fabricWorker = read("worker_conversation_fabric.js");
assert.match(transport, /conversation_fabric_content\.js/, "shared transport must refresh Conversation Fabric in already-open tabs");
assert.match(fabricWorker, /chrome\.storage\.local/, "campaign evidence must survive browser restart");
assert.match(fabricWorker, /createConversationSpawnTab/, "Conversation Fabric must reuse the existing Bridge spawn primitive");
assert.doesNotMatch(fabricWorker, /launchPersistentContext|connectOverCDP|nativeMessaging/i, "Conversation Fabric must not create a second browser control plane");

const popup = read("popup.js");
assert.doesNotMatch(popup, /older Bridge content script/i, "popup must not require a manual tab reload for protocol mismatch");
assert.match(popup, /type: "bridge:ensure-tab-content"/, "popup must delegate content activation to the worker");
assert.doesNotMatch(popup, /chrome\.scripting\.executeScript/, "popup must not maintain a second reinjection implementation");

const events = read("worker_events.js");
assert.match(events, /"bridge:ensure-tab-content"/, "worker must expose centralized popup content activation");
assert.match(events, /"bridge:operator-control"/, "worker must expose user-authored operator controls during migration");
assert.match(events, /"bridge:conversation-fabric-control"/, "worker must expose browser-native Conversation Fabric controls");
assert.match(events, /GITHUB_CONTROL_ALARM_NAME/, "worker events must route the durable GitHub-control poll");
assert.match(events, /initializeGithubControlPlane/, "extension lifecycle must establish the GitHub-control poll");
assert.match(events, /reconcileGithubConversationControls/, "worker lifecycle must reconcile GitHub desired state");

const serviceWorker = read("service_worker.js");
const fabricProtocolWorkerIndex = serviceWorker.indexOf('"conversation_fabric_protocol.js"');
const spawnWorkerIndex = serviceWorker.indexOf('"worker_spawn.js"');
const spawnResultIndex = serviceWorker.indexOf('"worker_spawn_result.js"');
const fabricWorkerIndex = serviceWorker.indexOf('"worker_conversation_fabric.js"');
const githubWorkerIndex = serviceWorker.indexOf('"worker_github_control.js"');
const labWorkerIndex = serviceWorker.indexOf('"worker_lab_commands.js"');
const githubGateIndex = serviceWorker.indexOf('"worker_github_legacy_gate.js"');
const eventsIndex = serviceWorker.indexOf('"worker_events.js"');
assert.ok(fabricProtocolWorkerIndex >= 0, "service worker must load the Conversation Fabric protocol");
assert.ok(githubWorkerIndex >= 0, "service worker must load GitHub desired-state reconciliation");
assert.ok(spawnWorkerIndex >= 0, "service worker must load existing spawn primitives");
assert.ok(spawnResultIndex > spawnWorkerIndex, "child result helpers must extend already-defined spawn primitives");
assert.ok(fabricWorkerIndex > spawnResultIndex, "Conversation Fabric campaign worker must load after spawn result helpers");
assert.ok(labWorkerIndex > fabricWorkerIndex, "legacy LAB controls must remain separate from Conversation Fabric controls");
assert.ok(githubGateIndex > labWorkerIndex, "GitHub legacy gate must wrap already-defined LAB handlers");
assert.ok(eventsIndex > githubGateIndex, "worker events must bind all already-defined handlers");

const runtimeExample = JSON.parse(read("runtime.example.json"));
assert.equal(runtimeExample.schema_version, 3, "GitHub control plane must remain backward-compatible with runtime schema 3");
assert.ok(Array.isArray(runtimeExample.conversation_controls), "runtime schema 3 must expose optional conversation_controls");

const githubWorker = read("worker_github_control.js");
assert.match(githubWorker, /bridgeGithubControlApplied/, "GitHub control generations must be durably deduplicated");
assert.doesNotMatch(githubWorker, /bindingRevision === control\.bindingRevision/, "GitHub schedule ownership must not depend on repository binding revision");
assert.match(githubWorker, /Ownership is keyed by chat identity only/, "GitHub schedule ownership must be keyed by chat identity");
assert.match(githubWorker, /localGeneration/, "local generation must participate in GitHub drift detection");
assert.match(githubWorker, /controlGeneration < appliedGeneration/, "stale GitHub control generations must fail closed");
assert.match(githubWorker, /github_control_reconciled/, "GitHub desired state must repair local schedule drift");
assert.match(githubWorker, /githubControlPreservedLocalSafety/, "GitHub reconciliation must preserve terminal local safety state");

const githubGate = read("worker_github_legacy_gate.js");
assert.match(githubGate, /github_control_managed/, "managed LAB schedule controls must terminate without mutating state");
assert.match(githubGate, /validControlFingerprint/, "assistant legacy gate must preserve fingerprint validation");
assert.match(githubGate, /labSenderUrl/, "legacy gate must preserve exact top-frame sender validation");

const labCommands = read("worker_lab_commands.js");
assert.match(
  labCommands,
  /globalThis\.__localAgentChatExhaustionGuard\?\.dispose\?\.\(\)/,
  "force content reload must dispose the actual exhaustion guard instance"
);
assert.doesNotMatch(
  labCommands,
  /__localAgentChatExhaustionGuardState/,
  "force content reload must not use a stale/nonexistent exhaustion guard global"
);

console.log(`Chat Bridge protocol contract tests passed (browser-native Conversation Fabric, content protocol v${protocol.CONTENT_PROTOCOL_VERSION}, extension ${manifest.version}).`);
