"use strict";

const assert = require("node:assert/strict");
const eventWakeState = require("./event_wake_state.js");

const BINDING = "033327ab-700d-43b4-9b3b-caff1acaa2c7";
const NOW = Date.parse("2026-09-16T09:30:00.000Z");

function rawEvent(overrides = {}) {
  return {
    schema_version: 1,
    event_id: `evt-${"a".repeat(32)}`,
    event_type: "task_result_ready",
    emitted_at: "2026-09-16T09:00:00.000Z",
    repository_id: "matrixhub",
    repository: "MichalMatu/MatrixHub",
    agent_binding: BINDING,
    task_id: "state-1",
    task_digest: "digest-state-1",
    result_status: "done",
    ...overrides
  };
}

assert.equal(eventWakeState.isoTimestamp("2026-09-16T09:00:00.000Z"), "2026-09-16T09:00:00.000Z");
assert.equal(eventWakeState.isoTimestamp("2026-99-99T09:00:00.000Z"), null);
assert.equal(eventWakeState.isoTimestamp("2026-09-16T09:00:00"), null,
  "persisted event timestamps must include an explicit timezone");

const event = eventWakeState.sanitizeNativeTaskEvent(rawEvent(), {
  receivedAt: "2026-09-16T09:00:01.000Z"
});
assert.ok(event);

const invalidStoredTimestamp = eventWakeState.sanitizeState({
  version: 1,
  watches: {},
  recentEvents: {
    [event.eventId]: { ...event, receivedAt: "not-a-timestamp" }
  },
  pendingWakes: {},
  diagnostics: {}
}, NOW);
assert.deepEqual(invalidStoredTimestamp.recentEvents, {},
  "invalid persisted timestamps must fail closed instead of being replaced with now");

const futureEvent = eventWakeState.sanitizeNativeTaskEvent(rawEvent({
  event_id: `evt-${"b".repeat(32)}`,
  task_id: "future-state-1",
  task_digest: "digest-future-state-1"
}), {
  receivedAt: "2026-09-17T09:30:00.000Z"
});
assert.ok(futureEvent);
const futureState = eventWakeState.sanitizeState({
  version: 1,
  watches: {},
  recentEvents: { [futureEvent.eventId]: futureEvent },
  pendingWakes: {},
  diagnostics: {}
}, NOW);
assert.deepEqual(futureState.recentEvents, {},
  "far-future stored timestamps must not bypass recent-event retention bounds");

const diagnostics = eventWakeState.sanitizeDiagnostics({
  nativeState: "totally-invalid",
  nativeProtocolVersion: 9999,
  lastError: "x".repeat(1000),
  lastAcceptedEventId: "not-an-event",
  arbitrarySecretField: "must-not-survive"
});
assert.equal(diagnostics.nativeState, "unknown");
assert.equal(diagnostics.nativeProtocolVersion, null);
assert.equal(diagnostics.lastError.length, 512);
assert.equal(diagnostics.lastAcceptedEventId, null);
assert.equal(Object.hasOwn(diagnostics, "arbitrarySecretField"), false,
  "diagnostic storage must use an explicit allowlist");

const watch = eventWakeState.sanitizeTaskWatch({
  conversationId: "chat-1234abcd",
  repositoryId: "matrixhub",
  repository: "MichalMatu/MatrixHub",
  agentBinding: BINDING,
  taskId: "state-1",
  bindingRevision: 3,
  bindingSetAt: "2026-09-16T08:00:00.000Z",
  createdAt: "2026-09-16T09:00:00.000Z"
});
assert.ok(watch);
const matchingConversation = {
  id: "chat-1234abcd",
  repositoryId: "matrixhub",
  repository: "MichalMatu/MatrixHub",
  agentBinding: BINDING,
  bindingRevision: 3,
  bindingSetAt: "2026-09-16T08:00:00.000Z"
};
assert.equal(eventWakeState.watchMatchesConversation(watch, matchingConversation), true);
assert.equal(eventWakeState.watchMatchesConversation(watch, {
  ...matchingConversation,
  bindingRevision: 4
}), false, "binding epoch changes must invalidate persisted ownership");

const pending = eventWakeState.pendingWakeFromEvent(event, watch);
assert.equal(eventWakeState.pendingWakeClaimsWatch(pending, watch), true);
assert.equal(eventWakeState.pendingWakeMatchesConversation(pending, matchingConversation), true);

console.log("Chat Bridge pure event wake state tests passed.");
