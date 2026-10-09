"use strict";

// Frozen source-site inventory for the CURRENT legacy DOM transport. These are
// NOT permits and do not block preinstalled/offline extension copies. A changed
// count is a demand for human review, not proof that a count-preserving change
// is safe. This is deliberately separate from the production extension.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = __dirname;
const effectSites = Object.freeze({
  "worker_spawn.js": {
    "chrome.tabs.create(": 2,
    "chrome.tabs.update(": 1,
    "chrome.tabs.sendMessage(": 3,
    "chrome.scripting.executeScript(": 1
  },
  "worker_spawn_result.js": {
    "chrome.tabs.sendMessage(": 1,
    "chrome.scripting.executeScript(": 1,
    "chrome.tabs.remove(": 1
  },
  "worker_spawn_route_transition.js": {
    "chrome.scripting.executeScript(": 2,
    "expanders[0].click()": 1
  },
  "worker_delivery.js": {
    "chrome.tabs.sendMessage(": 1,
    "chrome.scripting.executeScript(": 1
  },
  "spawn_content.js": {
    "button.click()": 2
  },
  "content.js": {
    "sendButton.click()": 1,
    "form.requestSubmit()": 1
  }
});
const browserPrimitives = [
  "chrome.tabs.create(", "chrome.tabs.update(", "chrome.tabs.sendMessage(",
  "chrome.tabs.remove(", "chrome.scripting.executeScript("
];

function matches(source, literal) {
  return source.split(literal).length - 1;
}

function run() {
  let effects = 0;
  for (const [file, expected] of Object.entries(effectSites)) {
    const source = fs.readFileSync(path.join(ROOT, file), "utf8");
    for (const primitive of browserPrimitives) {
      const count = matches(source, primitive);
      assert.equal(count, expected[primitive] || 0,
        file + ": unreviewed browser effect API count: " + primitive);
      effects += count;
    }
    for (const [literal, count] of Object.entries(expected)) {
      assert.equal(matches(source, literal), count,
        file + ": unreviewed DOM/button effect site: " + literal);
    }
  }
  assert.equal(effects, 14, "Unexpected native browser effect count");

  const content = fs.readFileSync(path.join(ROOT, "spawn_content.js"), "utf8");
  assert.match(content, /phases\.armAndSend\(sessionStorage, intent/,
    "durable pre-Send arm must remain on V2 page-local submission");
  assert.match(content, /spawn_submission_ambiguous/,
    "legacy submission ambiguity must retain its no-auto-replay path");
  const delivery = fs.readFileSync(path.join(ROOT, "worker_conversation_fabric_delivery_guard.js"), "utf8");
  assert.match(delivery, /feedback_delivery_assumed\s*=\s*true/);
  assert.match(delivery, /delivery_claim_recovered_after_restart/);
  assert.match(delivery, /conversationFabricAssumeClaimDelivered/);
  const spawn = fs.readFileSync(path.join(ROOT, "worker_spawn.js"), "utf8");
  assert.match(spawn, /async function submitConversationSpawnBootstrap/);
  const worker = fs.readFileSync(path.join(ROOT, "service_worker.js"), "utf8");
  const manifest = fs.readFileSync(path.join(ROOT, "manifest.json"), "utf8");
  assert.doesNotMatch(worker + manifest, /github_fabric_global_admission_audit/);
  console.log("Legacy DOM effect-site inventory (bounded review sentinel): PASS");
}

run();
