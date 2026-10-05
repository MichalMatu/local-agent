"use strict";

// Offline real-extension proof: parent control -> three same-browser children ->
// partial durable capture -> real MV3 service-worker restart -> recovery -> terminal feedback ->
// second restart -> no replay.
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(__dirname, "..");
const catalog = require(path.join(root, "chat_bridge/runtime.example.json"));
const parentUrl = "https://chatgpt.com/c/fabric-parent-proof";
const fixture = `<!doctype html><html><head><style>#prompt-textarea { white-space: pre-wrap; }</style></head><body>
<div id="turns"></div>
<form><div id="prompt-textarea" class="ProseMirror" contenteditable="true" role="textbox"></div>
<button id="composer-submit-button" type="submit">Send</button></form>
<script>
window.submitted = [];
window.__childId = null;
window.__completionMarker = null;
window.__childCompleted = false;
function turn(role, text) {
  const row = document.createElement("div");
  row.dataset.turnKey = role + "-" + document.querySelectorAll("[data-turn-key]").length;
  const message = document.createElement("div");
  if (role === "assistant") {
    const unit = document.createElement("div");
    unit.dataset.contentSearchUnitKey = row.dataset.turnKey + ":assistant";
    const heading = document.createElement("h4");
    heading.dataset.conversationRole = role;
    heading.textContent = "ChatGPT said:";
    unit.appendChild(heading);
    message.dataset.chatgptSelectionMessageId = row.dataset.turnKey;
    unit.appendChild(message);
    row.appendChild(unit);
    const rating = document.createElement("div");
    rating.textContent = "Is this conversation helpful so far?";
    row.appendChild(rating);
  } else {
    message.dataset.messageAuthorRole = role;
    row.appendChild(message);
  }
  message.textContent = text;
  document.querySelector("#turns").appendChild(row);
}
window.completeChild = () => {
  if (!window.__childId || !window.__completionMarker || window.__childCompleted) return;
  window.__childCompleted = true;
  turn("assistant", "RESULT_" + window.__childId.toUpperCase() + "\\n" + window.__completionMarker);
};
document.querySelector("form").onsubmit = (event) => {
  event.preventDefault();
  const composer = document.querySelector("#prompt-textarea");
  const text = composer.innerText || composer.textContent;
  window.submitted.push(text);
  turn("user", text);
  composer.textContent = "";
  composer.dispatchEvent(new Event("input", {bubbles: true}));
  if (text === "INITIAL_PARENT") {
    history.pushState({}, "", "/c/fabric-parent-proof");
    turn("assistant", "READY");
    return;
  }
  const child = text.match(/^child_id=(.+)$/m);
  if (child) {
    window.__childId = child[1];
    history.pushState({}, "", "/c/fabric-child-" + child[1]);
    const completion = text.match(/<<<LOCAL_AGENT_CF_CHILD_COMPLETE:[0-9a-f]{8}:[A-Za-z0-9._-]{1,64}:[0-9a-f]{8}>>>/);
    if (!completion) throw new Error("child bootstrap missing completion marker");
    window.__completionMarker = completion[0];
    if (child[1] === "fast") window.completeChild();
    if (child[1] === "slow") turn("assistant", "WORKING_SLOW");
    return;
  }
  if (
    text.includes("completed.") &&
    text.includes("RESULT_FAST") &&
    text.includes("RESULT_SLOW") &&
    text.includes("RESULT_TRANSIENT")
  ) {
    turn("assistant", "PARENT_SYNTHESIS: RESULT_FAST + RESULT_SLOW + RESULT_TRANSIENT");
  }
};
</script></body></html>`;

async function waitFor(label, predicate, timeout = 30000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) {
    const value = await predicate();
    if (value) return value;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`${label} timed out`);
}

async function installRuntimeFetch(worker) {
  await worker.evaluate(runtime => {
    globalThis.fetch = async () => ({ ok: true, json: async () => runtime });
  }, catalog);
}

async function triggerProductionFabricPoll(worker) {
  return worker.evaluate(async () => {
    const originalPoll = pollConversationFabricCampaigns;
    let restored = false;
    let resolveCompleted;
    let rejectCompleted;
    const completed = new Promise((resolve, reject) => {
      resolveCompleted = resolve;
      rejectCompleted = reject;
    });
    const restore = () => {
      if (restored) return;
      restored = true;
      pollConversationFabricCampaigns = originalPoll;
    };
    const timeout = setTimeout(() => {
      restore();
      rejectCompleted(new Error("production Conversation Fabric poll alarm did not complete"));
    }, 10000);

    pollConversationFabricCampaigns = async function observedProductionFabricPoll(...args) {
      try {
        const result = await originalPoll(...args);
        resolveCompleted({ ok: true, completedAt: Date.now() });
        return result;
      } catch (error) {
        rejectCompleted(error);
        throw error;
      } finally {
        restore();
      }
    };

    try {
      await chrome.alarms.create(GITHUB_CONTROL_ALARM_NAME, { when: Date.now() + 50 });
      return await completed;
    } finally {
      clearTimeout(timeout);
      restore();
    }
  });
}

