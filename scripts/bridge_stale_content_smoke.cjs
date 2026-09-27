"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright");

const root = path.resolve(__dirname, "..");
const catalog = require(path.join(root, "chat_bridge/runtime.example.json"));
const conversationUrl = "https://chatgpt.com/c/stale-content-fixture";

const fixture = `<!doctype html><html><body>
<div data-message-author-role="assistant" data-message-id="old-answer">Previous answer</div>
<form id="composer-form">
  <div id="prompt-textarea" class="ProseMirror" contenteditable="true" role="textbox"></div>
  <button id="composer-submit-button" type="submit">Send</button>
</form>
<script>
window.submits = 0;
document.querySelector('#composer-form').onsubmit = (event) => {
  event.preventDefault();
  window.submits += 1;
  const input = document.querySelector('#prompt-textarea');
  const message = document.createElement('div');
  message.dataset.messageAuthorRole = 'user';
  message.textContent = input.innerText || input.textContent || '';
  document.body.append(message);
  input.textContent = '';
  input.dispatchEvent(new Event('input', { bubbles: true }));
};
</script></body></html>`;

function bounded(label, promise) {
  let timer;
  return Promise.race([
    promise.finally(() => clearTimeout(timer)),
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(`${label} exceeded 10 seconds`)), 10_000);
    })
  ]);
}

async function inspectBridge(worker) {
  return worker.evaluate(async (url) => {
    const tabs = await chrome.tabs.query({ url: ["https://chatgpt.com/*"] });
    const tab = tabs.find((item) => item.url === url);
    if (!tab?.id) return { found: false, hadBridge: false };
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id, frameIds: [0] },
      func: () => ({
        hadBridge: Boolean(globalThis.__localAgentChatBridgeState),
        protocolVersion: globalThis.__localAgentChatBridgeState?.protocolVersion || null
      })
    });
    return { found: true, tabId: tab.id, ...(result?.result || {}) };
  }, conversationUrl);
}

(async () => {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), "bridge-stale-content-"));
  let context;
  try {
    const extension = path.join(root, "chat_bridge");
    context = await chromium.launchPersistentContext(profile, {
      channel: "chromium",
      headless: true,
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
    });
    await context.setOffline(true);
    await context.route("https://**/*", (route) => {
      if (route.request().url() === conversationUrl) {
        return route.fulfill({ contentType: "text/html", body: fixture });
      }
      return route.abort();
    });

    const worker = context.serviceWorkers()[0] || await context.waitForEvent("serviceworker");
    await bounded("runtime fixture setup", worker.evaluate((runtime) => {
      globalThis.fetch = async () => ({ ok: true, json: async () => runtime });
    }, catalog));
    const extensionId = new URL(worker.url()).host;

    const page = await context.newPage();
    await page.goto(conversationUrl);
    await page.waitForSelector("#prompt-textarea");

    const popup = await context.newPage();
    await popup.goto(`chrome-extension://${extensionId}/popup.html`);
    const request = (message) => bounded(
      message.type,
      popup.evaluate((value) => chrome.runtime.sendMessage(value), message)
    );
    const runtimeSetup = await request({
      type: "bridge:save-global-settings",
      settings: { runtimeUrl: `chrome-extension://${extensionId}/runtime.example.json` }
    });
    assert.equal(runtimeSetup?.ok, true, runtimeSetup?.error || "runtime fixture setup failed");

    const tracker = catalog.agents.find((agent) => agent.repository_id === "tracker");
    assert.ok(tracker?.agent_binding, "tracker binding fixture is required");
    const added = await request({
      type: "bridge:upsert-conversation",
      conversation: {
        url: conversationUrl,
        label: "stale-content",
        agentBinding: tracker.agent_binding,
        enabled: false
      }
    });
    assert.equal(added?.ok, true, added?.error || "conversation setup failed");

    const bridge = await bounded("initial content script", (async () => {
      for (let attempt = 0; attempt < 50; attempt += 1) {
        const current = await inspectBridge(worker);
        if (current.hadBridge) return current;
        await page.waitForTimeout(100);
      }
      throw new Error("manifest content script did not initialize");
    })());
    assert.equal(bridge.protocolVersion, 7, "fixture must start with the current content protocol");

    const sabotaged = await bounded("stale content setup", worker.evaluate(async (url) => {
      const tabs = await chrome.tabs.query({ url: ["https://chatgpt.com/*"] });
      const tab = tabs.find((item) => item.url === url);
      if (!tab?.id) return { found: false };
      const [result] = await chrome.scripting.executeScript({
        target: { tabId: tab.id, frameIds: [0] },
        func: () => {
          const bridgeState = globalThis.__localAgentChatBridgeState;
          const before = {
            hadBridge: Boolean(bridgeState),
            protocolVersion: bridgeState?.protocolVersion || null
          };
          bridgeState?.dispose?.();
          return {
            ...before,
            retainedAfterDispose: globalThis.__localAgentChatBridgeState === bridgeState
          };
        }
      });
      return { found: true, ...(result?.result || {}) };
    }, conversationUrl));
    assert.equal(sabotaged.found, true);
    assert.equal(sabotaged.hadBridge, true);
    assert.equal(sabotaged.protocolVersion, 7);
    assert.equal(sabotaged.retainedAfterDispose, true, "test must retain stale same-version page state");

    const delivery = await request({
      type: "bridge:run-now",
      conversationId: added.conversation.id
    });
    assert.equal(delivery?.ok, true, delivery?.reason || delivery?.error);
    assert.equal(delivery.reason, "sent");
    assert.equal(await page.evaluate(() => window.submits), 1);
    assert.match(
      await page.locator('[data-message-author-role="user"]').innerText(),
      /LA_REPO=tracker/
    );

    const recovered = await inspectBridge(worker);
    assert.equal(recovered.hadBridge, true);
    assert.equal(recovered.protocolVersion, 7);
    console.log("PASS: Run now hard-refreshes a stale same-version content receiver and submits once");
  } finally {
    if (context) await context.close();
    await fs.rm(profile, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
