"use strict";

// Offline installed-MV3 read-only intake proof; no real ChatGPT, no tab spawning.
const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(__dirname, "..");
const extension = path.join(root, "chat_bridge");
const runtimeUrl = "https://raw.githubusercontent.com/MichalMatu/local-agent/chat-bridge-state/chat_bridge/runtime.json";
const recordRoot = "https://raw.githubusercontent.com/MichalMatu/local-agent/chat-bridge-state/.agent/conversation/browser_dispatches/";

function syntheticDispatch() {
  const python = [
    "import json",
    "from tests.test_github_fabric_dispatch import operator_request, admitted_children",
    "from local_agent.conversation.github_fabric_dispatch import build_github_fabric_dispatch",
    "print(json.dumps(build_github_fabric_dispatch(operator_request(), admitted_children())))"
  ].join("\n");
  const result = spawnSync(process.env.PYTHON || "python", ["-c", python], {
    cwd: root, encoding: "utf8", timeout: 30000, maxBuffer: 200 * 1024
  });
  assert.equal(result.status, 0, result.stderr || "synthetic dispatch generation failed");
  const value = JSON.parse(result.stdout.trim());
  assert.equal(value.children.length, 2);
  return value;
}

async function start(profile) {
  const context = await chromium.launchPersistentContext(profile, {
    channel: "chromium", headless: true,
    ignoreDefaultArgs: ["--disable-extensions"],
    args: ["--disable-background-networking",
      "--disable-extensions-except=" + extension, "--load-extension=" + extension]
  });
  await context.setOffline(true);
  const worker = context.serviceWorkers()[0] || await context.waitForEvent("serviceworker");
  return { context, worker };
}

async function configure(worker, dispatch) {
  return worker.evaluate(async ({ dispatch, runtimeUrl, recordRoot }) => {
    const parent = await upsertConversation({
      url: dispatch.parent_conversation_url, enabled: true
    });
    await mutateState(state => {
      state.settings.masterEnabled = true;
      state.settings.runtimeUrl = runtimeUrl;
      return state;
    });
    globalThis.__githubFabricTest = {
      dispatch, recordRoot, enabled: false, controlEnabled: true,
      index: { schema_version: 1, dispatch_ids: [dispatch.id] }, requests: 0
    };
    globalThis.fetchRuntime = async () => ({
      source: "remote",
      githubFabricReadOnlyIntakeEnabled: globalThis.__githubFabricTest.enabled,
      conversationControls: [{
        conversationId: parent.id, enabled: globalThis.__githubFabricTest.controlEnabled,
        controlGeneration: 1
      }]
    });
    globalThis.fetch = async url => {
      const f = globalThis.__githubFabricTest;
      const target = String(url).split("?")[0];
      ++f.requests;
      const payload = target === f.recordRoot + "index.json" ? f.index
        : target === f.recordRoot + f.dispatch.id + ".json" ? f.dispatch
        : null;
      if (payload === null) throw new Error("unexpected read-only fixture URL");
      return new Response(typeof payload === "string" ? payload : JSON.stringify(payload), {
        headers: { "Content-Type": "application/json" }
      });
    };
    return parent.id;
  }, { dispatch, runtimeUrl, recordRoot });
}

const poll = worker => worker.evaluate(async () => pollGithubFabricReadOnlyIntake());
const change = (worker, fields) => worker.evaluate(value => {
  Object.assign(globalThis.__githubFabricTest, value);
}, fields);
const snapshot = worker => worker.evaluate(async () => ({
  seen: (await chrome.storage.local.get("bridgeGithubFabricReadOnlySeen"))
    .bridgeGithubFabricReadOnlySeen || {},
  campaigns: Object.keys(await chrome.storage.local.get(null))
    .filter(key => key.startsWith("conversation-fabric-campaign:")),
  tabs: (await chrome.tabs.query({})).length,
  requests: globalThis.__githubFabricTest.requests
}));

(async () => {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), "fabric-readonly-mv3-"));
  const dispatch = syntheticDispatch();
  let active = null;
  try {
    active = await start(profile);
    assert.ok(await configure(active.worker, dispatch));
    const baseline = await snapshot(active.worker);
    assert.equal((await poll(active.worker)).status, "disabled");
    assert.equal((await snapshot(active.worker)).requests, 0);
    await change(active.worker, { enabled: true });
    const first = await poll(active.worker);
    assert.equal(first.status, "read_only");
    assert.equal(first.stored, 1);
    assert.equal(first.replayed, 0);
    assert.equal((await poll(active.worker)).replayed, 1);
    const original = await snapshot(active.worker);
    assert.equal(Object.keys(original.seen).length, 1);
    assert.ok(Object.hasOwn(original.seen, dispatch.id));
    assert.deepEqual(original.campaigns, []);
    assert.equal(original.tabs, baseline.tabs);
    await active.worker.evaluate(() => chrome.storage.session.clear());
    await active.context.close();

    // Cold Chrome + MV3 restart must preserve the real storage.local ledger.
    active = await start(profile);
    await configure(active.worker, dispatch);
    await change(active.worker, { enabled: true });
    const restored = await poll(active.worker);
    assert.equal(restored.replayed, 1);
    assert.equal(restored.stored, 0);
    assert.deepEqual((await snapshot(active.worker)).seen, original.seen);

    const conflict = structuredClone(dispatch);
    conflict.children[0].spawn.bootstrap_text += "\nsynthetic changed text";
    conflict.children[0].spawn.bootstrap_digest = "sha256:" + crypto
      .createHash("sha256").update(conflict.children[0].spawn.bootstrap_text).digest("hex");
    await change(active.worker, { dispatch: conflict });
    assert.equal((await poll(active.worker)).conflicts, 1);
    assert.deepEqual((await snapshot(active.worker)).seen, original.seen);

    await change(active.worker, { index: '{"schema_version":1,' });
    await assert.rejects(poll(active.worker));
    await change(active.worker, { index: "x".repeat(9000) });
    await assert.rejects(poll(active.worker), /exceeds bound/);
    assert.deepEqual((await snapshot(active.worker)).seen, original.seen);

    await change(active.worker, {
      index: { schema_version: 1, dispatch_ids: [dispatch.id] },
      dispatch, controlEnabled: false
    });
    assert.equal((await poll(active.worker)).skipped, 1);
    await change(active.worker, { controlEnabled: true, enabled: false });
    assert.equal((await poll(active.worker)).status, "disabled");
    const final = await snapshot(active.worker);
    assert.deepEqual(final.campaigns, []);
    assert.equal(final.tabs, baseline.tabs);
    console.log("Installed MV3 GitHub Fabric read-only restart smoke passed.");
  } finally {
    if (active) await active.context.close().catch(() => undefined);
    await fs.rm(profile, { recursive: true, force: true });
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
