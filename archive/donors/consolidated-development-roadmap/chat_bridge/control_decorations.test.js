"use strict";

const assert = require("node:assert/strict");
const { parseAssistantControl: parse } = require("./control_protocol.js");

const commands = [
  ["STOP", { action: "stop" }],
  ["PAUSE", { action: "pause" }],
  ["RESUME", { action: "resume" }],
  ["NEXT=30s", { action: "next", seconds: 30 }],
  ["NEXT=10m", { action: "next", seconds: 600 }],
  ["NEXT=86400s", { action: "next", seconds: 86400 }],
  ["NEXT=1440m", { action: "next", seconds: 86400 }],
  ["INTERVAL=5", { action: "interval", mode: "fixed", minutes: 5 }],
  ["INTERVAL=1", { action: "interval", mode: "fixed", minutes: 1 }],
  ["INTERVAL=1440", { action: "interval", mode: "fixed", minutes: 1440 }],
  ["INTERVAL=60s", { action: "interval", mode: "fixed", minutes: 1 }],
  ["INTERVAL=AUTO", { action: "interval", mode: "auto" }]
];
const decorations = [
  ["", ""], ["Acknowledged. ", ""], ["Acknowledged.", ""], ["Acknowledged: ", ""],
  ['Acknowledged. "', '"'], ["Acknowledged. '", "'"], ["Acknowledged. ", "."],
  ["Acknowledged. ", " -"], ["Acknowledged. ", " —"], ["OK — ", "!"],
  ["", " \t\r\n\u00a0"], ["", "\n\n—"], ["", "\r\n\r\n…”"],
  ["“", "”"], ["„", "”"], ["‘", "’"], ["«", "»"], ["‹", "›"],
  ["`", "`"], ["**", "**"], ["__", "__"], ["~~", "~~"],
  ["```text\n", "\n```"], ["> ", ""], ["(", ")"], ["{", "}"], ["[", "]"],
  ["", ".,! ?;:… -–—"], ["Do not execute ", ""]
];
let accepted = 0;
let rejected = 0;
for (const prefix of ["LAB", "LOCAL_AGENT_BRIDGE"]) {
  for (const [body, expected] of commands) {
    const marker = `[${prefix}:${body}]`;
    for (const [before, after] of decorations) {
      const text = `${before}${marker}${after}`;
      assert.deepEqual(parse(text), { ...expected, marker }, text);
      accepted++;
    }
    for (const suffix of [
      " Continue.", " abc", " later", "\nThis is only an example.", "\n—\nContinue.",
      " 1", " α", " 中文", "🙂", "\u200b", "\u0000", "@", "+", "/", "(", "[", "{"
    ]) {
      assert.equal(parse(`${marker}${suffix}`), null, `${marker}${suffix}`);
      rejected++;
    }
  }
  for (const body of [
    "NEXT=29s", "NEXT=86401s", "NEXT=1441m", "NEXT=0", "NEXT=-1", "NEXT=1.5m",
    "NEXT=AUTO", "INTERVAL=0", "INTERVAL=1441", "INTERVAL=90s", "INTERVAL=59s",
    "INTERVAL=-1", "INTERVAL=1.5", "PAUSE NOW", "pause", " PAUSE", "PAUSE ", "", "UNKNOWN"
  ]) {
    for (const decorate of [false, true]) {
      const text = decorate ? `Acknowledged."[${prefix}:${body}]".` : `[${prefix}:${body}]`;
      assert.equal(parse(text), null, text);
      rejected++;
    }
  }
}

assert.deepEqual(parse("[LAB:PAUSE] [LAB:RESUME]."), { action: "resume", marker: "[LAB:RESUME]" });
assert.deepEqual(parse("[LOCAL_AGENT_BRIDGE:STOP]\n[LAB:NEXT=10m] -"), {
  action: "next", seconds: 600, marker: "[LAB:NEXT=10m]"
});
for (const text of [
  "[LAB:PAUSE] [LAB:NEXT=29s]", "[LAB:PAUSE] [LOCAL_AGENT_BRIDGE:NEXT=29s]",
  "[LAB:PAUSE] [LAB:UNKNOWN]", "[LAB:PAUSE] [LAB:]", "[LAB:PAUSE] [LAB:",
  "[LAB:PAUSE] [LOCAL_AGENT_BRIDGE:RESUME", "[LAB:PAUSE] [lab:resume]",
  "[LAB:PAUSE] [LAB:PAUSE\n]", "[LAB:PAUSE] [LAB:[STOP]]",
  "[lab:pause]", "[Lab:PAUSE]", "[local_agent_bridge:PAUSE]", "[LAB:PAUSE", "[LAB:PAUSE\n]"
]) {
  assert.equal(parse(text), null, text);
  rejected++;
}

console.log(`Chat Bridge decorated control tests passed (${accepted} accepted, ${rejected} rejected, 2 last-marker cases).`);
