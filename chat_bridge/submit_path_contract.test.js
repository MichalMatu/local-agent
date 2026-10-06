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

for (const [name, source] of [
  ["normal Bridge", content],
  ["Conversation Fabric", fabricContent]
]) {
  assert.match(
    source,
    /dispatchComposerBeforeInput\(composer, text\);/,
    `${name} must begin contenteditable mutation with a beforeinput lifecycle event`
  );
  assert.match(
    source,
    /dispatchComposerInput\(composer, text\);/,
    `${name} must always finish contenteditable mutation with an explicit input event`
  );
  assert.doesNotMatch(
    source,
    /formFallbackAt|formFallbackAttempted|submitBoundaryCrossed/,
    `${name} must never cross a delayed second submit mechanism`
  );
}

assert.match(
  fabricContent,
  /const form = composer\?\.closest\?\.\("form"\);[\s\S]*form\.requestSubmit\(\);[\s\S]*sendButton\.click\(\);/,
  "Conversation Fabric must prefer one native form submit boundary and use button click only when no form submit path exists"
);

assert.match(
  fabricContent,
  /const composerInputVersions = new WeakMap\(\);/,
  "Fabric must track composer input generations for prompt provenance"
);
assert.match(
  fabricContent,
  /const ownedComposerPrompts = new WeakMap\(\);/,
  "Fabric must retain only same-content-script prompt ownership"
);
assert.match(
  fabricContent,
  /existingComposerText && composerOwnedPromptMatches\(composer, prompt\)/,
  "Fabric may reuse pre-existing text only when this content-script instance owns it"
);
assert.match(
  fabricContent,
  /document\.removeEventListener\("input", trackComposerInput, true\)/,
  "Fabric must release its composer provenance listener on reinjection"
);
assert.match(
  fabricContent,
  /submitComposer\(composer, button\);[\s\S]*ownership\.submissionAttempted = true;/,
  "Fabric must mark its exact owned prompt only after a submit attempt was actually issued"
);
assert.match(
  fabricContent,
  /composerOwnedPromptSubmissionAttempted\(composer, prompt\)/,
  "Fabric retries must not click the same unchanged owned prompt twice"
);

console.log("Chat Bridge live Send submission contract tests passed.");
