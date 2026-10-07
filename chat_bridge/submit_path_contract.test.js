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
  /dispatchComposerBeforeInput\(composer, text\);/,
  "normal Bridge must begin contenteditable mutation with a beforeinput lifecycle event"
);
assert.match(
  content,
  /dispatchComposerInput\(composer, text\);/,
  "normal Bridge must always finish contenteditable mutation with an explicit input event"
);
assert.doesNotMatch(
  content,
  /formFallbackAt|formFallbackAttempted|submitBoundaryCrossed/,
  "normal Bridge must never cross a delayed second submit mechanism"
);

for (const forbidden of [
  "findComposer",
  "setComposerText",
  "submitComposer",
  "findSendButton",
  "dispatchComposerBeforeInput",
  "dispatchComposerInput",
  "ownedComposerPrompts",
  "composerInputVersions",
  "deliverFabricFeedback"
]) {
  assert.doesNotMatch(
    fabricContent,
    new RegExp("\\b" + forbidden + "\\b"),
    `Conversation Fabric control scanner must not own parent-composer primitive: ${forbidden}`
  );
}

assert.match(
  fabricContent,
  /Machine diagnostics must never be injected into the parent composer/,
  "Fabric malformed-control handling must remain machine-only"
);
assert.match(
  fabricContent,
  /single journaled feedback path/,
  "Fabric feedback must be delegated to the worker delivery path"
);

console.log("Chat Bridge parent composer ownership contract tests passed.");
