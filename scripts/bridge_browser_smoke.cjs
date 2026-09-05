"use strict";

// Isolated Chromium fixture: never contacts ChatGPT or the operator's profile.
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(__dirname, "..");
const catalog = require(path.join(root, "chat_bridge/runtime.example.json"));

async function bounded(label, promise) {
  let timer;
  try {
    return await Promise.race([promise, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(`${label} exceeded 10 seconds`)), 10_000);
    })]);
  } finally { clearTimeout(timer); }
}

const fixture = `<!doctype html><html><body>
<div data-message-author-role="assistant" data-message-id="old-answer">Previous answer</div>
<form id="composer-form">
  <div id="prompt-textarea" class="ProseMirror" contenteditable="true" role="textbox"></div>
  <button id="composer-submit-button" type="submit">Send</button>
</form>
<script>
window.submits = 0;
window.dropDelivery = false;
window.replaceComposerOnSubmit = false;
document.querySelector('form').onsubmit = (event) => {
  event.preventDefault();
  window.submits++;
  if (window.dropDelivery) return;
  const form = document.querySelector('#composer-form');
  const input = form.querySelector('#prompt-textarea');
  const message = document.createElement('div');
  message.dataset.messageAuthorRole = 'user';
  message.textContent = input.innerText || input.textContent || '';
  document.body.append(message);
  if (window.replaceComposerOnSubmit) {
    form.innerHTML = '<div id="prompt-textarea" class="ProseMirror" contenteditable="true" role="textbox"></div><button id="composer-submit-button" type="submit">Send</button>';
    return;
  }
  input.textContent = '';
  input.dispatchEvent(new Event('input', { bubbles: true }));
};
</script></body></html>`;

