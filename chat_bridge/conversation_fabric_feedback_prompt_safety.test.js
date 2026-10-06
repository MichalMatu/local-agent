"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const worker = fs.readFileSync(
  path.join(__dirname, "worker_conversation_fabric.js"),
  "utf8"
);

assert.doesNotMatch(
  worker,
  /<<<LOCAL_AGENT_CF/,
  "Bridge-generated Conversation Fabric feedback must never contain an executable control envelope"
);
assert.doesNotMatch(
  worker,
  /conversationFabric(?:Control|Collect|Inspect|Retire)Block/,
  "worker feedback must not synthesize executable Conversation Fabric control blocks"
);
assert.match(
  worker,
  /No parent action is required while children are still running\./,
  "running-campaign feedback must make the passive automatic wait contract explicit"
);
assert.match(
  worker,
  /Do not emit LOCAL_AGENT_CF inspect, collect, retire, or delegate controls/,
  "running-campaign feedback must explicitly forbid self-triggered control echo"
);

console.log("Conversation Fabric feedback prompt safety tests passed.");
