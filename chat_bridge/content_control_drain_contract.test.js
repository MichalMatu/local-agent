"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const content = fs.readFileSync(path.join(__dirname, "content.js"), "utf8");
const workerBase = fs.readFileSync(path.join(__dirname, "worker_base.js"), "utf8");

assert.match(
  content,
  /async function drainLatestAssistantControlBeforeFeedback\(\)/,
  "content script must expose an explicit pre-feedback control drain"
);

const feedbackHandlerStart = content.indexOf('if (message?.type !== "bridge:feedback") return false;');
assert.notEqual(feedbackHandlerStart, -1);
const feedbackHandler = content.slice(feedbackHandlerStart, feedbackHandlerStart + 1200);
const drainIndex = feedbackHandler.indexOf("await drainLatestAssistantControlBeforeFeedback()");
const sendIndex = feedbackHandler.indexOf("return sendFeedback(");
assert.ok(drainIndex >= 0, "feedback handler must drain assistant control");
assert.ok(sendIndex > drainIndex, "assistant control must be drained before automatic wake delivery");

assert.match(
  workerBase,
  /"assistant_control_pending"/,
  "pending control must use bounded retry pacing rather than the normal wake interval"
);

console.log("Chat Bridge control-drain ordering contract tests passed.");
