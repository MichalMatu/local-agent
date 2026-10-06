"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const { chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright");

const root = path.resolve(__dirname, "..");
const bridge = path.join(root, "chat_bridge");
const parentUrl = "https://chatgpt.com/c/cf-parent-smoke";
const childUrl = "https://chatgpt.com/c/cf-child-smoke";
const completionMarkerRe = /<<<LOCAL_AGENT_CF_CHILD_COMPLETE:[0-9a-f]{8}:[A-Za-z0-9._-]{1,64}:[0-9a-f]{8}>>>/;

const parentFixture = `<!doctype html><html><body>
<form id="composer-form">
  <div id="prompt-textarea" contenteditable="true" role="textbox"></div>
  <button data-testid="composer-submit-button" type="submit">Send</button>
</form>
<div id="turns"></div>
<script>
window.__submitted = [];
window.__sendReplacementCount = 0;
document.querySelector("#prompt-textarea").addEventListener("input", () => {
  const composer = document.querySelector("#prompt-textarea");
  if (!String(composer.innerText || composer.textContent || "").trim()) return;
  const current = document.querySelector('button[data-testid="composer-submit-button"]');
  if (!current) return;
  const replacement = current.cloneNode(true);
  current.replaceWith(replacement);
  window.__sendReplacementCount += 1;
});
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

const childFixture = `<!doctype html><html><body><div id="turns"></div></body></html>`;

async function installParentChromeStub(page) {
  await page.addInitScript(() => {
    window.__cfRuntimeMessages = [];
    const runtime = {
      async sendMessage(message) {
        window.__cfRuntimeMessages.push(JSON.parse(JSON.stringify(message)));
        return message.type === "bridge:conversation-fabric-feedback" ? { ok: true } :
          { ok: true, reason: "conversation_fabric_started", campaignId: "cf-1234567890abcdef", feedbackPrompt: "FABRIC FEEDBACK" };
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
  const malformedAssistantText = [
    "I am delegating two bounded reasoning jobs.",
    "<<<LOCAL_AGENT_CF",
    JSON.stringify(control),
    "LOCAL_AGENT_CF>>>",
    "This trailing prose makes the control unsupported."
  ].join("\n");
  await page.evaluate((text) => {
    const turn = document.createElement("div");
    turn.dataset.turnKey = "assistant-parent-control-invalid";
    const message = document.createElement("div");
    message.dataset.messageAuthorRole = "assistant";
    for (const line of text.split("\n")) {
      const paragraph = document.createElement("p");
      paragraph.textContent = line;
      message.appendChild(paragraph);
    }
    turn.appendChild(message);
    document.querySelector("#turns").appendChild(turn);
  }, malformedAssistantText);

  await page.waitForFunction(() => window.__submitted.some(text =>
    text.includes("Conversation Fabric control rejected: reason=control_not_terminal")
  ));
  assert.equal(
    await page.evaluate(() => window.__cfRuntimeMessages.filter(message =>
      message.type === "bridge:conversation-fabric-control"
    ).length),
    0,
    "visible malformed/non-terminal control must be diagnosed without Fabric control dispatch"
  );

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
    for (const line of text.split("\n")) {
      const paragraph = document.createElement("p");
      paragraph.textContent = line;
      message.appendChild(paragraph);
    }
    turn.appendChild(message);
    document.querySelector("#turns").appendChild(turn);
  }, assistantText);

  await page.waitForFunction(() => window.__cfRuntimeMessages.some(message =>
    message.type === "bridge:conversation-fabric-control"
  ));
  const runtimeMessage = await page.evaluate(() => window.__cfRuntimeMessages.find(message =>
    message.type === "bridge:conversation-fabric-control"
  ));
  assert.equal(runtimeMessage.type, "bridge:conversation-fabric-control");
  assert.equal(runtimeMessage.conversationUrl, parentUrl);
  assert.equal(runtimeMessage.control.action, "delegate");
  assert.equal(runtimeMessage.control.children.length, 2);
  assert.equal(runtimeMessage.contentProtocolVersion, require(path.join(bridge, "control_protocol.js")).CONTENT_PROTOCOL_VERSION);

  const markers = runtimeMessage.control.children.map((child) => {
    const match = String(child.prompt || "").match(completionMarkerRe);
    assert.ok(match, `missing completion marker for child ${child.id}`);
    assert.match(child.prompt, /Never emit this marker in progress/);
    return match[0];
  });
  assert.notEqual(markers[0], markers[1], "each child must have a unique completion marker");

  await page.waitForFunction(() => window.__submitted.includes("FABRIC FEEDBACK"));
  const submitted = await page.evaluate(() => window.__submitted);
  assert.equal(submitted.length, 2);
  assert.match(submitted[0], /control_not_terminal/);
  assert.equal(submitted[1], "FABRIC FEEDBACK");
  assert.ok(
    await page.evaluate(() => window.__sendReplacementCount >= 2),
    "Fabric feedback must survive ChatGPT replacing the live Send button after composer input"
  );
  await page.close();
  return markers[0];
}

async function setChildAssistant(page, text, { generating = false } = {}) {
  await page.evaluate(({ text, generating }) => {
    const turns = document.querySelector("#turns");
    turns.textContent = "";
    const turn = document.createElement("div");
    turn.dataset.turnKey = "assistant-child-result";

    const user = document.createElement("div");
    user.dataset.messageAuthorRole = "user";
    user.textContent = "USER SECRET MUST NOT LEAK";
    turn.appendChild(user);

    const assistant = document.createElement("div");
    assistant.dataset.messageAuthorRole = "assistant";
    const body = document.createElement("div");
    body.className = "markdown";
    body.textContent = text;
    assistant.appendChild(body);
    const copy = document.createElement("button");
    copy.type = "button";
    copy.textContent = "Copy";
    assistant.appendChild(copy);
    turn.appendChild(assistant);
    turns.appendChild(turn);

    document.querySelectorAll('[data-testid="stop-button"], [data-testid="composer-stop-button"]').forEach((node) => node.remove());
    if (generating) {
      const stop = document.createElement("button");
      stop.dataset.testid = "stop-button";
      stop.textContent = "Stop";
      document.body.appendChild(stop);
    }
  }, { text, generating });
}

async function runChildSmoke(context, completionMarker) {
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
    protocolVersion: 2,
    transactionId,
    childRequestDigest,
    bootstrapDigest,
    completionMarker
  };

  await setChildAssistant(page, "INTERMEDIATE AUDIT PROGRESS");
  await page.waitForTimeout(850);
  const pausedIntermediate = await page.evaluate(
    (payload) => window.__dispatchExtensionMessage(payload),
    message
  );
  assert.equal(pausedIntermediate.ok, true, JSON.stringify(pausedIntermediate));
  assert.equal(
    pausedIntermediate.reason,
    "child_generating",
    "stable intermediate output without a Stop button must remain pending after >700 ms"
  );

  await setChildAssistant(page, "INTERMEDIATE AUDIT PROGRESS\nTOOL WORK CONTINUES", { generating: true });
  const activeToolUse = await page.evaluate(
    (payload) => window.__dispatchExtensionMessage(payload),
    message
  );
  assert.equal(activeToolUse.ok, true, JSON.stringify(activeToolUse));
  assert.equal(activeToolUse.reason, "child_generating");

  // Reinstall the result listener to exercise extension/content-script reload recovery.
  await page.addScriptTag({ path: path.join(bridge, "spawn_result_content.js") });
  await setChildAssistant(page, `CHILD RESULT ALPHA\n${completionMarker}`);
  const result = await page.evaluate(
    (payload) => window.__dispatchExtensionMessage(payload),
    message
  );
  assert.equal(result.ok, true, JSON.stringify(result));
  assert.equal(result.reason, "child_result_ready");
  assert.equal(result.childConversationUrl, childUrl);
  assert.equal(result.assistantIdentity, "assistant-child-result");
  assert.equal(result.assistantText, "CHILD RESULT ALPHA");
  assert.doesNotMatch(result.assistantText, /LOCAL_AGENT_CF_CHILD_COMPLETE|USER SECRET|Copy/);

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
    const completionMarker = await runParentSmoke(context);
    await runChildSmoke(context, completionMarker);
    console.log("Conversation Fabric DOM smoke passed.");
  } finally {
    await context.close();
    await browser.close();
  }
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});