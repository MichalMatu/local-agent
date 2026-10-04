"use strict";

// Offline proof with the real extension: parent control -> two child tabs -> results -> parent.
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
document.querySelector("form").onsubmit = (event) => {
  event.preventDefault();
  const composer = document.querySelector("#prompt-textarea");
  const text = composer.innerText || composer.textContent;
  window.submitted.push(text);
  turn("user", text);
  composer.textContent = "";
  composer.dispatchEvent(new Event("input", {bubbles: true}));
  if (text === "INITIAL_PARENT") { history.pushState({}, "", "/c/fabric-parent-proof"); turn("assistant", "READY"); }
  const child = text.match(/^child_id=(.+)$/m);
  if (child) {
    history.pushState({}, "", "/c/fabric-child-" + child[1]);
    turn("assistant", "RESULT_" + child[1].toUpperCase());
  } else if (text.includes("completed.") && text.includes("RESULT_A") && text.includes("RESULT_B")) {
    turn("assistant", "PARENT_SYNTHESIS: RESULT_A + RESULT_B");
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

(async () => {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), "fabric-browser-proof-"));
  let context;
  let worker;
  let parent;
  try {
    const extension = path.join(root, "chat_bridge");
    context = await chromium.launchPersistentContext(profile, {
      channel: "chromium",
      ignoreDefaultArgs: ["--disable-extensions"], headless: true,
      args: [`--disable-extensions-except=${extension}`, `--load-extension=${extension}`]
    });
    await context.setOffline(true);
    await context.route("https://**/*", route => route.request().url().startsWith("https://chatgpt.com/")
      ? route.fulfill({ contentType: "text/html", body: fixture }) : route.abort());
    worker = context.serviceWorkers()[0] || await context.waitForEvent("serviceworker");
    await worker.evaluate(runtime => { globalThis.fetch = async () => ({ ok: true, json: async () => runtime }); }, catalog);
    parent = await context.newPage();
    parent.on("console", message => { if (["error", "warning"].includes(message.type())) console.error("PARENT:", message.text()); });
    await parent.goto("https://chatgpt.com/");
    await parent.evaluate(() => { document.querySelector("#prompt-textarea").textContent = "INITIAL_PARENT"; document.querySelector("form").requestSubmit(); });
    await worker.evaluate(async url => {
      const parent = await upsertConversation({ url, enabled: true });
      await mutateState(state => { state.settings.masterEnabled = true; return state; });
      return parent.id;
    }, parentUrl);
    const control = { schema_version: 1, action: "delegate", children: [
      { id: "a", role: "research", prompt: "Return RESULT_A." },
      { id: "b", role: "verification", prompt: "Return RESULT_B." }
    ] };
    await parent.evaluate(control => {
      window.turn("assistant", "<<<LOCAL_AGENT_CF\n" + JSON.stringify(control) + "\nLOCAL_AGENT_CF>>>");
    }, control);
    const campaign = await waitFor("two child delegation", () => worker.evaluate(async () => {
      const campaigns = await listConversationFabricCampaigns();
      return campaigns.find(value => value.state === "running") || null;
    }));
    assert.equal(campaign.children.length, 2);
    const children = context.pages().filter(page => page.url().includes("/c/fabric-child-"));
    assert.equal(children.length, 2, "children must be tabs in the same browser context");
    for (const page of children) assert.equal(await page.evaluate(() => window.submitted.length), 1);
    await waitFor("started feedback", () => parent.evaluate(() => window.submitted.length === 2));
    await worker.evaluate(() => chrome.storage.session.clear());
    await worker.evaluate(async tabId => {
      await chrome.scripting.executeScript({ target: { tabId, frameIds: [0] }, func: () => {
        globalThis.__localAgentConversationSpawnResultContent.dispose();
      } });
    }, campaign.children[0].intent.tab_id);
    const invalid = { ...campaign.children[0].intent, child_request_digest: `sha256:${"a".repeat(64)}` };
    const refused = await worker.evaluate(intent => observeConversationSpawnResult(intent), invalid);
    assert.equal(refused.ok, false, "session recovery must reject a mismatched page claim");
    const recovered = await worker.evaluate(intent => observeConversationSpawnResult(intent), campaign.children[0].intent);
    assert.equal(recovered.reason, "child_result_ready", "reinjection must replace a detached listener even with an unchanged wire protocol");
    await worker.evaluate(() => pollConversationFabricCampaigns());
    await parent.waitForFunction(() => document.body.textContent.includes("PARENT_SYNTHESIS: RESULT_A + RESULT_B"));
    const completed = await worker.evaluate(id => loadConversationFabricCampaign(id), campaign.id);
    assert.equal(completed.state, "completed");
    assert.equal(completed.feedback_delivered, true);
    assert.equal(completed.results.length, 2);
    assert.deepEqual(completed.results.map(value => value.assistant_text), ["RESULT_A", "RESULT_B"]);
    assert.ok(completed.results.every(value => !value.assistant_text.includes("LOCAL AGENT BROWSER CHILD")));
    assert.equal(context.pages().filter(page => page.url().includes("/c/fabric-child-")).length, 0);
    const submittedBefore = await parent.evaluate(() => window.submitted.length);
    await worker.evaluate(() => pollConversationFabricCampaigns());
    assert.equal(await parent.evaluate(() => window.submitted.length), submittedBefore, "result feedback must not be replayed");
    assert.equal(parent.isClosed(), false, "parent must survive child cleanup");
    console.log("PASS: real Bridge delegates two same-browser children, captures results, closes owned tabs and delivers one parent synthesis.");
  } catch (error) {
    if (worker) console.error("CAMPAIGN STATE:", JSON.stringify(await worker.evaluate(() => listConversationFabricCampaigns())));
    if (parent) console.error("PARENT STATE:", await parent.evaluate(() => ({text: document.body.innerText, controller: Boolean(globalThis.__localAgentConversationFabricContent)})));
    throw error;
  } finally {
    if (context) await context.close();
    await fs.rm(profile, { recursive: true, force: true });
  }
})().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