async function restartServiceWorker(context, worker, { clearSession = true } = {}) {
  const extensionId = new URL(worker.url()).hostname;
  const page = context.pages().find(candidate => candidate.url().startsWith("https://chatgpt.com/"));
  if (!page) throw new Error("ChatGPT page unavailable for MV3 restart proof");

  await worker.evaluate(async shouldClear => {
    if (shouldClear) await chrome.storage.session.clear();
  }, clearSession);

  // Capture both the extension content-script world and Chromium's actual service-worker
  // lifecycle. CDP is harness-only observation/interruption; recovery itself remains the
  // installed extension's normal message/alarm/durable-state path.
  const cdp = await context.newCDPSession(page);
  const executionContexts = new Set();
  const workerVersions = new Map();
  cdp.on("Runtime.executionContextCreated", event => {
    if (Number.isInteger(event?.context?.id)) executionContexts.add(event.context.id);
  });
  cdp.on("ServiceWorker.workerVersionUpdated", event => {
    for (const version of event?.versions || []) {
      if (version?.versionId) workerVersions.set(version.versionId, version);
    }
  });

  try {
    await cdp.send("Runtime.enable");
    await cdp.send("ServiceWorker.enable");

    const contentContextId = await waitFor("extension isolated content world", async () => {
      for (const contextId of executionContexts) {
        try {
          const probe = await cdp.send("Runtime.evaluate", {
            expression: "globalThis.chrome?.runtime?.id || ''",
            contextId,
            returnByValue: true
          });
          if (probe?.result?.value === extensionId) return contextId;
        } catch (_error) {}
      }
      return null;
    }, 5000);

    const runningVersion = await waitFor("running extension service worker", () => {
      return Array.from(workerVersions.values()).find(version =>
        String(version.scriptURL || "").startsWith(`chrome-extension://${extensionId}/`) &&
        version.runningStatus === "running"
      ) || null;
    }, 5000);

    await cdp.send("ServiceWorker.stopAllWorkers");
    await waitFor("stopped extension service worker", () => {
      return workerVersions.get(runningVersion.versionId)?.runningStatus === "stopped";
    }, 5000);

    // Wake the stopped worker through the extension's already-injected isolated content
    // world using a real, side-effect-free production message handler.
    const wake = await cdp.send("Runtime.evaluate", {
      expression: `chrome.runtime.sendMessage({type:"bridge:control-context",conversationUrl:${JSON.stringify(parentUrl)}})`,
      contextId: contentContextId,
      awaitPromise: true,
      returnByValue: true
    });
    assert.equal(wake?.result?.value?.ok, true, "content-script runtime message must wake the stopped worker");

    await waitFor("running extension service worker after wake", () => {
      return Array.from(workerVersions.values()).find(version =>
        String(version.scriptURL || "").startsWith(`chrome-extension://${extensionId}/`) &&
        version.runningStatus === "running"
      ) || null;
    }, 10000);

    // Playwright may reuse the same Worker handle after the real MV3 restart. Reacquire
    // whichever handle is currently evaluable instead of requiring a new event/object.
    const nextWorker = await waitFor("evaluable restarted service worker", async () => {
      const candidates = Array.from(new Set([worker, ...context.serviceWorkers()]));
      for (const candidate of candidates) {
        try {
          if (await candidate.evaluate(id => chrome.runtime.id === id, extensionId)) return candidate;
        } catch (_error) {}
      }
      return null;
    }, 10000);

    await installRuntimeFetch(nextWorker);
    return nextWorker;
  } finally {
    await cdp.detach();
  }
}

async function contentControllerPresent(worker, expectedUrl) {
  return worker.evaluate(async url => {
    const normalized = normalizeConversationUrl(url);
    const tabs = await chrome.tabs.query({});
    const tab = tabs.find(candidate =>
      Number.isInteger(candidate.id) &&
      normalizeConversationUrl(candidate.url || "") === normalized
    );
    if (!tab?.id) return false;
    try {
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: [0] },
        world: "ISOLATED",
        func: () => Boolean(globalThis.__localAgentConversationFabricContent)
      });
      return Boolean(results?.[0]?.result);
    } catch (_error) {
      return false;
    }
  }, expectedUrl);
}

