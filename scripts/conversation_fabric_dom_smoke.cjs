"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright");

const root = path.resolve(__dirname, "..");
const bridge = path.join(root, "chat_bridge");
const parentUrl = "https://chatgpt.com/c/cf-parent-smoke";
const childUrl = "https://chatgpt.com/c/cf-child-smoke";

const parentFixture = `<!doctype html><html><body>
<form id="composer-form">
  <div id="prompt-textarea" contenteditable="true" role="textbox"></div>
  <button id="composer-submit-button" type="submit">Send</button>
</form>
<div id="turns"></div>
<script>
window.__submitted = [];
document.querySelector("#composer-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const composer = document.querySelector("#prompt-textarea");
  const text = String(composer.innerText || composer.textContent || "").trim();
  if (!text) return;
  window.__submitted.push(text);
  const turn = document.createElement("div");
  turn.dataset.turnKey = "user-" + window.__submitted.length;
  const message = document.createElement("div");
  message.dataset.messageAuthorRole = "user";
  message.textContent = text;
  turn.appendChild(message);
  document.querySelector("#turns").appendChild(turn);
  composer.textContent = "";
  composer.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "deleteContent" }));
});
</script>
</body></html>`;

const childFixture = `<!doctype html><html><body>
<div data-turn-key="assistant-child-result">
  <div data-message-author-role="user">USER SECRET MUST NOT LEAK</div>
  <div data-message-author-role="assistant">
    <div class="markdown">CHILD RESULT ALPHA</div>
    <button type="button">Copy</button>
  </div>
</div>
</body></html>`;

async function installParentChromeStub(page) {
  await page.addInitScript(() => {
    window.__cfRuntimeMessages = [];
    const runtime = {
      async sendMessage(message) {
        window.__cfRuntimeMessages.push(JSON.parse(JSON.stringify(message)));
        return { ok: true, reason: "conversation_fabric_started", feedbackPrompt: "FABRIC FEEDBACK" };
      },
      onMessage: { addListener() {}, removeListener() {} }
    };
    globalThis.chrome = globalThis.chrome || {};
    globalThis.chrome.runtime = runtime;
  });
}

async function installChildChromeStub(page) {
  await page.addInitScript(() => {
    const listeners = [];
    globalThis.chrome = globalThis.chrome || {};
    globalThis.chrome.runtime = {
      onMessage: {
        addListener(listener) { listeners.push(listener); },
        removeListener(listener) {
          const index = listeners.indexOf(listener);
          if (index >= 0) listeners.splice(index, 1);
        }
      }
    };
    window.__dispatchExtensionMessage = (message) => new Promise((resolve) => {
      let settled = false;
      const sendResponse = (response) => {
        if (settled) return;
        settled = true;
        resolve(response);
      };
      for (const listener of [...listeners]) {
        const keepAlive = listener(message, {}, sendResponse);
        if (keepAlive === true) return;
      }
      if (!settled) resolve(undefined);
    });
  });
}

async function runParentSmoke(context) {
  const page = await context.newPage();
  await installParentChromeStub(page);
  await page.goto(parentUrl, { waitUntil: "domcontentloaded" });
  for (const filename of [
    "control_protocol.js",
    "conversation_fabric_protocol.js",
    "content_retry.js",
    "conversation_fabric_content.js"
  ]) {
    await page.addScriptTag({ path: path.join(bridge, filename) });
  }

  const control = {
    schema_version: 1,
    action: "delegate",
    children: [
      { id: "audit", role: "research", prompt: "Audit one bounded topic." },
      { id: "verify", role: "verification", prompt: "Verify one independent topic." }
    ]
  };
  const assistantText = [
    "I am delegating two bounded reasoning jobs.",
    "<<<LOCAL_AGENT_CF",
    JSON.stringify(control),
    "LOCAL_AGENT_CF>>>"
  ].join("\n");
  await page.evaluate((text) => {
    const turn = document.createElement("div");
    turn.dataset.turnKey = "assistant-parent-control";
    const message = document.createElement("div");
    message.dataset.messageAuthorRole = "assistant";
    message.textContent = text;
    turn.appendChild(message);
    document.querySelector("#turns").appendChild(turn);
  }, assistantText);

  await page.waitForFunction(() => window.__cfRuntimeMessages.length === 1);
  const runtimeMessage = await page.evaluate(() => window.__cfRuntimeMessages[0]);
  assert.equal(runtimeMessage.type, "bridge:conversation-fabric-control");
  assert.equal(runtimeMessage.conversationUrl, parentUrl);
  assert.equal(runtimeMessage.control.action, "delegate");
  assert.equal(runtimeMessage.control.children.length, 2);
  assert.equal(runtimeMessage.contentProtocolVersion, 14);

  await page.waitForFunction(() => window.__submitted.includes("FABRIC FEEDBACK"));
  assert.deepEqual(await page.evaluate(() => window.__submitted), ["FABRIC FEEDBACK"]);
  await page.close();
}

async function runChildSmoke(context) {
  const page = await context.newPage();
  await installChildChromeStub(page);
  await page.goto(childUrl, { waitUntil: "domcontentloaded" });
  const transactionId = `spawn-${"a".repeat(64)}`;
  const childRequestDigest = `sha256:${"b".repeat(64)}`;
  const bootstrapDigest = `sha256:${"c".repeat(64)}`;
  await page.evaluate(({ transactionId, childRequestDigest, bootstrapDigest }) => {
    sessionStorage.setItem(`local-agent:conversation-spawn:${transactionId}`, JSON.stringify({
      transactionId,
      childRequestDigest,
      bootstrapDigest,
      state: "submitted",
      childConversationUrl: location.href
    }));
  }, { transactionId, childRequestDigest, bootstrapDigest });

  for (const filename of ["control_protocol.js", "spawn_result_content.js"]) {
    await page.addScriptTag({ path: path.join(bridge, filename) });
  }
  const message = {
    type: "bridge:spawn-result",
    protocolVersion: 1,
    transactionId,
    childRequestDigest,
    bootstrapDigest
  };
  const result = await page.evaluate(
    (payload) => window.__dispatchExtensionMessage(payload),
    message
  );
  assert.equal(result.ok, true, JSON.stringify(result));
  assert.equal(result.reason, "child_result_ready");
  assert.equal(result.childConversationUrl, childUrl);
  assert.equal(result.assistantIdentity, "assistant-child-result");
  assert.equal(result.assistantText, "CHILD RESULT ALPHA");
  assert.doesNotMatch(result.assistantText, /USER SECRET|Copy/);

  const rejected = await page.evaluate(
    (payload) => window.__dispatchExtensionMessage(payload),
    { ...message, childRequestDigest: `sha256:${"d".repeat(64)}` }
  );
  assert.equal(rejected.ok, false);
  assert.equal(rejected.reason, "spawn_claim_conflict");
  await page.close();
}

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.route("https://chatgpt.com/**", async (route) => {
    const url = route.request().url();
    const body = url.includes("cf-child-smoke") ? childFixture : parentFixture;
    await route.fulfill({ status: 200, contentType: "text/html", body });
  });
  try {
    await runParentSmoke(context);
    await runChildSmoke(context);
    console.log("Conversation Fabric DOM smoke passed.");
  } finally {
    await context.close();
    await browser.close();
  }
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
