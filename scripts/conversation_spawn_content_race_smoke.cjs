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

function spawnIntent(tabId = null) {
  const bootstrapText = "LOCAL AGENT CHILD BOOTSTRAP\nrequest=content-race-smoke";
  return {
    schema_version: 1,
    transaction_id: `spawn-${sha256("content-race-transaction")}`,
    child_request_digest: `sha256:${sha256("content-race-request")}`,
    bootstrap_digest: `sha256:${sha256(bootstrapText)}`,
    bootstrap_text: bootstrapText,
    tab_id: tabId
  };
}

const fixture = `<!doctype html><html><body>
<form>
  <div id="prompt-textarea" class="ProseMirror" contenteditable="true" role="textbox"></div>
  <button id="composer-submit-button" type="submit">Send</button>
</form>
</body></html>`;

const wrapperSource = `"use strict";
const fs = require("node:fs");
const real = require(process.env.LOCAL_AGENT_PLAYWRIGHT_REAL_MODULE);
const fixture = fs.readFileSync(process.env.LOCAL_AGENT_CONTENT_RACE_FIXTURE, "utf8");
module.exports = {
  chromium: {
    async launchPersistentContext(profile, options) {
      const context = await real.chromium.launchPersistentContext(profile, {
        ...options,
        channel: "chromium"
      });
      let documentCount = 0;
      await context.route("https://**/*", async (route) => {
        const url = route.request().url();
        if (url.startsWith("https://chatgpt.com/") || url.startsWith("https://chat.openai.com/")) {
          if (route.request().resourceType() === "document") {
            documentCount += 1;
            if (documentCount >= 2) {
              await new Promise((resolve) => setTimeout(resolve, 900));
            }
          }
          return route.fulfill({ status: 200, contentType: "text/html", body: fixture });
        }
        return route.abort();
      });
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

function startActuator({ profile, wrapperPath, fixturePath }) {
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
      LOCAL_AGENT_CONTENT_RACE_FIXTURE: fixturePath
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
    return response.result;
  };

  const stop = async () => {
    if (child.exitCode !== null) return;
    const result = await request("shutdown");
    assert.equal(result.ok, true, JSON.stringify(result));
    child.stdin.end();
    const exitCode = await bounded(
      "actuator exit",
      new Promise((resolve) => child.once("exit", resolve)),
      10_000
    );
    assert.equal(exitCode, 0, stderr);
    lines.close();
  };

  return { child, request, stop, closeLines: () => lines.close(), stderr: () => stderr };
}

(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), "conversation-spawn-content-race-"));
  const profile = path.join(temp, "profile");
  const fixturePath = path.join(temp, "fixture.html");
  const wrapperPath = path.join(temp, "playwright-wrapper.cjs");
  await fs.writeFile(fixturePath, fixture, "utf8");
  await fs.writeFile(wrapperPath, wrapperSource, "utf8");

  let actuator = null;
  try {
    actuator = startActuator({ profile, wrapperPath, fixturePath });
    const ready = await actuator.request("wait_ready", { timeout_ms: 15_000 });
    assert.equal(ready.ok, true, JSON.stringify(ready));
    assert.equal(ready.reason, "chatgpt_ready");

    const created = await actuator.request("create", { intent: spawnIntent() });
    assert.equal(created.ok, true, JSON.stringify(created));
    assert.equal(created.reason, "tab_created", JSON.stringify(created));
    assert.ok(Number.isInteger(created.tabId));

    const durableIntent = spawnIntent(created.tabId);
    const startedAt = Date.now();
    const probe = await actuator.request("probe", { intent: durableIntent }, 10_000);
    const elapsed = Date.now() - startedAt;
    assert.equal(probe.ok, true, JSON.stringify(probe));
    assert.equal(probe.reason, "spawn_ready", JSON.stringify(probe));
    assert.ok(
      elapsed >= 500,
      `probe returned too quickly to exercise transient content unavailability: ${elapsed}ms`
    );

    await actuator.stop();
    actuator = null;
    console.log("Conversation spawn transient content race smoke passed.");
  } finally {
    if (actuator) {
      if (actuator.child.exitCode === null) actuator.child.kill("SIGTERM");
      actuator.closeLines();
    }
    await fs.rm(temp, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
