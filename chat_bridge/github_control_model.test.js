"use strict";

const assert = require("node:assert/strict");
const model = require("./github_control_model.js");

const AGENT = Object.freeze({
  repositoryId: "local-agent",
  repository: "MichalMatu/local-agent",
  agentBinding: "2180d453-1357-4fbc-be1a-e1e5b8fbb10a",
  executionEnabled: true
});

function raw(overrides = {}) {
  return {
    conversation_id: "chat-e8ad8275",
    repository_id: AGENT.repositoryId,
    repository: AGENT.repository,
    agent_binding: AGENT.agentBinding,
    binding_revision: 1,
    control_generation: 7,
    enabled: true,
    interval_minutes: 5,
    next_wake_at: "2026-09-30T00:30:00+02:00",
    updated_at: "2026-09-30T00:28:00+02:00",
    ...overrides
  };
}

const [control] = model.validateConversationControls([raw()], [AGENT]);
assert.equal(control.conversationId, "chat-e8ad8275");
assert.equal(control.controlGeneration, 7);
assert.equal(control.nextWakeAt, "2026-09-29T22:30:00.000Z");
assert.equal(control.updatedAt, "2026-09-29T22:28:00.000Z");
assert.equal(control.intervalMinutes, 5);

assert.equal(model.findConversationControl({ conversationControls: [control] }, control.conversationId), control);
assert.equal(model.findConversationControl({ conversationControls: [control] }, "chat-00000000"), null);

const localConversation = {
  id: control.conversationId,
  repositoryId: control.repositoryId,
  repository: control.repository,
  agentBinding: control.agentBinding,
  bindingRevision: 1
};
assert.equal(model.controlMatchesConversation(control, localConversation), true);
assert.equal(model.controlMatchesConversation(control, { ...localConversation, bindingRevision: 2 }), true);
assert.equal(model.controlMatchesConversation(control, { ...localConversation, repositoryId: "growclip" }), true);

const now = Date.parse("2026-09-29T22:00:00.000Z");
assert.equal(
  model.scheduleDeadline(control, 10, now),
  Date.parse("2026-09-29T22:30:00.000Z")
);
const overdue = model.sanitizeConversationControl(raw({
  next_wake_at: "2026-09-29T21:00:00Z",
  updated_at: "2026-09-29T20:59:00Z"
}));
assert.equal(model.scheduleDeadline(overdue, 10, now), now + 5 * 60_000);
const defaultInterval = model.sanitizeConversationControl(raw({ next_wake_at: null, interval_minutes: null }));
assert.equal(model.scheduleDeadline(defaultInterval, 10, now), now + 10 * 60_000);
const paused = model.sanitizeConversationControl(raw({ enabled: false, next_wake_at: null }));
assert.equal(model.scheduleDeadline(paused, 10, now), null);
const futureDatedControl = model.sanitizeConversationControl(raw({
  updated_at: "2026-10-01T22:00:00Z",
  next_wake_at: "2026-10-01T23:00:00Z"
}));
assert.throws(
  () => model.scheduleDeadline(futureDatedControl, 10, now),
  /maximum horizon from now/
);

assert.throws(
  () => model.validateConversationControls([raw(), raw({ control_generation: 8 })], [AGENT]),
  /duplicate runtime conversation control/
);
const transportOnly = model.sanitizeConversationControl({
  conversation_id: "chat-00000001",
  control_generation: 1,
  enabled: true,
  interval_minutes: 10,
  next_wake_at: null,
  updated_at: "2026-09-30T00:28:00+02:00"
});
assert.equal(transportOnly.repositoryId, null);
assert.equal(transportOnly.agentBinding, null);
assert.equal(transportOnly.bindingRevision, 0);
assert.equal(model.controlMatchesConversation(transportOnly, { id: "chat-00000001" }), true);
assert.throws(
  () => model.sanitizeConversationControl(raw({ binding_revision: 0 })),
  /binding_revision/
);
assert.throws(
  () => model.sanitizeConversationControl(raw({ control_generation: 0 })),
  /control_generation/
);
assert.throws(
  () => model.sanitizeConversationControl(raw({ interval_minutes: 0 })),
  /interval_minutes/
);
assert.throws(
  () => model.sanitizeConversationControl(raw({ next_wake_at: "2026-09-30T00:30:00" })),
  /offset-aware/
);
assert.throws(
  () => model.sanitizeConversationControl(raw({ enabled: false })),
  /disabled.*next_wake_at/
);
assert.throws(
  () => model.sanitizeConversationControl(raw({
    next_wake_at: "2026-09-30T00:27:00+02:00"
  })),
  /must not precede updated_at/
);
assert.throws(
  () => model.sanitizeConversationControl(raw({
    next_wake_at: "2026-10-01T00:29:00+02:00"
  })),
  /maximum wake horizon/
);

console.log("GitHub Bridge control model tests passed.");
