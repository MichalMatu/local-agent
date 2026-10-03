"use strict";

const assert = require("node:assert/strict");
const { createHarness } = require("./worker_test_harness.js");

async function addConversation(harness, repositoryId, url) {
  const agent = harness.runtimeAgents.find((item) => item.repository_id === repositoryId);
  assert.ok(agent, `missing runtime agent ${repositoryId}`);
  const result = await harness.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: {
      url,
      agentBinding: agent.agent_binding,
      enabled: true,
      preferredTabId: url.endsWith("/a") ? 11 : 22
    }
  });
  assert.equal(result.ok, true, result.error);
  return { id: result.conversation.id, agent };
}

(async () => {
  {
    const h = createHarness();
    const { id, agent } = await addConversation(h, "host-ops", "https://chatgpt.com/c/a");
    assert.equal(agent.planner_scope, "multirepo");

    const result = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    assert.equal(result.ok, true, result.reason);
    assert.equal(h.sentMessages.length, 1);
    const prompt = h.sentMessages[0].message.prompt;

    assert.match(prompt, /transport\/scheduling channel, not a repository execution binding/);
    assert.match(prompt, /may include multiple repositories, including donor and target repositories, without rebinding the chat/);
    assert.match(prompt, /use that target.s exact canonical agent_binding/);
    assert.match(prompt, /Bridge metadata as execution authority/);
    assert.match(prompt, /local-agent=MichalMatu\/local-agent@2180d453-1357-4fbc-be1a-e1e5b8fbb10a;execution=disabled/);
    assert.match(prompt, /growclip=MichalMatu\/growclip@2db52048-57ea-4643-bf4b-1ea5c5c3fa86;execution=enabled/);
    assert.doesNotMatch(prompt, /Work only on repository MichalMatu\/host-ops/);
    assert.doesNotMatch(prompt, /Every Local Agent task JSON created by this conversation MUST contain exactly/);
  }

  {
    const h = createHarness();
    const { id, agent } = await addConversation(h, "matrixhub", "https://chatgpt.com/c/b");
    assert.equal(agent.planner_scope, undefined);

    const result = await h.sendRuntimeMessage({ type: "bridge:run-now", conversationId: id });
    assert.equal(result.ok, true, result.reason);
    const prompt = h.sentMessages[0].message.prompt;

    assert.match(prompt, /transport\/scheduling channel, not a repository execution binding/);
    assert.match(prompt, /may include multiple repositories, including donor and target repositories, without rebinding the chat/);
    assert.match(prompt, /use that target.s exact canonical agent_binding/);
    assert.doesNotMatch(prompt, /Work only on repository MichalMatu\/MatrixHub/);
  }

  {
    const h = createHarness();
    const defaultScope = h.evaluate(`sanitizeRuntimeAgent({
      repository_id: "a",
      repository: "Owner/A",
      agent_binding: "033327ab-700d-43b4-9b3b-caff1acaa2c7",
      execution_enabled: true
    }).plannerScope`);
    assert.equal(defaultScope, "repository");
    assert.throws(
      () => h.evaluate(`sanitizeRuntimeAgent({
        repository_id: "a",
        repository: "Owner/A",
        agent_binding: "033327ab-700d-43b4-9b3b-caff1acaa2c7",
        execution_enabled: true,
        planner_scope: "global"
      })`),
      /planner_scope/
    );
    assert.throws(
      () => h.evaluate(`sanitizeRuntimeAgent({
        repository_id: "a",
        repository: "Owner/A",
        agent_binding: "033327ab-700d-43b4-9b3b-caff1acaa2c7",
        execution_enabled: false,
        planner_scope: "multirepo"
      })`),
      /requires execution_enabled=true/
    );
  }

  console.log("Chat Bridge transport-only multirepo tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});