function fabricChildren(context) {
  return context.pages().filter(page => page.url().includes("/c/fabric-child-"));
}

async function pageForChild(context, childId) {
  return waitFor(`child page ${childId}`, async () => {
    for (const page of fabricChildren(context)) {
      if (await page.evaluate(() => window.__childId) === childId) return page;
    }
    return null;
  });
}

async function campaignSnapshot(worker, campaignId) {
  return worker.evaluate(id => loadConversationFabricCampaign(id), campaignId);
}

(async () => {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), "fabric-browser-proof-"));
  let context;
  let worker;
  let parent;
  let campaignId = null;
  try {
    const extension = path.join(root, "chat_bridge");
    context = await chromium.launchPersistentContext(profile, {
      channel: "chromium",
      ignoreDefaultArgs: ["--disable-extensions"],
      headless: true,
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
    });
    await context.setOffline(true);
    await context.route("https://**/*", route => route.request().url().startsWith("https://chatgpt.com/")
      ? route.fulfill({ contentType: "text/html", body: fixture }) : route.abort());
    worker = context.serviceWorkers()[0] || await context.waitForEvent("serviceworker");
    await installRuntimeFetch(worker);

    parent = await context.newPage();
    parent.on("console", message => {
      if (["error", "warning"].includes(message.type())) console.error("PARENT:", message.text());
    });
    await parent.goto("https://chatgpt.com/");
    await parent.evaluate(() => {
      document.querySelector("#prompt-textarea").textContent = "INITIAL_PARENT";
      document.querySelector("form").requestSubmit();
    });
    await worker.evaluate(async url => {
      const parent = await upsertConversation({ url, enabled: true });
      await mutateState(state => { state.settings.masterEnabled = true; return state; });
      return parent.id;
    }, parentUrl);

    const control = {
      schema_version: 1,
      action: "delegate",
      children: [
        { id: "fast", role: "research", prompt: "Return RESULT_FAST." },
        { id: "slow", role: "verification", prompt: "Return RESULT_SLOW after a longer observation window." },
        { id: "transient", role: "integration", prompt: "Return RESULT_TRANSIENT after a transient observation gap." }
      ]
    };
    await parent.evaluate(controlValue => {
      window.turn("assistant", "<<<LOCAL_AGENT_CF\n" + JSON.stringify(controlValue) + "\nLOCAL_AGENT_CF>>>");
    }, control);

    const campaign = await waitFor("three child delegation", () => worker.evaluate(async () => {
      const campaigns = await listConversationFabricCampaigns();
      return campaigns.find(value => value.state === "running" && value.children?.length === 3) || null;
    }), 30000);
    campaignId = campaign.id;
    assert.equal(campaign.children.length, 3);
    assert.ok(campaign.children.every(child => /<<<LOCAL_AGENT_CF_CHILD_COMPLETE:/.test(child.intent.bootstrap_text)));
    await waitFor("three same-browser child tabs", () => fabricChildren(context).length === 3);
    for (const page of fabricChildren(context)) {
      assert.equal(await page.evaluate(() => window.submitted.length), 1);
    }
    await waitFor("started feedback", () => parent.evaluate(() => window.submitted.length >= 2));

    // Drive collection through the real GitHub-control alarm event. Only the fast child
    // is terminal; slow/transient must remain pending and the fast result must be saved.
    await triggerProductionFabricPoll(worker);
    const partiallyCaptured = await waitFor("durable fast result capture", async () => {
      const value = await campaignSnapshot(worker, campaignId);
      return value?.state === "running" && value.results?.length === 1 ? value : null;
    }, 20000);
    assert.deepEqual(partiallyCaptured.results.map(value => value.assistant_text), ["RESULT_FAST"]);
    assert.ok(partiallyCaptured.children.find(child => child.id === "slow").observation_attempts >= 1);
    assert.ok(partiallyCaptured.children.find(child => child.id === "transient").observation_attempts >= 1);

    const slowPage = await pageForChild(context, "slow");
    const transientPage = await pageForChild(context, "transient");

    // Real MV3 service-worker stop/restart while the campaign is active. Clear
    // storage.session first so recovery cannot depend on transient tab ownership.
    worker = await restartServiceWorker(context, worker, { clearSession: true });
    await waitFor(
      "parent content reinjection in extension isolated world",
      () => contentControllerPresent(worker, parentUrl)
    );
    const afterReload = await campaignSnapshot(worker, campaignId);
    assert.equal(afterReload.state, "running");
    assert.deepEqual(afterReload.results.map(value => value.assistant_text), ["RESULT_FAST"]);

    // Poll once while both remaining children are still incomplete. This exercises
    // transient observation recovery after the real worker restart without replaying bootstrap.
    const submissionsBeforeRecovery = await Promise.all(
      fabricChildren(context).map(page => page.evaluate(() => window.submitted.length))
    );
    await triggerProductionFabricPoll(worker);
    const observedAfterReload = await waitFor("post-reload pending observation", async () => {
      const value = await campaignSnapshot(worker, campaignId);
      const slow = value?.children?.find(child => child.id === "slow");
      const transient = value?.children?.find(child => child.id === "transient");
      return slow?.observation_attempts >= 2 && transient?.observation_attempts >= 2 ? value : null;
    }, 20000);
    assert.deepEqual(observedAfterReload.results.map(value => value.assistant_text), ["RESULT_FAST"]);
    assert.deepEqual(
      await Promise.all(fabricChildren(context).map(page => page.evaluate(() => window.submitted.length))),
      submissionsBeforeRecovery,
      "worker-restart recovery must not replay child bootstraps"
    );

    await slowPage.evaluate(() => window.completeChild());
    await transientPage.evaluate(() => window.completeChild());

    // The real alarm route must now collect both results, cleanup exact owned child tabs,
    // and deliver terminal feedback through runFeedbackCycle exactly once.
    await triggerProductionFabricPoll(worker);
    await parent.waitForFunction(() => document.body.textContent.includes(
      "PARENT_SYNTHESIS: RESULT_FAST + RESULT_SLOW + RESULT_TRANSIENT"
    ), null, { timeout: 30000 });
    const completed = await waitFor("terminal durable campaign", async () => {
      const value = await campaignSnapshot(worker, campaignId);
      return value?.state === "completed" && value.feedback_delivered ? value : null;
    }, 20000);
    assert.deepEqual(
      completed.results.map(value => value.assistant_text).sort(),
      ["RESULT_FAST", "RESULT_SLOW", "RESULT_TRANSIENT"].sort()
    );
    assert.ok(completed.results.every(value => !value.assistant_text.includes("LOCAL_AGENT_CF_CHILD_COMPLETE")));
    assert.ok(completed.results.every(value => !value.assistant_text.includes("LOCAL AGENT BROWSER CHILD")));
    assert.equal(fabricChildren(context).length, 0, "all exact owned child tabs must be closed");

    const terminalPrompts = await parent.evaluate(id => window.submitted.filter(text =>
      text.includes(`Conversation Fabric campaign ${id} completed.`)
    ), campaignId);
    assert.equal(terminalPrompts.length, 1, "terminal feedback must be submitted exactly once");

    // Restart the worker a second time and trigger the same production alarm route.
    // A completed, durably delivered campaign must not reach the parent again.
    worker = await restartServiceWorker(context, worker, { clearSession: true });
    const secondPoll = await triggerProductionFabricPoll(worker);
    assert.equal(
      secondPoll?.ok,
      true,
      "second post-reload production alarm callback must complete before no-replay assertions"
    );
    const afterSecondReload = await campaignSnapshot(worker, campaignId);
    assert.equal(afterSecondReload.state, "completed");
    assert.equal(afterSecondReload.feedback_delivered, true);
    const terminalPromptsAfterReload = await parent.evaluate(id => window.submitted.filter(text =>
      text.includes(`Conversation Fabric campaign ${id} completed.`)
    ), campaignId);
    assert.equal(terminalPromptsAfterReload.length, 1, "terminal campaign must not replay after restart/poll");
    assert.equal(parent.isClosed(), false, "parent must survive child cleanup and worker restarts");

    console.log(
      "PASS: real Bridge delegates three children, durably captures a fast result, " +
      "recovers an active campaign through a real MV3 worker restart, recovers transient " +
      "observations without bootstrap replay, closes owned tabs, delivers terminal feedback " +
      "once, and does not replay it after a second reload/poll."
    );
  } catch (error) {
    if (worker && campaignId) {
      try {
        console.error("CAMPAIGN STATE:", JSON.stringify(await campaignSnapshot(worker, campaignId)));
      } catch (_ignored) {}
    }
    if (parent && !parent.isClosed()) {
      console.error("PARENT STATE:", await parent.evaluate(() => ({
        text: document.body.innerText,
        submitted: window.submitted,
        controller: Boolean(globalThis.__localAgentConversationFabricContent)
      })));
    }
    throw error;
  } finally {
    if (context) await context.close();
    await fs.rm(profile, { recursive: true, force: true });
  }
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
