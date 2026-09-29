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
assert.equal(protocol.CONTENT_PROTOCOL_VERSION, 13, "GitHub control-plane upgrade must not change the DOM content protocol");
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
assert.equal(workerGuardVersion, 8, "GitHub schedule control must not change the assistant guard DOM contract");
assert.match(
  read("content.js"),
  /const stableId = latest\.getAttribute\("data-message-id"\) \|\| turnKey \|\|/,
  "content assistant identity must preserve v8 data-message-id precedence across reinjection"
);

const manifest = JSON.parse(read("manifest.json"));
assert.equal(manifest.version, "0.6.0", "GitHub-backed schedule control must have an unambiguous Bridge version");
const scripts = manifest.content_scripts?.[0]?.js || [];
const retryIndex = scripts.indexOf("content_retry.js");
const contentIndex = scripts.indexOf("content.js");
assert.ok(retryIndex >= 0, "manifest must load content_retry.js");
assert.ok(contentIndex >= 0, "manifest must load content.js");
assert.ok(retryIndex < contentIndex, "content retry policy must load before content.js");

assert.match(
  workerBase,
  /importScripts\("control_protocol\.js", "bridge_state\.js", "github_control_model\.js"\)/,
  "worker base must load the GitHub control model before worker modules"
);
assert.match(workerBase, /GITHUB_CONTROL_ALARM_NAME/, "worker base must own the GitHub poll alarm identity");

const transport = read("worker_transport.js");
assert.match(
  transport,
  /files: \["control_protocol\.js", "content_retry\.js", "content\.js"\]/,
  "dynamic worker reinjection must include content retry policy before content.js"
);
assert.match(
  transport,
  /content_script_unavailable" \|\| content\.reason === "content_script_protocol_mismatch/,
  "stale reachable content protocols must be refreshable"
);

const popup = read("popup.js");
assert.doesNotMatch(popup, /older Bridge content script/i, "popup must not require a manual tab reload for protocol mismatch");
assert.match(popup, /type: "bridge:ensure-tab-content"/, "popup must delegate content activation to the worker");
assert.doesNotMatch(popup, /chrome\.scripting\.executeScript/, "popup must not maintain a second reinjection implementation");

const events = read("worker_events.js");
assert.match(events, /"bridge:ensure-tab-content"/, "worker must expose centralized popup content activation");
assert.match(events, /"bridge:operator-control"/, "worker must expose user-authored operator controls during migration");
assert.match(events, /GITHUB_CONTROL_ALARM_NAME/, "worker events must route the durable GitHub-control poll");
assert.match(events, /initializeGithubControlPlane/, "extension lifecycle must establish the GitHub-control poll");
assert.match(events, /reconcileGithubConversationControls/, "worker lifecycle must reconcile GitHub desired state");

const serviceWorker = read("service_worker.js");
assert.match(serviceWorker, /"worker_github_control\.js"/, "service worker must load GitHub desired-state reconciliation");
assert.match(serviceWorker, /"worker_lab_commands\.js"/, "legacy LAB control plane remains loaded only for migration compatibility");

const runtimeExample = JSON.parse(read("runtime.example.json"));
assert.equal(runtimeExample.schema_version, 3, "GitHub control plane must remain backward-compatible with runtime schema 3");
assert.ok(Array.isArray(runtimeExample.conversation_controls), "runtime schema 3 must expose optional conversation_controls");

const githubWorker = read("worker_github_control.js");
assert.match(githubWorker, /bridgeGithubControlApplied/, "GitHub control generations must be durably deduplicated");
assert.match(githubWorker, /controlGeneration < appliedGeneration/, "stale GitHub control generations must fail closed");
assert.match(githubWorker, /github_control_reconciled/, "GitHub desired state must repair local schedule drift");

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

console.log(`Chat Bridge protocol contract tests passed (GitHub control plane, content protocol v${protocol.CONTENT_PROTOCOL_VERSION}, extension ${manifest.version}).`);