(async () => {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), "bridge-browser-"));
  let context;
  try {
    const extension = path.join(root, "chat_bridge");
    const launch = () => chromium.launchPersistentContext(profile, {
      channel: "chromium", headless: true,
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
    });
    context = await launch();
    await context.setOffline(true);
    const installRoutes = () => context.route("https://**/*", (route) => {
      if (route.request().url().startsWith("https://chatgpt.com/c/bridge-fixture")) {
        return route.fulfill({ contentType: "text/html", body: fixture });
      }
      return route.abort();
    });
    await installRoutes();
    const worker = context.serviceWorkers()[0] || await context.waitForEvent("serviceworker");
    const mockRuntime = async () => bounded("runtime fixture setup", worker.evaluate((runtime) => {
      globalThis.fetch = async () => ({ ok: true, json: async () => runtime });
    }, catalog));
    await mockRuntime();
    const extensionId = new URL(worker.url()).host;
    let page = await context.newPage();
    let popup = await context.newPage();
    await popup.goto(`chrome-extension://${extensionId}/popup.html`);
    const request = (message) => bounded(message.type, popup.evaluate((value) => chrome.runtime.sendMessage(value), message));
    const readChat = async (id) => (await request({ type: "bridge:get-state" })).state.conversations[id];
    const add = async (suffix) => {
      const url = `https://chatgpt.com/c/bridge-fixture-${suffix}`;
      await page.goto(url);
      const result = await request({ type: "bridge:upsert-conversation", conversation: {
        url, agentBinding: catalog.agents.find((agent) => agent.repository_id === "tracker").agent_binding,
        enabled: false
      } });
      assert.equal(result.ok, true, result.error);
      return result.conversation.id;
    };
    const run = (id) => request({ type: "bridge:run-now", conversationId: id });
    const prepare = () => page.evaluate(() => { document.querySelector("button").disabled = true; });
    const waitInsertion = () => page.waitForFunction(() => document.querySelector("#prompt-textarea").textContent.length > 0);
    const composerText = () => page.locator("#prompt-textarea").textContent();

    let id = await add("success");
    assert.equal((await run(id)).reason, "sent");
    assert.equal(await page.evaluate(() => window.submits), 1);
    assert.match(await page.locator('[data-message-author-role="user"]').innerText(), /LA_REPO=tracker/);
    assert.equal((await readChat(id)).bootstrapPending, false);
    console.log("PASS: confirmed contenteditable form delivery, capability preflight and exact repository binding");

    id = await add("replacement");
    await page.evaluate(() => { window.replaceComposerOnSubmit = true; });
    assert.equal((await run(id)).reason, "sent");
    assert.equal(await page.evaluate(() => window.submits), 1);
    assert.match(await page.locator('[data-message-author-role="user"]').innerText(), /LA_REPO=tracker/);
    console.log("PASS: composer DOM replacement after submit still confirms exact user delivery");

    id = await add("draft");
    await prepare();
    let delivery = run(id);
    await waitInsertion();
    await page.locator("#prompt-textarea").fill("Operator draft must survive");
    assert.equal((await delivery).reason, "send_button_not_ready");
    assert.equal(await composerText(), "Operator draft must survive");
    assert.equal(await page.evaluate(() => window.submits), 0);
    console.log("PASS: concurrent operator draft preserved");

    id = await add("whitespace-edit");
    await prepare();
    delivery = run(id);
    await waitInsertion();
    await page.evaluate(() => {
      const input = document.querySelector("#prompt-textarea");
      input.textContent = ` ${input.textContent}`;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      document.querySelector("button").disabled = false;
    });
    assert.equal((await delivery).reason, "composer_changed");
    assert.ok((await composerText()).startsWith(" "));
    assert.equal(await page.evaluate(() => window.submits), 0);
    console.log("PASS: whitespace-only operator edit is preserved and never submitted");

    id = await add("navigation");
    await prepare();
    delivery = run(id);
    await waitInsertion();
    await page.evaluate(() => {
      history.pushState({}, "", "/c/bridge-fixture-other");
      document.querySelector("button").disabled = false;
    });
    assert.equal((await delivery).ok, false);
    assert.equal(await page.evaluate(() => window.submits), 0);
    console.log("PASS: SPA navigation cannot redirect a wake");

    id = await add("overlap");
    await prepare();
    delivery = run(id);
    await waitInsertion();
    assert.equal((await run(id)).reason, "delivery_in_progress");
    await page.evaluate(() => { document.querySelector("button").disabled = false; });
    assert.equal((await delivery).reason, "sent");
    assert.equal(await page.evaluate(() => window.submits), 1);
    console.log("PASS: overlapping sends submit once");

    id = await add("uncertain");
    await page.evaluate(() => { window.dropDelivery = true; });
    assert.equal((await run(id)).reason, "delivery_uncertain");
    assert.equal((await readChat(id)).enabled, false);
    assert.ok((await readChat(id)).pendingDelivery);
    assert.equal((await run(id)).reason, "delivery_uncertain");
    assert.equal(await page.evaluate(() => window.submits), 1);
    console.log("PASS: unconfirmed submission pauses without retry");

    const removePendingId = await add("remove-pending");
    await page.evaluate(() => { window.dropDelivery = true; });
    assert.equal((await run(removePendingId)).reason, "delivery_uncertain");
    await popup.reload();
    assert.equal(await popup.locator(".current-chat-panel .small-copy").count(), 0);
    assert.match(
      await popup.locator(".current-chat-panel .info-icon").getAttribute("title"),
      /explicitly bound to exactly one agent UUID and repository/
    );
    assert.equal(await popup.locator(".has-pending-delivery .resolution-sent").count(), 2);
    assert.equal(await popup.locator(".has-pending-delivery .resolution-not-sent").count(), 2);
    assert.equal(await popup.getByRole("button", { name: "Wake was sent", exact: true }).count(), 0);
    assert.equal(await popup.getByRole("button", { name: "Wake was not sent", exact: true }).count(), 0);
    popup.once("dialog", (dialog) => dialog.accept());
    await popup.locator(".has-pending-delivery .danger").last().click();
    await popup.waitForFunction(() => document.querySelectorAll(".has-pending-delivery").length === 1);
    const stateAfterRemove = (await request({ type: "bridge:get-state" })).state;
    assert.equal(Object.keys(stateAfterRemove.conversations).length, 7);
    const remainingPending = Object.values(stateAfterRemove.conversations).filter((item) => item.pendingDelivery);
    assert.equal(remainingPending.length, 1);
    id = remainingPending[0].id;
    const pendingUrl = remainingPending[0].url;
    console.log("PASS: compact popup uses ✓/× resolution icons, tooltip help and working pending Remove");

    await bounded("browser shutdown", context.close());
    context = await launch();
    await context.setOffline(true);
    await installRoutes();
    page = await context.newPage();
    await page.goto(pendingUrl);
    popup = await context.newPage();
    await popup.goto(`chrome-extension://${extensionId}/popup.html`);
    assert.equal((await run(id)).reason, "delivery_uncertain");
    assert.equal(await page.evaluate(() => window.submits), 0);
    const resolved = await request({ type: "bridge:resolve-delivery", conversationId: id, wasSent: false });
    assert.equal(resolved.ok, true, resolved.error);
    assert.equal(resolved.conversation.enabled, false);
    assert.equal(resolved.conversation.pendingDelivery, null);
    assert.equal(await page.evaluate(() => window.submits), 0);
    console.log("PASS: browser/worker restart preserves journal; explicit resolution does not send");
  } finally {
    if (context) await context.close();
    await fs.rm(profile, { recursive: true, force: true });
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
