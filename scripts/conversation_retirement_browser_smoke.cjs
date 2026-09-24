"use strict";

// Offline browser proof for terminal-gated child retirement. The script uses a
// disposable Chromium profile and serves only a local synthetic ChatGPT fixture.
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright");

const root = path.resolve(__dirname, "..");
const CHILD_URL = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222";
const OTHER_URL = "https://chatgpt.com/c/33333333-3333-4333-8333-333333333333";

function authority(url = CHILD_URL) {
  return {
    schema_version: 1,
    child_request_id: "child-retire-browser-001",
    child_request_digest: `sha256:${"1".repeat(64)}`,
    child_conversation_url: url,
    terminal_digest: `sha256:${"2".repeat(64)}`
  };
}

async function poll(label, predicate, timeoutMs = 8_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const value = await predicate();
    if (value) return value;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error(`${label} exceeded ${timeoutMs} ms`);
}

(async () => {
  const profile = await fs.mkdtemp(path.join(os.tmpdir(), "conversation-retirement-browser-"));
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
      if (route.request().url().startsWith("https://chatgpt.com/")) {
        return route.fulfill({
          contentType: "text/html",
          body: "<!doctype html><html><body><main>synthetic conversation</main></body></html>"
        });
      }
      return route.abort();
    });

    const worker = context.serviceWorkers()[0] || await context.waitForEvent("serviceworker");
    const closeWithAuthority = (value) => worker.evaluate(
      (retirementAuthority) => closeRetiredConversationTab(retirementAuthority),
      value
    );

    const child = await context.newPage();
    const unrelated = await context.newPage();
    await child.goto(CHILD_URL);
    await unrelated.goto(OTHER_URL);

    const receipt = await closeWithAuthority(authority());
    assert.equal(receipt.result, "closed", JSON.stringify(receipt));
    assert.equal(receipt.child_conversation_url, CHILD_URL);
    await poll("registered child tab close", () => child.isClosed());
    assert.equal(unrelated.isClosed(), false, "unrelated conversation tab must remain open");
    console.log("PASS: retirement authority closes only the exact registered child tab");

    const recovered = await closeWithAuthority(authority());
    assert.equal(recovered.result, "already_closed", JSON.stringify(recovered));
    assert.equal(unrelated.isClosed(), false);
    console.log("PASS: repeated retirement after a lost close receipt reconciles as already_closed");

    const duplicateA = await context.newPage();
    const duplicateB = await context.newPage();
    await duplicateA.goto(CHILD_URL);
    await duplicateB.goto(CHILD_URL);
    await assert.rejects(
      closeWithAuthority(authority()),
      /multiple tabs match the registered child conversation URL/
    );
    assert.equal(duplicateA.isClosed(), false);
    assert.equal(duplicateB.isClosed(), false);
    console.log("PASS: duplicate matching child tabs fail closed without closing either tab");

    const invalid = authority(`${CHILD_URL}?unsafe=1`);
    await assert.rejects(closeWithAuthority(invalid), /must be canonical/);
    assert.equal(unrelated.isClosed(), false);
    console.log("PASS: non-canonical retirement authority fails before browser side effects");
  } finally {
    if (context) await context.close().catch(() => null);
    await fs.rm(profile, { recursive: true, force: true });
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
