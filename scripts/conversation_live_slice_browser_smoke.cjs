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
const expectedExecutable = process.env.LOCAL_AGENT_EXPECTED_CHROME_EXECUTABLE || "";
const authenticated = process.env.LOCAL_AGENT_LIVE_SLICE_AUTHENTICATED !== "0";
const profileControl = process.env.LOCAL_AGENT_LIVE_SLICE_PROFILE_CONTROL === "1";
const realChromeExecutable = process.env.LOCAL_AGENT_LIVE_SLICE_REAL_CHROME_EXECUTABLE || "";
const composerDelayMs = Number(process.env.LOCAL_AGENT_LIVE_SLICE_COMPOSER_DELAY_MS || "0");
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
      if (expectedExecutable) {
        if (options.executablePath !== expectedExecutable) {
          throw new Error("live-slice browser must pass the explicit Chrome executable to Playwright");
        }
      } else if (Object.prototype.hasOwnProperty.call(options, "executablePath")) {
        throw new Error("live-slice browser must preserve the default Playwright executable when no override is configured");
      }
      const launchOptions = { ...options };
      delete launchOptions.executablePath;
      if (realChromeExecutable) launchOptions.executablePath = realChromeExecutable;
      else launchOptions.channel = "chromium";
      const context = await real.chromium.launchPersistentContext(profile, launchOptions);
      const realServiceWorkers = context.serviceWorkers.bind(context);
      const realWaitForEvent = context.waitForEvent.bind(context);
      let workerProbeStartedAt = null;
      Object.defineProperty(context, "serviceWorkers", {
        configurable: true,
        value: () => {
          const workers = realServiceWorkers();
          if (workerProbeStartedAt === null) workerProbeStartedAt = Date.now();
          if (Date.now() - workerProbeStartedAt < 750) {
            return workers.filter((worker) => !worker.url().startsWith("chrome-extension://"));
          }
          return workers;
        }
      });
      Object.defineProperty(context, "waitForEvent", {
        configurable: true,
        value: (event, eventOptions) => {
          if (event === "serviceworker") {
            return new Promise((resolve) => setTimeout(() => resolve(null), 750));
          }
          return realWaitForEvent(event, eventOptions);
        }
      });
      await context.setOffline(true);
      await context.route("https://**/*", (route) => {
        const url = route.request().url();
        if (url === "https://chatgpt.com/api/auth/session") {
          return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(authenticated ? { user: { id: "synthetic-user" } } : { WARNING_BANNER: "guest" }) });
        }
        if (url.startsWith("https://chatgpt.com/") || url.startsWith("https://chat.openai.com/")) {
          const renderedFixture = profileControl
            ? fixture.replace("</body>", '<button data-testid="accounts-profile-button">Account</button></body>')
            : fixture;
          const delayedFixture = composerDelayMs > 0
            ? renderedFixture.replace(
                '<div id="prompt-textarea" class="ProseMirror" contenteditable="true" role="textbox"></div>',
                '<div id="delayed-composer-anchor"></div><script>setTimeout(function(){const anchor=document.getElementById("delayed-composer-anchor");if(!anchor)return;const composer=document.createElement("div");composer.id="prompt-textarea";composer.className="ProseMirror";composer.contentEditable="true";composer.setAttribute("role","textbox");anchor.replaceWith(composer);},' + composerDelayMs + ');</script>'
              )
            : renderedFixture;
          return route.fulfill({ status: 200, contentType: "text/html", body: delayedFixture });
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

function startActuator({ profile, wrapperPath, fixturePath, chromeExecutable = null, authenticated = true, profileControl = false, composerDelayMs = 0 }) {
  const env = {
    ...process.env,
    LOCAL_AGENT_PLAYWRIGHT_MODULE: wrapperPath,
    LOCAL_AGENT_PLAYWRIGHT_REAL_MODULE: playwrightModule,
    LOCAL_AGENT_LIVE_SLICE_FIXTURE: fixturePath,
    LOCAL_AGENT_LIVE_SLICE_AUTHENTICATED: authenticated ? "1" : "0",
    LOCAL_AGENT_LIVE_SLICE_PROFILE_CONTROL: profileControl ? "1" : "0",
    LOCAL_AGENT_LIVE_SLICE_COMPOSER_DELAY_MS: String(composerDelayMs)
  };
  delete env.LOCAL_AGENT_CHROME_EXECUTABLE;
  delete env.LOCAL_AGENT_EXPECTED_CHROME_EXECUTABLE;
  if (chromeExecutable) {
    env.LOCAL_AGENT_CHROME_EXECUTABLE = chromeExecutable;
    env.LOCAL_AGENT_EXPECTED_CHROME_EXECUTABLE = chromeExecutable;
  }

  const child = spawn(process.execPath, [
    path.join(root, "scripts", "conversation_live_slice_browser.cjs"),
    "--profile",
    profile,
    "--extension",
    path.join(root, "chat_bridge"),
    "--headless"
  ], {
    cwd: root,
    env,
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
  const fakeChromePath = path.join(temp, "fake-system-chrome");
  await fs.writeFile(fixturePath, fixture, "utf8");
  await fs.writeFile(wrapperPath, wrapperSource, "utf8");
  await fs.writeFile(fakeChromePath, "#!/bin/sh\nexit 1\n", "utf8");
  await fs.chmod(fakeChromePath, 0o755);
  const staleWorkerSentinel = path.join(profile, "Default", "Service Worker", "stale-worker-sentinel");
  await fs.mkdir(path.dirname(staleWorkerSentinel), { recursive: true });
  await fs.writeFile(staleWorkerSentinel, "stale\n", "utf8");

  let guest = null;
  let uiAuthenticated = null;
  let slowComposer = null;
  let first = null;
  let second = null;
  try {
    const pending = intent("actuator-smoke");

    guest = startActuator({ profile: path.join(temp, "guest-profile"), wrapperPath, fixturePath, chromeExecutable: fakeChromePath, authenticated: false });
    const guestReady = await guest.request("wait_ready", { timeout_ms: 1200 }, 15_000);
    assert.equal(guestReady.ok, false, JSON.stringify(guestReady));
    assert.equal(guestReady.reason, "chatgpt_login_timeout", JSON.stringify(guestReady));
    assert.equal(guestReady.url, "https://chatgpt.com/", JSON.stringify(guestReady));
    await guest.stop();
    guest = null;

    uiAuthenticated = startActuator({
      profile: path.join(temp, "ui-auth-profile"),
      wrapperPath,
      fixturePath,
      chromeExecutable: fakeChromePath,
      authenticated: false,
      profileControl: true
    });
    const uiReady = await uiAuthenticated.request("wait_ready", { timeout_ms: 3000 }, 15_000);
    assert.equal(uiReady.ok, true, JSON.stringify(uiReady));
    assert.equal(uiReady.reason, "chatgpt_ready", JSON.stringify(uiReady));
    await uiAuthenticated.stop();
    uiAuthenticated = null;

    slowComposer = startActuator({
      profile: path.join(temp, "slow-composer-profile"),
      wrapperPath,
      fixturePath,
      chromeExecutable: fakeChromePath,
      composerDelayMs: 6500
    });
    const slowReady = await slowComposer.request("wait_ready", { timeout_ms: 15_000 }, 25_000);
    assert.equal(slowReady.ok, true, JSON.stringify(slowReady));
    const slowPending = intent("slow-composer");
    const slowCreated = await slowComposer.request("create", { intent: slowPending });
    assert.equal(slowCreated.ok, true, JSON.stringify(slowCreated));
    const slowDurable = intent("slow-composer", slowCreated.tabId);
    const slowRecovered = await recoverMarker(slowComposer.request, slowDurable);
    assert.equal(slowRecovered?.ok, true, JSON.stringify(slowRecovered));
    const slowProbeStarted = Date.now();
    const slowProbe = await slowComposer.request("probe", { intent: slowDurable }, 35_000);
    assert.equal(slowProbe.ok, true, JSON.stringify(slowProbe));
    assert.equal(slowProbe.reason, "spawn_ready", JSON.stringify(slowProbe));
    assert.ok(Date.now() - slowProbeStarted >= 6000, "probe must wait for delayed composer stabilization");
    await slowComposer.stop();
    slowComposer = null;

    first = startActuator({
      profile,
      wrapperPath,
      fixturePath,
      chromeExecutable: fakeChromePath
    });
    const ready = await first.request("wait_ready", { timeout_ms: 15_000 }, 20_000);
    assert.equal(ready.ok, true, JSON.stringify(ready));
    assert.equal(ready.reason, "chatgpt_ready");

    const workerWaitStarted = Date.now();
    const created = await first.request("create", { intent: pending });
    assert.ok(
      Date.now() - workerWaitStarted >= 650,
      "create must tolerate extension-worker startup beyond the old 300ms race"
    );
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

    // Persistent Chromium does not guarantee whether the marker tab survives a
    // controlled context restart. Both outcomes are valid: strict recovery may
    // find the existing tab, or the runner may authorize one bounded pre-submit
    // reattach while durable state still proves that no submit has happened.
    await first.stop();
    first = null;

    // The second launch intentionally omits LOCAL_AGENT_CHROME_EXECUTABLE so the
    // smoke also proves that the default Playwright executable path is unchanged.
    second = startActuator({ profile, wrapperPath, fixturePath });
    const readyAfterRestart = await second.request(
      "wait_ready",
      { timeout_ms: 15_000 },
      20_000
    );
    assert.equal(readyAfterRestart.ok, true, JSON.stringify(readyAfterRestart));
    assert.equal(readyAfterRestart.reason, "chatgpt_ready");

    const strictAfterRestart = await recoverMarker(second.request, durableIntent, 1000);
    assert.ok(strictAfterRestart && typeof strictAfterRestart.ok === "boolean");
    if (!strictAfterRestart.ok) {
      assert.equal(strictAfterRestart.reason, "spawn_create_recovery_missing");
    } else {
      assert.equal(strictAfterRestart.reason, "tab_recovered");
      assert.ok(Number.isInteger(strictAfterRestart.tabId));
    }

    const reattached = await second.request("reattach_pre_submit", { intent: durableIntent });
    assert.equal(reattached.ok, true, JSON.stringify(reattached));
    assert.ok(["tab_recovered", "tab_reattached"].includes(reattached.reason), JSON.stringify(reattached));
    assert.ok(Number.isInteger(reattached.tabId));
    if (strictAfterRestart.ok) {
      assert.equal(reattached.reason, "tab_recovered");
      assert.equal(reattached.tabId, strictAfterRestart.tabId);
    } else {
      assert.equal(reattached.reason, "tab_reattached");
    }

    const recoveredReattached = await recoverMarker(
      second.request,
      { ...durableIntent, tab_id: reattached.tabId }
    );
    assert.equal(recoveredReattached?.ok, true, JSON.stringify(recoveredReattached));
    assert.equal(recoveredReattached.reason, "tab_recovered", JSON.stringify(recoveredReattached));
    assert.equal(recoveredReattached.tabId, reattached.tabId);

    await second.stop();
    second = null;
    console.log("Conversation live slice bounded restart recovery smoke passed.");
  } finally {
    for (const actuator of [guest, uiAuthenticated, slowComposer, first, second]) {
      if (!actuator) continue;
      if (actuator.child.exitCode === null) actuator.child.kill("SIGTERM");
      actuator.closeLines();
    }
    await fs.rm(temp, { recursive: true, force: true, maxRetries: 8, retryDelay: 100 });
  }
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
