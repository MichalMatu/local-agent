"use strict";

const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");
const { CONTENT_PROTOCOL_VERSION } = require("./control_protocol.js");

(async () => {
  let staleProbeCount = 0;
  const h = createHarness({
    contentScriptProbe({ injectedScripts }) {
      const resetInjected = injectedScripts.some((entry) => entry.hasFunction);
      const fullBundleInjected = injectedScripts.some((entry) =>
        Array.isArray(entry.files) &&
        entry.files.includes("content.js") &&
        entry.files.includes("exhaustion_guard.js")
      );
      if (!resetInjected || !fullBundleInjected) {
        staleProbeCount += 1;
        throw new Error("Receiving end does not exist");
      }
      return {
        ok: true,
        reason: "ready",
        protocolVersion: CONTENT_PROTOCOL_VERSION,
        assistantIdentity: "fresh-assistant"
      };
    }
  });

  const added = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url: "https://chatgpt.com/c/a",
      label: "Stale content refresh",
      enabled: false,
      preferredTabId: 11,
      agentBinding: h.MATRIX_BINDING
    }
  });
  assert.equal(added.ok, true, added.error);

  const delivery = await h.sendRuntimeMessage({
    type: "bridge:run-now",
    conversationId: added.conversation.id
  });

  assert.equal(delivery.ok, true, delivery.reason);
  assert.equal(delivery.reason, "sent");
  assert.ok(staleProbeCount >= 1);
  assert.equal(h.sentMessages.length, 1);

  const resetIndex = h.injectedScripts.findIndex((entry) => entry.hasFunction);
  const fullBundleIndex = h.injectedScripts.findIndex((entry) =>
    Array.isArray(entry.files) &&
    entry.files.includes("control_protocol.js") &&
    entry.files.includes("content_retry.js") &&
    entry.files.includes("content.js") &&
    entry.files.includes("dom_contract.js") &&
    entry.files.includes("exhaustion_guard.js")
  );
  assert.ok(resetIndex >= 0, "stale page state must be explicitly reset");
  assert.ok(fullBundleIndex > resetIndex, "the full content bundle must be injected after reset");

  console.log("Chat Bridge stale content auto-refresh test passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
