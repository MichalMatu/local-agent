"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = __dirname;
const read = (name) => fs.readFileSync(path.join(ROOT, name), "utf8");
const protocolVersion = (name) => {
  const match = read(name).match(/const CONTENT_PROTOCOL_VERSION = (\d+);/);
  assert.ok(match, `${name} must declare CONTENT_PROTOCOL_VERSION`);
  return Number(match[1]);
};

const contentVersion = protocolVersion("content.js");
const workerVersion = protocolVersion("worker_base.js");
const harnessVersion = protocolVersion("worker_test_harness.js");
assert.equal(contentVersion, workerVersion, "content and worker protocol versions must match");
assert.equal(harnessVersion, workerVersion, "worker harness must exercise the production protocol version");

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
  "dynamic reinjection must include content retry policy before content.js"
);
assert.match(
  transport,
  /content_script_unavailable" \|\| content\.reason === "content_script_protocol_mismatch/,
  "stale reachable content protocols must be refreshable"
);

console.log(`Chat Bridge protocol contract tests passed (content protocol v${workerVersion}, extension ${manifest.version}).`);
