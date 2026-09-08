"use strict";

const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const h = createHarness({
    contentScriptProbe: async ({ tabId, injectedScripts }) => {
      if (tabId === 22) {
        return {
          ok: true,
          reason: "ready",
          protocolVersion: h.CONTENT_PROTOCOL_VERSION,
          assistantIdentity: "tracker-current"
        };
      }
      const refreshed = injectedScripts.some((entry) =>
        entry.target?.tabId === tabId && Array.isArray(entry.files) && entry.files.includes("content.js")
      );
      return {
        ok: true,
        reason: "ready",
        protocolVersion: refreshed ? h.CONTENT_PROTOCOL_VERSION : h.CONTENT_PROTOCOL_VERSION - 1,
        assistantIdentity: refreshed ? "matrix-refreshed" : "matrix-stale"
      };
    }
  });

  // Let the worker's automatic activation refresh finish while no chats are configured,
  // then build an explicit lifecycle fixture for the startup event below.
  await new Promise((resolve) => setTimeout(resolve, 0));

  let response = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      label: "Stale open chat",
      agentBinding: h.MATRIX_BINDING,
      preferredTabId: 11,
      enabled: false,
      assistantBaseline: "matrix-stale"
    }
  });
  assert.equal(response.ok, true);
  const staleId = response.conversation.id;

  response = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/b",
      label: "Current open chat",
      agentBinding: h.TRACKER_BINDING,
      preferredTabId: 22,
      enabled: false,
      assistantBaseline: "tracker-current"
    }
  });
  assert.equal(response.ok, true);
  const currentId = response.conversation.id;

  const staleBefore = JSON.parse(JSON.stringify(h.storage.bridgeState.conversations[staleId]));
  const currentBefore = JSON.parse(JSON.stringify(h.storage.bridgeState.conversations[currentId]));
  h.injectedScripts.length = 0;
  h.tabMessages.length = 0;
  h.sentMessages.length = 0;

  const startupResult = await h.startup();
  assert.deepEqual(startupResult, { checked: 2, ready: 1, refreshed: 1, failed: 0 });

  const staleContentInjection = h.injectedScripts.filter((entry) =>
    entry.target?.tabId === 11 && Array.isArray(entry.files) && entry.files.includes("content.js")
  );
  const currentContentInjection = h.injectedScripts.filter((entry) =>
    entry.target?.tabId === 22 && Array.isArray(entry.files) && entry.files.includes("content.js")
  );
  assert.equal(staleContentInjection.length, 1, "stale protocol tab must be refreshed exactly once");
  assert.equal(currentContentInjection.length, 0, "current protocol tab must only be probed");
  assert.equal(h.sentMessages.length, 0, "startup content refresh must never send a wake or feedback prompt");

  assert.deepEqual(h.storage.bridgeState.conversations[staleId], staleBefore,
    "startup refresh must not mutate stale chat binding/schedule state");
  assert.deepEqual(h.storage.bridgeState.conversations[currentId], currentBefore,
    "startup refresh must not mutate current chat binding/schedule state");

  const staleProbes = h.tabMessages.filter((entry) =>
    entry.tabId === 11 && entry.message?.type === "bridge:capabilities"
  );
  assert.ok(staleProbes.length >= 2, "stale tab must be probed before and after reinjection");
  assert.ok(staleProbes.every((entry) => entry.message.protocolVersion === h.CONTENT_PROTOCOL_VERSION));

  console.log("Chat Bridge worker startup refreshes only stale configured tabs without sending a wake.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
