"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const content = fs.readFileSync(path.join(__dirname, "content.js"), "utf8");

assert.match(
  content,
  /if \(sendButton instanceof HTMLButtonElement && sendButton\.isConnected && !sendButton\.disabled\) \{\s*sendButton\.click\(\);\s*return;/s,
  "Bridge must use the live ChatGPT Send button as the primary submit path"
);
assert.match(
  content,
  /sendButton = findSendButton\(composer\) \|\| await waitForSendButton\(composer, 1200\);/,
  "Bridge must re-resolve the live Send button immediately before submission"
);
assert.doesNotMatch(
  content,
  /form\.requestSubmit\(sendButton\)/,
  "Bridge must not prefer requestSubmit(button) over the live button click path"
);
assert.match(
  content,
  /form\.requestSubmit\(\);/,
  "requestSubmit without a stale button may remain as a last-resort fallback"
);

console.log("Chat Bridge live Send submission contract tests passed.");
