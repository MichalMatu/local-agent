"use strict";

// Isolated Chromium fixture: verifies bounded connection interruption recovery through
// the real unpacked extension, including one Continue. submission and one whole-tab reload.
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(__dirname, "..");
const catalog = require(path.join(root, "chat_bridge/runtime.example.json"));

async function bounded(label, promise, timeoutMs = 20_000) {
  let timer;
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(`${label} exceeded ${timeoutMs} ms`)), timeoutMs);
    })]);
  } finally {
    clearTimeout(timer);
  }
}

const fixture = `<!doctype html><html><body>
<div data-message-author-role="assistant" data-message-id="old-answer">Previous answer</div>
<form id="composer-form">
  <div id="prompt-textarea" contenteditable="true" data-lexical-editor="true"></div>
  <button id="composer-submit-button" type="submit">Send</button>
</form>
<script>
function count(key) { return Number(localStorage.getItem(key) || '0'); }
localStorage.setItem('loadCount', String(count('loadCount') + 1));

function removeCurrentAssistant() {
  document.querySelectorAll('[data-fixture-current-assistant]').forEach((node) => node.remove());
}

function appendUser(prompt) {
  const user = document.createElement('section');
  user.dataset.turn = 'user';
  user.dataset.turnId = 'user-' + String(count('submitCount'));
  user.dataset.messageAuthorRole = 'user';
  user.dataset.messageId = user.dataset.turnId;
  user.textContent = prompt;
  document.body.append(user);
}

function appendInterrupted() {
  removeCurrentAssistant();
  const turn = document.createElement('section');
  turn.dataset.turn = 'assistant';
  turn.dataset.turnId = 'request-connection-interrupted';
  turn.dataset.fixtureCurrentAssistant = '1';
  const status = document.createElement('div');
  status.className = 'mask-shimmer-muted';
  status.textContent = 'Connection interrupted. Waiting for the complete answer';
  turn.append(status);
  document.body.append(turn);
}

const retainedUsers = JSON.parse(localStorage.getItem('users') || '[]');
for (const prompt of retainedUsers) appendUser(prompt);
if (retainedUsers.length) appendInterrupted();

document.querySelector('form').onsubmit = (event) => {
  event.preventDefault();
  const input = document.querySelector('#prompt-textarea');
  const prompt = input.innerText || input.textContent || '';
  const users = JSON.parse(localStorage.getItem('users') || '[]');
  users.push(prompt);
  localStorage.setItem('users', JSON.stringify(users));
  localStorage.setItem('submitCount', String(count('submitCount') + 1));
  appendUser(prompt);
  input.textContent = '';
  input.dispatchEvent(new Event('input', { bubbles: true }));
  setTimeout(appendInterrupted, 50);
};
</script></body></html>`;

(async () => {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), "bridge-transient-recovery-"));
  let context;
  try {
    const extension = path.join(root, "chat_bridge");
    context = await chromium.launchPersistentContext(profile, {
      channel: "chromium",
      headless: true,
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
    });
    await context.setOffline(true);

    const url = "https://chatgpt.com/c/transient-recovery-fixture";
    await context.route("https://**/*", (route) => {
      if (route.request().url() === url) return route.fulfill({ contentType: "text/html", body: fixture });
      return route.abort();
    });

    const worker = context.serviceWorkers()[0] || await context.waitForEvent("serviceworker");
    await bounded("runtime fixture setup", worker.evaluate((runtime) => {
      globalThis.fetch = async () => ({ ok: true, json: async () => runtime });
    }, catalog));
    const extensionId = new URL(worker.url()).host;
    const popup = await context.newPage();
    await popup.goto(`chrome-extension://${extensionId}/popup.html`);
    const request = (message, timeoutMs = 15_000) => bounded(
      message.type,
      popup.evaluate((value) => chrome.runtime.sendMessage(value), message),
      timeoutMs
    );
    await request({
      type: "bridge:save-global-settings",
      settings: { runtimeUrl: `chrome-extension://${extensionId}/runtime.example.json` }
    });

    const page = await context.newPage();
    await page.goto(url);
    const matrix = catalog.agents.find((agent) => agent.repository_id === "matrixhub");
    const added = await request({
      type: "bridge:upsert-conversation",
      conversation: {
        url,
        label: "transient recovery fixture",
        agentBinding: matrix.agent_binding,
        enabled: true,
        preferredTabId: (await page.evaluate(() => null))
      }
    });
    assert.equal(added.ok, true, added.error);

    const delivery = await request({ type: "bridge:run-now", conversationId: added.conversation.id });
    assert.equal(delivery.ok, true);
    assert.equal(delivery.reason, "sent");
    await page.waitForFunction(() => document.body.textContent.includes('Connection interrupted.'), null, {
      timeout: 5000
    });

    let recovery = await request({ type: "bridge:run-now", conversationId: added.conversation.id });
    assert.equal(recovery.reason, "assistant_connection_interrupted");
    assert.equal(await page.evaluate(() => Number(localStorage.getItem('submitCount') || '0')), 1);

    await popup.evaluate((chatId) => new Promise((resolve) => {
      chrome.storage.local.get('bridgeAssistantTransientRecovery', (stored) => {
        const state = stored.bridgeAssistantTransientRecovery;
        state.entries[chatId].firstSeenAt = new Date(Date.now() - 60_000).toISOString();
        chrome.storage.local.set({ bridgeAssistantTransientRecovery: state }, resolve);
      });
    }), added.conversation.id);

    recovery = await request({ type: "bridge:run-now", conversationId: added.conversation.id });
    assert.equal(recovery.reason, "assistant_connection_continue_sent");
    await page.waitForFunction(() => Number(localStorage.getItem('submitCount') || '0') === 2, null, {
      timeout: 5000
    });
    assert.equal(await page.evaluate(() => {
      const users = JSON.parse(localStorage.getItem('users') || '[]');
      return users.at(-1);
    }), "Continue.");

    await popup.evaluate((chatId) => new Promise((resolve) => {
      chrome.storage.local.get('bridgeAssistantTransientRecovery', (stored) => {
        const state = stored.bridgeAssistantTransientRecovery;
        state.entries[chatId].continueSentAt = new Date(Date.now() - 70_000).toISOString();
        chrome.storage.local.set({ bridgeAssistantTransientRecovery: state }, resolve);
      });
    }), added.conversation.id);

    recovery = await request({ type: "bridge:run-now", conversationId: added.conversation.id });
    assert.equal(recovery.reason, "assistant_tab_reloaded");
    await page.waitForFunction(() => Number(localStorage.getItem('loadCount') || '0') === 2, null, {
      timeout: 5000
    });

    recovery = await request({ type: "bridge:run-now", conversationId: added.conversation.id });
    assert.equal(recovery.reason, "assistant_connection_reload_exhausted");
    await new Promise((resolve) => setTimeout(resolve, 500));
    assert.equal(await page.evaluate(() => Number(localStorage.getItem('loadCount') || '0')), 2,
      "durable recovery reservation must prevent a reload loop");
    assert.equal(await page.evaluate(() => Number(localStorage.getItem('submitCount') || '0')), 2,
      "recovery must submit only the original Bridge wake and one Continue.");

    console.log("PASS: real extension performs wait -> Continue. -> one whole-tab reload without replay loops");
  } finally {
    await context?.close();
    await fs.rm(profile, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
