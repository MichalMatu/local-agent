"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const CHILD_URL = "https://chatgpt.com/c/22222222-2222-4222-8222-222222222222";

function normalizeConversationUrl(raw) {
  try {
    const url = new URL(String(raw || ""));
    if (url.protocol !== "https:") return "";
    if (!["chatgpt.com", "chat.openai.com"].includes(url.hostname)) return "";
    if (url.username || url.password || url.port || url.search || url.hash) return "";
    const match = url.pathname.match(/^\/c\/([A-Za-z0-9_-]{1,200})\/?$/);
    return match ? `https://chatgpt.com/c/${match[1]}` : "";
  } catch (_error) {
    return "";
  }
}

function authority() {
  return {
    schema_version: 1,
    child_request_id: "child-retire-001",
    child_request_digest: `sha256:${"1".repeat(64)}`,
    child_conversation_url: CHILD_URL,
    terminal_digest: `sha256:${"2".repeat(64)}`
  };
}

function loadWorker(initialTabs) {
  let tabs = initialTabs.map((tab) => ({ ...tab }));
  const removed = [];
  const context = {
    console,
    URL,
    normalizeConversationUrl,
    chrome: {
      tabs: {
        query: async () => tabs.map((tab) => ({ ...tab })),
        remove: async (tabId) => {
          removed.push(tabId);
          tabs = tabs.filter((tab) => tab.id !== tabId);
        }
      }
    }
  };
  vm.createContext(context);
  const source = fs.readFileSync(
    path.join(__dirname, "worker_retirement.js"),
    "utf8"
  );
  vm.runInContext(source, context, { filename: "worker_retirement.js" });
  return { context, removed, tabs: () => tabs.map((tab) => ({ ...tab })) };
}

(async () => {
  {
    const harness = loadWorker([
      { id: 10, url: "https://chatgpt.com/c/unrelated-child" },
      { id: 11, url: CHILD_URL },
      { id: 12, url: "https://example.com/" }
    ]);
    const receipt = await harness.context.closeRetiredConversationTab(authority());
    assert.equal(receipt.result, "closed");
    assert.equal(receipt.child_conversation_url, CHILD_URL);
    assert.deepEqual(harness.removed, [11]);
    assert.deepEqual(harness.tabs().map((tab) => tab.id), [10, 12]);
  }

  {
    const harness = loadWorker([{ id: 20, url: "https://chatgpt.com/c/other" }]);
    const receipt = await harness.context.closeRetiredConversationTab(authority());
    assert.equal(receipt.result, "already_closed");
    assert.deepEqual(harness.removed, []);
  }

  {
    const harness = loadWorker([
      { id: 30, url: CHILD_URL },
      { id: 31, url: CHILD_URL }
    ]);
    await assert.rejects(
      harness.context.closeRetiredConversationTab(authority()),
      /multiple tabs match/
    );
    assert.deepEqual(harness.removed, []);
  }

  {
    const harness = loadWorker([{ id: 40, url: CHILD_URL }]);
    const badDigest = authority();
    badDigest.terminal_digest = "not-a-digest";
    await assert.rejects(
      harness.context.closeRetiredConversationTab(badDigest),
      /terminal_digest is invalid/
    );
    assert.deepEqual(harness.removed, []);

    const nonCanonical = authority();
    nonCanonical.child_conversation_url = `${CHILD_URL}?unsafe=1`;
    await assert.rejects(
      harness.context.closeRetiredConversationTab(nonCanonical),
      /must be canonical/
    );
    assert.deepEqual(harness.removed, []);
  }

  console.log("conversation retirement tests passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
