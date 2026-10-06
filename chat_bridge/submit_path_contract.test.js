"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const content = fs.readFileSync(path.join(__dirname, "content.js"), "utf8");
const fabricContent = fs.readFileSync(
  path.join(__dirname, "conversation_fabric_content.js"),
  "utf8"
);

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

for (const [name, source] of [
  ["normal Bridge", content],
  ["Conversation Fabric", fabricContent]
]) {
  assert.match(
    source,
    /const formFallbackAt = Date\.now\(\) \+ 1200;/,
    `${name} must bound the post-click fallback delay`
  );
  assert.match(
    source,
    /let formFallbackAttempted = false;/,
    `${name} must permit at most one post-click fallback attempt`
  );
  assert.match(
    source,
    /composerText\(composer\) === /,
    `${name} fallback must require the exact unchanged Bridge-owned composer text`
  );
  assert.match(
    source,
    /form\.requestSubmit\(\);/,
    `${name} must use native form submission only after the guarded click path stalls`
  );
}

console.log("Chat Bridge live Send submission contract tests passed.");
