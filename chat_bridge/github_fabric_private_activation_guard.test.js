"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = __dirname;
const read = file => fs.readFileSync(path.join(root, file), "utf8");
const workerSource = read("service_worker.js");
const manifest = JSON.parse(read("manifest.json"));
const runtimeExample = JSON.parse(read("runtime.example.json"));
const intake = read("worker_github_fabric_intake.js");

const imports = [...workerSource.matchAll(/"([a-z0-9_.-]+\.js)"/g)]
  .map(match => match[1]);
const contentScripts = manifest.content_scripts.flatMap(script => script.js || []);
const privateReader = "github_fabric_private_parent_fence_reader.js";
const privateDispatch = "github_fabric_private_transport.js";

assert.ok(imports.includes("worker_github_fabric_intake.js"),
  "legacy GitHub-first public read-only observer must remain test-visible");
assert.ok(imports.includes("worker_conversation_fabric.js"),
  "old DOM implementation still owns live effects until fenced migration");
for (const sensitive of [privateReader, privateDispatch]) {
  assert.ok(!imports.includes(sensitive),
    "private GitHub reader must not be loaded into production service worker");
  assert.ok(!contentScripts.includes(sensitive),
    "private token-reading code must not be loaded into ChatGPT page");
}
assert.ok(!imports.some(name => name.startsWith("github_fabric_private_")),
  "private reader/writer modules require separately reviewed secure provisioning");
assert.ok(!contentScripts.some(name => name.startsWith("github_fabric_private_")),
  "ChatGPT content scripts must never receive private GitHub authorization");

// The present public index poller may validate & observe, never invoke a
// browser side effect. New dispatch effects require an explicit migration gate.
for (const forbidden of [
  /\bchrome\.tabs\./,
  /\bchrome\.scripting\./,
  /\bcreateConversationSpawnTab\s*\(/,
  /\bsubmitConversationSpawn\s*\(/,
  /\bcreateConversationFabricCampaign\s*\(/,
  /\bdeliverConversationSpawn\s*\(/
]) {
  assert.ok(!forbidden.test(intake),
    "public GitHub-first intake must remain observation-only");
}
assert.ok(intake.includes("runtime.githubFabricReadOnlyIntakeEnabled !== true"),
  "the existing public intake must preserve its opt-in default-disabled guard");
assert.ok(!Object.prototype.hasOwnProperty.call(runtimeExample,
  "githubFabricPrivateParentFenceEnabled"),
  "example runtime must not opt into an unverified global parent fence");
assert.ok(!Object.prototype.hasOwnProperty.call(runtimeExample,
  "githubFabricPrivateChildSendEnabled"),
  "example runtime must not claim private browser Send authority");

console.log("Private GitHub Fabric production import/effect safety contract passed.");
