"use strict";

// Source-only acceptance harness for the default-absent local deny latch.
// Passing tests cannot prove admission by older/offline extension versions.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const folder = __dirname;
const workerGate = fs.readFileSync(path.join(folder, "worker_legacy_dom_effect_gate.js"), "utf8");
const spawn = fs.readFileSync(path.join(folder, "worker_spawn.js"), "utf8");
const loader = fs.readFileSync(path.join(folder, "service_worker.js"), "utf8");
const KEY = "conversationFabricLegacyDomEffectSuspension";

function createGuard(read) {
  const context = vm.createContext({ chrome: { storage: { local: { get: read } } } });
  vm.runInContext(workerGate, context);
  return vm.runInContext("requireLegacyConversationSpawnEffectAllowed", context);
}

async function run() {
  const absent = createGuard(async () => ({}));
  assert.equal(await absent(), true, "existing legacy DOM remains operational by default");

  for (const value of [null, false, true, 0, "", {}, { mode: "legacy_dom" }]) {
    const suspend = createGuard(async key => {
      assert.equal(key, KEY);
      return { [KEY]: value };
    });
    await assert.rejects(suspend(), /browser effects suspended/,
      "any present migration latch must deny even when payload is false");
  }
  for (const malformed of [null, false, [], "not-object"]) {
    await assert.rejects(
      createGuard(async () => malformed)(),
      /snapshot malformed/,
      "malformed storage cannot authorize browser effects"
    );
  }
  await assert.rejects(createGuard(async () => {
    throw new Error("browser storage inaccessible");
  })(), /storage read failed/);

  assert.ok(loader.indexOf('"worker_legacy_dom_effect_gate.js"') >= 0);
  assert.ok(loader.indexOf('"worker_legacy_dom_effect_gate.js"') <
    loader.indexOf('"worker_spawn.js"'), "gate must load before legacy effects");

  // The two tab creations, two content-script probes and two messages must
  // each have a fresh local deny read directly in front of the side effect.
  for (const [effect, count] of [
    ["const tab = await chrome.tabs.create({", 2],
    ["const ready = await ensureConversationSpawnContent(tab.id);", 2],
    ["const response = await chrome.tabs.sendMessage(tab.id, {", 2]
  ]) {
    const sites = spawn.split(effect);
    assert.equal(sites.length - 1, count, "unexpected new unreviewed effect site: " + effect);
    for (const prefix of sites.slice(0, -1)) {
      const segment = prefix.slice(-260);
      assert.ok(segment.includes("await requireLegacyConversationSpawnEffectAllowed();"),
        "spawn effect has no immediate guard: " + effect);
    }
  }
  assert.doesNotMatch(workerGate, /chrome\.tabs\.|chrome\.scripting\./);
  assert.doesNotMatch(workerGate, /fetch\s*\(|readToken|Authorization|github_first_send/i);
  console.log("Default-absent legacy DOM suspension seam: bounded deny tests PASS.");
}

run().catch(error => { console.error(error); process.exitCode = 1; });
