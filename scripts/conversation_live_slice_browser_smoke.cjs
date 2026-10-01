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
</body></html>`;

const wrapperSource = `"use strict";
const fs = require("node:fs");
const path = require("node:path");
const real = require(process.env.LOCAL_AGENT_PLAYWRIGHT_REAL_MODULE);
const fixture = fs.readFileSync(process.env.LOCAL_AGENT_LIVE_SLICE_FIXTURE, "utf8");
module.exports = {
  chromium: {
    async launchPersistentContext(profile, options) {
      const staleWorkerSentinel = path.join(profile, "Default", "Service Worker", "stale-worker-sentinel");
      if (fs.existsSync(staleWorkerSentinel)) {
        throw new Error("live-slice browser must clear stale DEV service-worker state before launch");
      }
      if (!Array.isArray(options.args) || !options.args.includes("--restore-last-session")) {
        throw new Error("live-slice browser must restore the isolated persistent session");
      }
      const context = await real.chromium.launchPersistentContext(profile, {
        ...options,
        channel: "chromium"
      });
      await context.setOffline(true);
      await context.route("https://**/*", (route) => {
        const url = route.request().url();
        if (url.startsWith("https://chatgpt.com/") || url.startsWith("https://chat.openai.com/")) {
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

  const stop = async () => {
    if (child.exitCode !== null) {
      lines.close();
      return;
    }
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
    lines.close();
  };

  return {
    child,
    request,
    stop,
    stderr: () => stderr,
    closeLines: () => lines.close()
  };
}

async function recoverMarker(request, pending, timeoutMs = 3000) {
  let recovered = null;
  const recoveryDeadline = Date.now() + timeoutMs;
  do {
    recovered = await request("recover_create", { intent: pending });
    if (recovered.ok || recovered.reason !== "spawn_create_recovery_missing") break;
    await new Promise((resolve) => setTimeout(resolve, 50));
  } while (Date.now() < recoveryDeadline);
  return recovered;
}

(async () => {
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), "conversation-live-slice-browser-"));
  const profile = path.join(temp, "profile");
  const fixturePath = path.join(temp, "fixture.html");
  const wrapperPath = path.join(temp, "playwright-wrapper.cjs");
  await fs.writeFile(fixturePath, fixture, "utf8");
  await fs.writeFile(wrapperPath, wrapperSource, "utf8");
  const staleWorkerSentinel = path.join(profile, "Default", "Service Worker", "stale-worker-sentinel");
  await fs.mkdir(path.dirname(staleWorkerSentinel), { recursive: true });
  await fs.writeFile(staleWorkerSentinel, "stale\n", "utf8");

  let first = null;
  let second = null;
  try {
    const pending = intent("actuator-smoke");

    first = startActuator({ profile, wrapperPath, fixturePath });
    const ready = await first.request("wait_ready", { timeout_ms: 15_000 }, 20_000);
    assert.equal(ready.ok, true, JSON.stringify(ready));
    assert.equal(ready.reason, "chatgpt_ready");

    const created = await first.request("create", { intent: pending });
    assert.equal(created.ok, true, JSON.stringify(created));
    assert.equal(created.reason, "tab_created", JSON.stringify(created));
    assert.ok(Number.isInteger(created.tabId));
    const durableIntent = intent("actuator-smoke", created.tabId);

    // tabs.create can acknowledge before the new tab exposes its marker through
    // tabs.query(url/pendingUrl), so first prove same-process lost-ACK recovery.
    const recovered = await recoverMarker(first.request, durableIntent);
    assert.equal(recovered?.ok, true, JSON.stringify(recovered));
    assert.equal(recovered.reason, "tab_recovered", JSON.stringify(recovered));
    assert.equal(recovered.tabId, created.tabId);

    // Controlled persistent-context shutdown does not preserve the marker tab.
    // Strict lost-ACK recovery must remain fail-closed after restart. The runner
    // may then authorize exactly one separate pre-submit transport reattach while
    // the durable transaction is still bootstrap_ready and no submit has happened.
    await first.stop();
    first = null;

    second = startActuator({ profile, wrapperPath, fixturePath });
    const readyAfterRestart = await second.request(
      "wait_ready",
      { timeout_ms: 15_000 },
      20_000
    );
    assert.equal(readyAfterRestart.ok, true, JSON.stringify(readyAfterRestart));
    assert.equal(readyAfterRestart.reason, "chatgpt_ready");

    const strictAfterRestart = await recoverMarker(second.request, durableIntent, 1000);
    assert.equal(strictAfterRestart?.ok, false, JSON.stringify(strictAfterRestart));
    assert.equal(strictAfterRestart.reason, "spawn_create_recovery_missing");

    const reattached = await second.request("reattach_pre_submit", { intent: durableIntent });
    assert.equal(reattached.ok, true, JSON.stringify(reattached));
    assert.equal(reattached.reason, "tab_reattached", JSON.stringify(reattached));
    assert.ok(Number.isInteger(reattached.tabId));

    const recoveredReattached = await recoverMarker(
      second.request,
      { ...durableIntent, tab_id: reattached.tabId }
    );
    assert.equal(recoveredReattached?.ok, true, JSON.stringify(recoveredReattached));
    assert.equal(recoveredReattached.reason, "tab_recovered", JSON.stringify(recoveredReattached));
    assert.equal(recoveredReattached.tabId, reattached.tabId);

    await second.stop();
    second = null;
    console.log("Conversation live slice bounded pre-submit reattach smoke passed.");
  } finally {
    for (const actuator of [first, second]) {
      if (!actuator) continue;
      if (actuator.child.exitCode === null) actuator.child.kill("SIGTERM");
      actuator.closeLines();
    }
    await fs.rm(temp, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
