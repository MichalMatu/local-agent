"use strict";

const assert = require("node:assert/strict");
const stateModel = require("./bridge_state.js");

const migrated = stateModel.migrateLegacyStorage({
  enabled: true,
  conversationUrl: "https://chat.openai.com/c/legacy?x=1",
  fallbackIntervalMinutes: 7,
  fallbackBusyRetryMinutes: 2,
  fallbackPrompt: "legacy bootstrap",
  intervalOverrideMinutes: 12,
  lastStatus: "sent",
  lastControlFingerprint: "abcd1234"
});
assert.equal(migrated.migrated, true);
assert.equal(migrated.state.settings.fallbackIntervalMinutes, 7);
const legacy = Object.values(migrated.state.conversations)[0];
assert.equal(legacy.url, "https://chatgpt.com/c/legacy");
assert.equal(legacy.enabled, true);
assert.equal(legacy.bootstrapPending, true);
assert.equal(legacy.intervalOverrideMinutes, 12);
assert.equal(legacy.lastControlFingerprint, "abcd1234");

let state = stateModel.emptyState();
let result = stateModel.upsertConversation(state, {
  url: "https://chatgpt.com/c/a",
  label: "Project A",
  repositoryId: "repo-a",
  preferredTabId: 10
});
state = result.state;
const aId = result.conversation.id;
result = stateModel.upsertConversation(state, {
  url: "https://chatgpt.com/c/b",
  label: "Project B",
  repositoryId: "repo-b",
  preferredTabId: 20
});
state = result.state;
const bId = result.conversation.id;
assert.notEqual(aId, bId);
assert.equal(Object.keys(state.conversations).length, 2);
assert.equal(state.conversations[aId].bootstrapPending, true);

const patched = stateModel.patchConversation(state, aId, {
  enabled: false,
  intervalOverrideMinutes: 15,
  lastStatus: "paused_by_assistant"
});
state = patched.state;
assert.equal(state.conversations[aId].enabled, false);
assert.equal(state.conversations[aId].intervalOverrideMinutes, 15);
assert.equal(state.conversations[bId].enabled, true);
assert.equal(state.conversations[bId].intervalOverrideMinutes, null);

assert.equal(
  stateModel.findConversationByUrl(state, "https://chat.openai.com/c/b")?.id,
  bId
);
state = stateModel.removeConversation(state, aId);
assert.equal(Object.keys(state.conversations).length, 1);
assert.equal(Boolean(state.conversations[bId]), true);

console.log("Chat Bridge state tests passed.");
