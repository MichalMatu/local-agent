"use strict";

const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

(async () => {
  const h = createHarness({
    contentScriptProbe: async ({ tabId, injectedScripts }) => {
      if (tabId !== 11) {
        return {
          ok: true,
          reason: "ready",
          protocolVersion: h.CONTENT_PROTOCOL_VERSION,
          assistantIdentity: tabId === 22 ? "tracker-current" : "infra-current"
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
    },
    exhaustionGuardProbe: async ({ tabId, injectedScripts }) => {
      if (tabId !== 22) {
        return { ok: true, reason: "ready", guardVersion: h.EXHAUSTION_GUARD_VERSION };
      }
      const refreshed = injectedScripts.some((entry) =>
        entry.target?.tabId === tabId && Array.isArray(entry.files) && entry.files.includes("exhaustion_guard.js")
      );
      return {
        ok: true,
        reason: "ready",
        guardVersion: refreshed ? h.EXHAUSTION_GUARD_VERSION : h.EXHAUSTION_GUARD_VERSION - 1
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
      label: "Stale content chat",
      agentBinding: h.MATRIX_BINDING,
      preferredTabId: 11,
      enabled: false,
      assistantBaseline: "matrix-stale"
    }
  });
  assert.equal(response.ok, true);
  const staleContentId = response.conversation.id;

  response = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/b",
      label: "Stale guard chat",
      agentBinding: h.TRACKER_BINDING,
      preferredTabId: 22,
      enabled: false,
      assistantBaseline: "tracker-current"
    }
  });
  assert.equal(response.ok, true);
  const staleGuardId = response.conversation.id;

  response = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/infra",
      label: "Current chat",
      agentBinding: h.LOCAL_AGENT_BINDING,
      preferredTabId: 33,
      enabled: false,
      assistantBaseline: "infra-current"
    }
  });
  assert.equal(response.ok, true);
  const currentId = response.conversation.id;

  const before = Object.fromEntries(
    [staleContentId, staleGuardId, currentId].map((id) => [
      id,
      JSON.parse(JSON.stringify(h.storage.bridgeState.conversations[id]))
    ])
  );
  h.injectedScripts.length = 0;
  h.tabMessages.length = 0;
  h.sentMessages.length = 0;

  const startupResult = await h.startup();
  assert.deepEqual(
    JSON.parse(JSON.stringify(startupResult)),
    { checked: 3, ready: 1, refreshed: 2, failed: 0 }
  );

  const staleContentInjection = h.injectedScripts.filter((entry) =>
    entry.target?.tabId === 11 && Array.isArray(entry.files) && entry.files.includes("content.js")
  );
  const staleGuardContentInjection = h.injectedScripts.filter((entry) =>
    entry.target?.tabId === 22 && Array.isArray(entry.files) && entry.files.includes("content.js")
  );
  const staleGuardInjection = h.injectedScripts.filter((entry) =>
    entry.target?.tabId === 22 && Array.isArray(entry.files) && entry.files.includes("exhaustion_guard.js")
  );
  const currentInjection = h.injectedScripts.filter((entry) => entry.target?.tabId === 33);
  assert.equal(staleContentInjection.length, 1, "stale content protocol must be refreshed exactly once");
  assert.equal(staleGuardContentInjection.length, 0, "current content must not be reinjected for a stale guard");
  assert.equal(staleGuardInjection.length, 1, "stale assistant guard must be refreshed exactly once");
  assert.equal(currentInjection.length, 0, "fully current tab must only be probed");
  assert.equal(h.sentMessages.length, 0, "startup refresh must never send a wake or feedback prompt");

  for (const id of [staleContentId, staleGuardId, currentId]) {
    assert.deepEqual(
      h.storage.bridgeState.conversations[id],
      before[id],
      "startup refresh must not mutate chat binding/schedule state"
    );
  }

  const staleContentProbes = h.tabMessages.filter((entry) =>
    entry.tabId === 11 && entry.message?.type === "bridge:capabilities"
  );
  assert.ok(staleContentProbes.length >= 2, "stale content tab must be probed before and after reinjection");
  assert.ok(staleContentProbes.every((entry) => entry.message.protocolVersion === h.CONTENT_PROTOCOL_VERSION));

  const staleGuardProbes = h.tabMessages.filter((entry) =>
    entry.tabId === 22 && entry.message?.type === "bridge:exhaustion-capabilities"
  );
  assert.ok(staleGuardProbes.length >= 2, "stale guard must be probed before and after reinjection");
  assert.ok(staleGuardProbes.every((entry) => entry.message.guardVersion === h.EXHAUSTION_GUARD_VERSION));

  console.log("Chat Bridge startup refreshes stale content and stale assistant guards without sending a wake.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
