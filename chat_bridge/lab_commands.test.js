"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const { createHarness } = require("./worker_test_harness.js");

function fingerprint(value) {
  return protocol.fnv1a32(value);
}

(async () => {
  // Future-proof parser catalog keeps assistant and operator privilege domains separate.
  for (const [marker, command] of [
    ["[LAB:HELP]", "help"],
    ["[LAB:CAPABILITIES]", "capabilities"],
    ["[LAB:STATUS]", "status"],
    ["[LAB:DEBUG]", "debug"],
    ["[LAB:SETTINGS]", "settings"],
    ["[LAB:CHATS]", "chats"],
    ["[LAB:CHAT=chat-deadbeef]", "chat"]
  ]) {
    const parsed = protocol.parseAssistantControl(marker);
    assert.equal(parsed?.action, "inspect", marker);
    assert.equal(parsed?.command, command, marker);
  }
  assert.equal(protocol.parseAssistantControl("[LAB:RELOAD=CONTENT]")?.command, "reload_content");
  assert.equal(protocol.parseAssistantControl("[LAB:RESTART=WORKER]")?.command, "reload_bridge");
  assert.equal(protocol.parseAssistantControl("[LAB:OP:ADD=tracker]"), null, "assistant parser must not accept operator mutation");
  assert.equal(protocol.parseOperatorControl("[LAB:PAUSE]"), null, "operator parser must not accept assistant controls");
  assert.deepEqual(protocol.parseOperatorControl("[LAB:OP:ADD=tracker]"), {
    action: "operator", command: "add", repositoryId: "tracker", marker: "[LAB:OP:ADD=tracker]"
  });
  assert.equal(protocol.parseOperatorControl("[LAB:OP:INTERVAL=AUTO]")?.mode, "auto");
  assert.equal(protocol.parseOperatorControl("[LAB:OP:INTERVAL=10m]")?.minutes, 10);
  assert.ok(protocol.COMMAND_CATALOG.some((item) => item.marker === "DEBUG" && item.privilege === "assistant"));
  assert.ok(protocol.COMMAND_CATALOG.some((item) => item.marker === "OP:ADD=<repository-id>" && item.privilege === "operator"));

  // DEBUG works even before a chat is configured, so Bridge can diagnose its own onboarding path.
  {
    const h = createHarness();
    const response = await h.sendRuntimeMessage({
      type: "bridge:assistant-control",
      conversationUrl: "https://chatgpt.com/c/a",
      fingerprint: fingerprint("debug-unbound"),
      assistantIdentity: "assistant-debug-1",
      contentProtocolVersion: protocol.CONTENT_PROTOCOL_VERSION,
      control: { marker: "[LAB:DEBUG]" }
    }, { tab: { id: 11, url: "https://chatgpt.com/c/a" } });
    assert.equal(response.ok, true);
    assert.equal(response.reason, "inspection_ready");
    assert.match(response.feedbackPrompt, /\[LA_BRIDGE_FEEDBACK\]/);
    assert.match(response.feedbackPrompt, /"configured": false/);
    assert.match(response.feedbackPrompt, /"expectedContentProtocol": 4/);
    assert.match(response.feedbackPrompt, /"reportedContentProtocol": 4/);
  }

  // User-authored OP controls can add/configure/remove exactly the current chat and dedupe persistently.
  {
    const h = createHarness();
    const url = "https://chatgpt.com/c/a";
    const sender = { tab: { id: 11, url } };
    const addFingerprint = fingerprint("operator-add-tracker");
    let response = await h.sendRuntimeMessage({
      type: "bridge:operator-control",
      conversationUrl: url,
      fingerprint: addFingerprint,
      userIdentity: "user-add-1",
      chatLabel: "Project A",
      assistantBaseline: "assistant-before-add",
      control: { marker: "[LAB:OP:ADD=tracker]" }
    }, sender);
    assert.equal(response.ok, true);
    assert.equal(response.reason, "operator_add");
    const chatId = protocol.conversationId(url);
    assert.equal(h.storage.bridgeState.conversations[chatId].repositoryId, "tracker");
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, false);
    assert.equal(h.storage.bridgeState.conversations[chatId].assistantBaseline, "assistant-before-add");

    response = await h.sendRuntimeMessage({
      type: "bridge:operator-control",
      conversationUrl: url,
      fingerprint: addFingerprint,
      userIdentity: "user-add-1",
      control: { marker: "[LAB:OP:ADD=tracker]" }
    }, sender);
    assert.equal(response.duplicate, true);

    response = await h.sendRuntimeMessage({
      type: "bridge:operator-control",
      conversationUrl: url,
      fingerprint: fingerprint("operator-enable"),
      userIdentity: "user-enable-1",
      control: { marker: "[LAB:OP:ENABLE]" }
    }, sender);
    assert.equal(response.ok, true);
    assert.equal(h.storage.bridgeState.conversations[chatId].enabled, true);

    response = await h.sendRuntimeMessage({
      type: "bridge:operator-control",
      conversationUrl: url,
      fingerprint: fingerprint("operator-interval"),
      userIdentity: "user-interval-1",
      control: { marker: "[LAB:OP:INTERVAL=10m]" }
    }, sender);
    assert.equal(response.ok, true);
    assert.equal(h.storage.bridgeState.conversations[chatId].intervalOverrideMinutes, 10);

    const assistantAttempt = await h.sendRuntimeMessage({
      type: "bridge:assistant-control",
      conversationUrl: url,
      fingerprint: fingerprint("assistant-op-attempt"),
      assistantIdentity: "assistant-op-1",
      control: { marker: "[LAB:OP:REMOVE]" }
    }, sender);
    assert.equal(assistantAttempt.reason, "control_invalid_marker");
    assert.ok(h.storage.bridgeState.conversations[chatId]);

    response = await h.sendRuntimeMessage({
      type: "bridge:operator-control",
      conversationUrl: url,
      fingerprint: fingerprint("operator-remove"),
      userIdentity: "user-remove-1",
      control: { marker: "[LAB:OP:REMOVE]" }
    }, sender);
    assert.equal(response.ok, true);
    assert.equal(h.storage.bridgeState.conversations[chatId], undefined);
    assert.ok(h.storage.bridgeOperatorControlDedupe?.[chatId], "operator dedupe must survive chat removal");
  }

  // Infrastructure-bound CHATS may inspect all Bridge routing metadata; project chats remain current-only.
  {
    const h = createHarness();
    const add = async (url, repositoryId, idSeed) => h.sendRuntimeMessage({
      type: "bridge:operator-control",
      conversationUrl: url,
      fingerprint: fingerprint(idSeed),
      userIdentity: `user-${idSeed}`,
      chatLabel: repositoryId,
      assistantBaseline: "",
      control: { marker: `[LAB:OP:ADD=${repositoryId}]` }
    }, { tab: { url } });
    assert.equal((await add("https://chatgpt.com/c/a", "tracker", "add-a")).ok, true);
    assert.equal((await add("https://chatgpt.com/c/infra", "local-agent", "add-infra")).ok, true);

    const infra = await h.sendRuntimeMessage({
      type: "bridge:assistant-control",
      conversationUrl: "https://chatgpt.com/c/infra",
      fingerprint: fingerprint("infra-chats"),
      assistantIdentity: "assistant-infra",
      contentProtocolVersion: 4,
      control: { marker: "[LAB:CHATS]" }
    }, { tab: { url: "https://chatgpt.com/c/infra" } });
    assert.equal(infra.ok, true);
    assert.match(infra.feedbackPrompt, /"scope": "all-configured-chats"/);
    assert.match(infra.feedbackPrompt, /"count": 2/);

    const project = await h.sendRuntimeMessage({
      type: "bridge:assistant-control",
      conversationUrl: "https://chatgpt.com/c/a",
      fingerprint: fingerprint("project-chats"),
      assistantIdentity: "assistant-project",
      contentProtocolVersion: 4,
      control: { marker: "[LAB:CHATS]" }
    }, { tab: { url: "https://chatgpt.com/c/a" } });
    assert.equal(project.ok, true);
    assert.match(project.feedbackPrompt, /"scope": "current-chat-only"/);
    assert.match(project.feedbackPrompt, /"count": 1/);
  }

  // Regression for the live 4.18.16 failure: popup activates a reachable protocol-3 tab through the worker.
  {
    const h = createHarness({
      contentScriptProbe: async ({ injectedScripts }) => {
        const refreshed = injectedScripts.some((entry) => Array.isArray(entry.files) && entry.files.includes("content.js"));
        return {
          ok: true,
          reason: "ready",
          protocolVersion: refreshed ? protocol.CONTENT_PROTOCOL_VERSION : 3,
          assistantIdentity: "assistant-before-refresh"
        };
      }
    });
    const response = await h.sendRuntimeMessage({
      type: "bridge:ensure-tab-content",
      tabId: 11,
      expectedUrl: "https://chatgpt.com/c/a"
    });
    assert.equal(response.ok, true);
    assert.equal(response.protocolVersion, 4);
    assert.equal(h.injectedScripts.length, 2, "force refresh should dispose then inject once");
    assert.equal(h.injectedScripts[0].hasFunction, true);
    assert.deepEqual(h.injectedScripts[1].files, [
      "control_protocol.js",
      "content_retry.js",
      "content.js",
      "dom_contract.js",
      "exhaustion_guard.js"
    ]);
  }

  console.log("LAB diagnostic, operator control and popup protocol recovery tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
