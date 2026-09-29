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
assert.equal(protocol.CONTENT_PROTOCOL_VERSION, 14, "sr-only user chrome must not shadow assistant controls");
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
assert.equal(workerGuardVersion, 8, "resume-stream recovery DOM contract upgrade must force replacement of the v7 guard");
assert.match(
  read("content.js"),
  /const stableId = latest\.getAttribute\("data-message-id"\) \|\| turnKey \|\|/,
  "content assistant identity must preserve v8 data-message-id precedence across reinjection"
);

const manifest = JSON.parse(read("manifest.json"));
assert.match(manifest.version, /^\d+\.\d+\.\d+$/);
const scripts = manifest.content_scripts?.[0]?.js || [];
const retryIndex = scripts.indexOf("content_retry.js");
const contentIndex = scripts.indexOf("content.js");
assert.ok(retryIndex >= 0, "manifest must load content_retry.js");
assert.ok(contentIndex >= 0, "manifest must load content.js");
assert.ok(retryIndex < contentIndex, "content retry policy must load before content.js");

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
assert.match(events, /"bridge:operator-control"/, "worker must expose user-authored operator controls");

const serviceWorker = read("service_worker.js");
assert.match(serviceWorker, /"worker_lab_commands\.js"/, "service worker must load LAB command control plane");

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

console.log(`Chat Bridge protocol contract tests passed (shared content protocol v${protocol.CONTENT_PROTOCOL_VERSION}, extension ${manifest.version}).`);
