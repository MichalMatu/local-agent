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
const privateReceipts = "github_fabric_private_receipts.js";
const trialWorker = "worker_github_fabric_private_live.js";

assert.ok(imports.includes("worker_github_fabric_intake.js"),
  "legacy GitHub-first public read-only observer must remain test-visible");
assert.ok(imports.includes("worker_conversation_fabric.js"),
  "old DOM implementation still owns live effects until fenced migration");
assert.ok(!imports.includes(privateReader),
  "unattested global parent fence preview remains disabled");
for (const name of [privateDispatch, privateReceipts, trialWorker]) {
  assert.ok(imports.includes(name), "private MVP module must load in worker only");
}
for (const sensitive of [privateReader, privateDispatch, privateReceipts, trialWorker]) {
  assert.ok(!contentScripts.includes(sensitive),
    "no private GitHub or owner-fence authority may run in ChatGPT page");
}
assert.ok(manifest.host_permissions.includes("https://api.github.com/*"),
  "private repository access requires explicit extension host grant");
assert.ok(!Object.prototype.hasOwnProperty.call(runtimeExample,
  "githubFabricPrivateChildSendEnabled"),
  "public runtime never activates private browser Send");
const privateWorker = read(trialWorker);
const events = read("worker_events.js");
assert.ok(events.includes('message.type === "bridge:private-github-first-start"'),
  "private trial must require an operator popup action");
assert.ok(events.includes('operator_ui_required'),
  "private trial commands must not accept page-origin messages");
assert.ok(privateWorker.includes('record.phase = "submission_unknown"'),
  "unknown Submit must be durably fenced before any UI action");
assert.ok(privateWorker.includes('reconcileConversationSpawn(record.intent)'),
  "unknown Send recovery must use reconcile, never blind re-send");
assert.ok(privateWorker.includes('!["retired", "abandoned"].includes(trial.phase)'),
  "old DOM delegate must be fenced for active GitHub-first parent");
assert.ok(!contentScripts.some(name => name.startsWith("github_fabric_private_")),
  "private tokens must never enter ChatGPT content scripts");

const popupHtml = read("popup.html");
const popupJs = read("popup.js");
for (const elementId of [
  "privateFabricSaveDispatch", "privateFabricSaveToken", "privateFabricForgetToken",
  "privateFabricDispatchState", "privateFabricTokenState"
]) {
  assert.ok(popupHtml.includes('id="' + elementId + '"'),
    "private trial popup must expose independently saved input: " + elementId);
  assert.ok(popupJs.includes('querySelector("#' + elementId + '")'),
    "private trial popup must wire saved input: " + elementId);
}
for (const type of [
  "draft-status", "save-dispatch", "save-token", "forget-token"
]) {
  assert.ok(events.includes('"bridge:private-github-first-' + type + '"'),
    "private saved input operations must use the popup-only worker gate");
}
assert.ok(privateWorker.includes("chrome.storage.session.set({ [PRIVATE_FABRIC_TOKEN_KEY]"),
  "private token must live in Chrome session storage");
assert.ok(privateWorker.includes("token.slice(-4)"),
  "operator may see only a bounded trailing credential hint");
assert.ok(popupJs.includes('savedUi[PRIVATE_POPUP_UI_KEY]?.advancedOpen'),
  "advanced settings must survive popup closure");
assert.ok(!popupJs.includes("localStorage.setItem"),
  "page-side localStorage must never store private credentials");

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

console.log("Private GitHub Fabric operator-gated effect safety contract passed.");
