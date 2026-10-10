"use strict";

const assert = require("node:assert/strict");
const protocol = require("./control_protocol.js");
const model = require("./github_control_model.js");
const example = require("./runtime.example.json");
const { createHarness } = require("./worker_test_harness.js");

const url = "https://chatgpt.com/c/a";
const chatId = protocol.conversationId(url);
const localAgent = example.agents.find((agent) => agent.repository_id === "local-agent");
assert.ok(localAgent);
const taskId = "local-agent-mvp-result-watch-01";
const watch = { repository_id: "local-agent", task_id: taskId };
let control = {
  conversation_id: chatId,
  control_generation: 1,
  enabled: true,
  interval_minutes: 10,
  next_wake_at: null,
  updated_at: new Date().toISOString(),
  task_result_watch: watch
};

function responseBody(value) {
  const bytes = new TextEncoder().encode(JSON.stringify(value));
  let emitted = false;
  return {
    getReader() {
      return {
        async read() {
          if (emitted) return { done: true };
          emitted = true;
          return { done: false, value: bytes };
        },
        releaseLock() {}
      };
    }
  };
}

function makeHarness(storage = {}) {
  let resultStatus = "missing";
  let wrongIdentity = false;
  let extraBytes = false;
  let resultReads = 0;
  const h = createHarness({
    storage,
    fetch: async (target) => {
      if (target.includes("/agent-control/.agent/results/")) {
        resultReads++;
        assert.match(target, /raw.githubusercontent.com\/MichalMatu\/local-agent\/agent-control\/\.agent\/results\/local-agent-mvp-result-watch-01\.json/);
        if (resultStatus === "missing") return { ok: false, status: 404 };
        if (resultStatus === "error") return { ok: false, status: 503 };
        return { ok: true, status: 200, body: extraBytes
          ? { getReader() { return { async read() { return { done: false, value: new Uint8Array(262145) }; }, async cancel() {}, releaseLock() {} }; } }
          : responseBody({ id: wrongIdentity ? "other-task" : taskId, status: resultStatus }) };
      }
      return {
        ok: true,
        async json() {
          return { ...example, bootstrap_prompt: "BOOTSTRAP", wake_prompt: "WAKE", conversation_controls: [control] };
        }
      };
    }
  });
  h.context.TextDecoder = TextDecoder;
  h.context.Uint8Array = Uint8Array;
  return {
    h,
    setStatus(value) { resultStatus = value; },
    setWrongIdentity(value) { wrongIdentity = value; },
    setOversize(value) { extraBytes = value; },
    getResultReads() { return resultReads; }
  };
}

(async () => {
  const parsed = model.sanitizeConversationControl(control);
  assert.equal(parsed.taskResultWatch.taskId, taskId);
  assert.equal(parsed.taskResultWatch.repositoryId, "local-agent");
  assert.throws(() => model.sanitizeConversationControl({ ...control, task_result_watch: { ...watch, task_id: "../bad" } }), /task_id is invalid/);
  assert.throws(() => model.sanitizeConversationControl({ ...control, enabled: false }), /disabled conversation cannot watch/);
  assert.throws(() => model.validateConversationControls([control], []), /enabled configured repository/);
  assert.throws(() => model.validateConversationControls([control], [{ ...localAgent, repositoryId: "local-agent", executionEnabled: false }]), /enabled configured repository/);

  const fixture = makeHarness();
  const { h } = fixture;
  const added = await h.sendRuntimeMessage({
    type: "bridge:upsert-conversation",
    conversation: { url, preferredTabId: 11, label: "MVP", enabled: true }
  });
  assert.equal(added.ok, true);
  await h.evaluate("reconcileGithubConversationControls()");
  const before = h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime;
  assert.ok(before > Date.now() + 5 * 60_000, "normal 10m cadence is preserved before completion");

  await h.evaluate("pollGithubTaskResultWakes()");
  assert.equal(h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime, before);
  assert.equal(h.sentMessages.length, 0);

  fixture.setStatus("done");
  fixture.setWrongIdentity(true);
  await h.evaluate("pollGithubTaskResultWakes()");
  assert.equal(h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime, before, "foreign task result is inert");
  fixture.setWrongIdentity(false);

  fixture.setOversize(true);
  await h.evaluate("pollGithubTaskResultWakes()");
  assert.equal(h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime, before, "oversize result is inert");
  fixture.setOversize(false);

  h.storage.bridgeState.settings.masterEnabled = false;
  await h.evaluate("pollGithubTaskResultWakes()");
  assert.equal(h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime, before, "Master off blocks task wake");
  h.storage.bridgeState.settings.masterEnabled = true;

  const previousGeneration = h.storage.bridgeGithubControlApplied[chatId].generation;
  h.storage.bridgeGithubControlApplied[chatId].generation = 99;
  await h.evaluate("pollGithubTaskResultWakes()");
  assert.equal(h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime, before, "wrong applied generation blocks task wake");
  h.storage.bridgeGithubControlApplied[chatId].generation = previousGeneration;

  const triggered = await h.evaluate("pollGithubTaskResultWakes()");
  assert.equal(triggered.triggered, 1);
  const quick = h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime;
  assert.ok(quick > Date.now() && quick < Date.now() + 5000, "completion advances existing alarm");
  assert.equal(h.sentMessages.length, 0, "watch never directly sends a ChatGPT message");
  assert.equal(h.storage.bridgeTaskResultWakeReceiptsV1[`${chatId}:local-agent:${taskId}`] > 0, true);

  const reads = fixture.getResultReads();
  const again = await h.evaluate("pollGithubTaskResultWakes()");
  assert.equal(again.triggered, 0);
  assert.equal(fixture.getResultReads(), reads, "durable watch claim suppresses repeated network lookups");
  assert.equal(h.alarms.get(`local-agent-chat:${chatId}`)?.scheduledTime, quick);

  // New worker instance retains the consumed identity and cannot submit or rearm.
  const restarted = makeHarness(h.storage);
  restarted.setStatus("done");
  await restarted.h.installed();
  const afterRestart = await restarted.h.evaluate("pollGithubTaskResultWakes()");
  assert.equal(afterRestart.triggered, 0);
  assert.equal(restarted.getResultReads(), 0);
  assert.equal(restarted.h.sentMessages.length, 0);

  console.log("MVP one-Chrome exact task-result wake tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
