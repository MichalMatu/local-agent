"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const readline = require("node:readline");
const { spawn } = require("node:child_process");

const root = path.resolve(__dirname, "..");
const playwrightModule = require.resolve(
  process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright"
);

function sha256(text) {
  return crypto.createHash("sha256").update(String(text), "utf8").digest("hex");
}

function intent(label, tabId = null) {
  const bootstrapText = [
    "LOCAL AGENT CHILD BOOTSTRAP",
    `request=${label}`,
    "Continue only the bounded synthetic live-slice smoke scope."
  ].join("\n");
  return {
    schema_version: 1,
    transaction_id: `spawn-${sha256(`transaction:${label}`)}`,
    child_request_digest: `sha256:${sha256(`request:${label}`)}`,
    bootstrap_digest: `sha256:${sha256(bootstrapText)}`,
    bootstrap_text: bootstrapText,
    tab_id: tabId
  };
}

const fixture = `<!doctype html><html><body>
<form id="composer-form">
  <div id="prompt-textarea" class="ProseMirror" contenteditable="true" role="textbox"></div>
  <button id="composer-submit-button" type="submit">Send</button>
</form>
<script>
window.submits = 0;
window.syntheticChildPath = (() => {
  const params = new URLSearchParams(location.hash.replace(/^#/, ""));
  const transaction = params.get("la-spawn") || "spawn-login";
  return "/c/live-slice-" + transaction.slice(-12);
})();
document.querySelector("form").onsubmit = (event) => {
  event.preventDefault();
  window.submits++;
  const input = document.querySelector("#prompt-textarea");
  const text = input.innerText || input.textContent || "";
  const message = document.createElement("div");
  message.dataset.messageAuthorRole = "user";
  message.textContent = text;
  document.body.append(message);
  input.textContent = "";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  history.pushState({}, "", window.syntheticChildPath);
};
</script></body></html>`;

const wrapperSource = `"use strict";
const fs = require("node:fs");
const real = require(process.env.LOCAL_AGENT_PLAYWRIGHT_REAL_MODULE);
const fixture = fs.readFileSync(process.env.LOCAL_AGENT_LIVE_SLICE_FIXTURE, "utf8");
module.exports = {
  chromium: {
    async launchPersistentContext(profile, options) {
      const context = await real.chromium.launchPersistentContext(profile, {
        ...options,
        channel: "chromium"
      });
      const fulfill = (route) => route.fulfill({
        status: 200,
        contentType: "text/html",
        body: fixture
      });
      await context.route("https://chatgpt.com/**", fulfill);
      await context.route("https://chat.openai.com/**", fulfill);
      return context;
    }
  }
};
`;

function bounded(label, promise, timeoutMs = 20_000) {
  let timer;
  return Promise.race([
    promise.finally(() => clearTimeout(timer)),
    new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error(`${label} exceeded ${timeoutMs} ms`)), timeoutMs);
    })
  ]);
}

(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), "conversation-live-slice-browser-"));
  const profile = path.join(temp, "profile");
  const fixturePath = path.join(temp, "fixture.html");
  const wrapperPath = path.join(temp, "playwright-wrapper.cjs");
  await fs.writeFile(fixturePath, fixture, "utf8");
  await fs.writeFile(wrapperPath, wrapperSource, "utf8");

  const child = spawn(process.execPath, [
    path.join(root, "scripts", "conversation_live_slice_browser.cjs"),
    "--profile",
    profile,
    "--extension",
    path.join(root, "chat_bridge"),
    "--headless"
  ], {
    cwd: root,
    env: {
      ...process.env,
      LOCAL_AGENT_PLAYWRIGHT_MODULE: wrapperPath,
      LOCAL_AGENT_PLAYWRIGHT_REAL_MODULE: playwrightModule,
      LOCAL_AGENT_LIVE_SLICE_FIXTURE: fixturePath
    },
    stdio: ["pipe", "pipe", "pipe"]
  });

  let stderr = "";
  child.stderr.setEncoding("utf8");
  child.stderr.on("data", (chunk) => { stderr += chunk; });

  const lines = readline.createInterface({ input: child.stdout, crlfDelay: Infinity });
  const waiting = [];
  lines.on("line", (line) => {
    const waiter = waiting.shift();
    if (!waiter) throw new Error(`unexpected actuator response: ${line}`);
    try {
      waiter.resolve(JSON.parse(line));
    } catch (error) {
      waiter.reject(error);
    }
  });

  let nextId = 0;
  const request = async (action, payload = {}, timeoutMs = 20_000) => {
    const id = ++nextId;
    const responsePromise = new Promise((resolve, reject) => waiting.push({ resolve, reject }));
    child.stdin.write(`${JSON.stringify({ id, action, payload })}\n`);
    const response = await bounded(`actuator ${action}`, responsePromise, timeoutMs);
    assert.equal(response.id, id, JSON.stringify(response));
    assert.equal(response.ok, true, response.error || JSON.stringify(response));
    assert.equal(typeof response.result, "object");
    return response.result;
  };

  try {
    const ready = await request("wait_ready", { timeout_ms: 15_000 }, 20_000);
    assert.equal(ready.ok, true, JSON.stringify(ready));
    assert.equal(ready.reason, "chatgpt_ready");

    const pending = intent("actuator-smoke");
    const created = await request("create", { intent: pending });
    assert.equal(created.ok, true, JSON.stringify(created));
    assert.equal(created.reason, "tab_created", JSON.stringify(created));
    assert.ok(Number.isInteger(created.tabId));

    const recovered = await request("recover_create", { intent: pending });
    assert.equal(recovered.ok, true, JSON.stringify(recovered));
    assert.equal(recovered.reason, "tab_recovered", JSON.stringify(recovered));
    assert.equal(recovered.tabId, created.tabId);

    const active = { ...pending, tab_id: created.tabId };
    let probe = null;
    const probeDeadline = Date.now() + 10_000;
    do {
      probe = await request("probe", { intent: active });
      if (probe.ok) break;
      await new Promise((resolve) => setTimeout(resolve, 100));
    } while (Date.now() < probeDeadline);
    assert.equal(probe?.ok, true, JSON.stringify(probe));
    assert.equal(probe.reason, "spawn_ready", JSON.stringify(probe));

    const submitted = await request("submit", { intent: active });
    assert.equal(submitted.ok, true, JSON.stringify(submitted));
    assert.equal(submitted.reason, "identity_discovered", JSON.stringify(submitted));
    assert.match(
      submitted.childConversationUrl,
      /^https:\/\/chatgpt\.com\/c\/live-slice-[a-f0-9]{12}$/
    );

    const shutdown = await request("shutdown");
    assert.equal(shutdown.ok, true, JSON.stringify(shutdown));
    assert.equal(shutdown.reason, "shutdown");
    child.stdin.end();
    const exitCode = await bounded(
      "actuator exit",
      new Promise((resolve) => child.once("exit", resolve)),
      10_000
    );
    assert.equal(exitCode, 0, stderr);
    console.log("Conversation live slice browser actuator smoke passed.");
  } finally {
    if (child.exitCode === null) child.kill("SIGTERM");
    lines.close();
    await fs.rm(temp, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
