"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const crypto = require("node:crypto");
const intakeModel = require("./github_fabric_intake_model.js");
const dispatchModel = require("./github_fabric_dispatch_model.js");
const runtimeUrl =
  "https://raw.githubusercontent.com/MichalMatu/local-agent/chat-bridge-state/chat_bridge/runtime.json";
const parentUrl = "https://chatgpt.com/c/6ac6840c-eaec-83ed-bde2-6971e9ffa220";
const id = "fabric-" + "a".repeat(32);
const hash = (value) => crypto.createHash("sha256").update(value).digest("hex");
const makeDispatch = (text) => ({
  schema_version: 1,
  operation: "delegate",
  id,
  request_id: "operator-1",
  request_digest: "sha256:" + "b".repeat(64),
  campaign_id: "cf-0123456789abcdef",
  parent_conversation_url: parentUrl,
  children: [{
    id: "research",
    request_id: "child-research",
    role: "research",
    spawn: {
      schema_version: 1,
      transaction_id: "spawn-" + "c".repeat(64),
      child_request_digest: "sha256:" + "d".repeat(64),
      bootstrap_digest: "sha256:" + hash(text),
      bootstrap_text: text
    }
  }]
});

async function suite() {
  const store = {};
  let requests = [];
  let active = true;
  let enabled = false;
  let dispatch = makeDispatch("LOCAL AGENT CHILD BOOTSTRAP\nFirst immutable bootstrap.");
  const bridgeState = {
    settings: { masterEnabled: true, runtimeUrl },
    conversations: { "chat-parent": { id: "chat-parent", enabled: true } }
  };
  const fetch = async (url) => {
    requests.push(url);
    const path = String(url).split("?")[0];
    const payload = path === intakeModel.indexUrl(runtimeUrl)
      ? { schema_version: 1, dispatch_ids: [id] }
      : path === intakeModel.dispatchUrl(runtimeUrl, id) ? dispatch : null;
    if (!payload) return { ok: false, status: 404 };
    const bytes = Buffer.from(JSON.stringify(payload));
    let consumed = false;
    return {
      ok: true,
      body: {
        getReader() {
          return {
            async read() {
              if (consumed) return { done: true };
              consumed = true;
              return { done: false, value: bytes };
            },
            releaseLock() {}
          };
        }
      }
    };
  };
  const context = vm.createContext({
    globalThis: {
      LocalAgentGithubFabricIntakeModel: intakeModel,
      LocalAgentGithubFabricDispatchModel: dispatchModel
    },
    chrome: {
      storage: {
        local: {
          async get(key) { return { [key]: store[key] }; },
          async set(items) { Object.assign(store, items); }
        }
      }
    },
    getBridgeState: async () => bridgeState,
    fetchRuntime: async () => ({
      source: "remote",
      githubFabricReadOnlyIntakeEnabled: enabled,
      conversationControls: [{ conversationId: "chat-parent", enabled: true }]
    }),
    fetch,
    conversationId: (url) => url === parentUrl ? "chat-parent" : "wrong",
    githubControlModel: {
      findConversationControl: (runtime, chatId) =>
        runtime.conversationControls.find((entry) => entry.conversationId === chatId) || null,
      controlMatchesConversation: (control, conversation) =>
        control.conversationId === conversation.id
    },
    requireConversationSpawnBootstrapDigest: async (intent) => {
      assert.equal(intent.tab_id, null);
      assert.equal(intent.bootstrap_digest, "sha256:" + hash(intent.bootstrap_text));
    },
    conversationSpawnSha256: async (text) => hash(text),
    AbortController,
    TextDecoder,
    Uint8Array,
    setTimeout,
    clearTimeout,
    console
  });
  vm.runInContext(fs.readFileSync(require.resolve("./worker_github_fabric_intake.js"), "utf8"), context);

  assert.equal((await context.pollGithubFabricReadOnlyIntake()).status, "disabled");
  assert.equal(requests.length, 0);
  enabled = true;
  assert.equal((await context.pollGithubFabricReadOnlyIntake()).stored, 1);
  assert.equal(requests.length, 2);
  assert.equal((await context.pollGithubFabricReadOnlyIntake()).replayed, 1);
  dispatch = makeDispatch("LOCAL AGENT CHILD BOOTSTRAP\nModified bootstrap.");
  assert.equal((await context.pollGithubFabricReadOnlyIntake()).conflicts, 1);
  const seen = store.bridgeGithubFabricReadOnlySeen;
  assert.equal(seen[id], hash(dispatchModel.canonicalJson(makeDispatch("LOCAL AGENT CHILD BOOTSTRAP\nFirst immutable bootstrap."))));
  active = false;
  bridgeState.conversations["chat-parent"].enabled = active;
  assert.equal((await context.pollGithubFabricReadOnlyIntake()).skipped, 1);
  bridgeState.settings.masterEnabled = false;
  requests = [];
  assert.equal((await context.pollGithubFabricReadOnlyIntake()).status, "master_disabled");
  assert.equal(requests.length, 0);
  assert.ok(!Object.keys(store).some((key) => key.startsWith("conversation-fabric-campaign:")));
}

suite().then(() => {
  console.log("GitHub Fabric read-only worker intake tests passed.");
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
