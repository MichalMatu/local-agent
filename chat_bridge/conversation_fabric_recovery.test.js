"use strict";

const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = __dirname;
const parentUrl = "https://chatgpt.com/c/recovery-parent";
const campaignId = "cf-1234567890abcdef";
const campaignKey = `conversation-fabric-campaign:${campaignId}`;

function clone(value) {
  return value === undefined ? undefined : JSON.parse(JSON.stringify(value));
}

function child(id, state = "submitted", tabId = 100) {
  return {
    id,
    role: "verification",
    state,
    intent: { tab_id: tabId },
    child_conversation_url: state === "submitted" ? `https://chatgpt.com/c/${id}` : "",
    attempts: state === "submitted" ? 1 : 0,
    last_reason: "",
    last_error: ""
  };
}

function campaign(children, overrides = {}) {
  return {
    schema_version: 1,
    id: campaignId,
    state: "running",
    parent_conversation_url: parentUrl,
    parent_tab_id: 11,
    assistant_identity: "assistant-parent",
    fingerprint: "a1b2c3d4",
    created_at: new Date().toISOString(),
    children,
    results: [],
    failed_children: [],
    feedback_delivered: false,
    ...overrides
  };
}

function createHarness(initialCampaign, observationPlan = {}, reconcilePlan = {}) {
  const storage = { [campaignKey]: clone(initialCampaign) };
  const observed = [];
  const closed = [];
  let feedbackDeliveries = 0;
  const plan = Object.fromEntries(
    Object.entries(observationPlan).map(([id, values]) => [id, [...values]])
  );
  const reconcileQueues = Object.fromEntries(
    Object.entries(reconcilePlan).map(([id, values]) => [id, [...values]])
  );

  const context = vm.createContext({
    console,
    crypto: crypto.webcrypto,
    Date,
    JSON,
    Object,
    Array,
    Set,
    Map,
    Number,
    String,
    Boolean,
    Promise,
    setTimeout: (fn) => { fn(); return 1; },
    clearTimeout: () => {},
    chrome: {
      runtime: { id: "test-bridge" },
      storage: {
        local: {
          async get(key) {
            if (key === null) return clone(storage);
            return { [key]: clone(storage[key]) };
          },
          async set(patch) { Object.assign(storage, clone(patch)); },
          async remove(key) { delete storage[key]; }
        }
      }
    }
  });
  context.globalThis = context;
  context.LocalAgentConversationFabricProtocol = {
    SCHEMA_VERSION: 1,
    MAX_CHILDREN: 4,
    CAMPAIGN_ID_RE: /^cf-[0-9a-f]{16}$/,
    CHILD_ID_RE: /^[A-Za-z0-9._-]{1,64}$/,
    validateControl(value) { return value; }
  };
  Object.assign(context, {
    CONTENT_PROTOCOL_VERSION: 1,
    normalizeConversationUrl: value => String(value || ""),
    conversationId: () => "parent-id",
    async getBridgeState() {
      return {
        settings: { masterEnabled: true },
        conversations: {
          "parent-id": { id: "parent-id", url: parentUrl, preferredTabId: 11, enabled: true }
        }
      };
    },
    async conversationSpawnSha256(text) {
      return crypto.createHash("sha256").update(String(text), "utf8").digest("hex");
    },
    async reconcileConversationSpawn(intent) {
      const current = Object.values(storage[campaignKey].children)
        .find(item => item.intent.tab_id === intent.tab_id);
      const id = current?.id || "unknown";
      const queue = reconcileQueues[id] || [];
      const reason = queue.length ? queue.shift() : "spawn_submission_ambiguous";
      if (reason === "identity_discovered") {
        return {
          ok: true,
          reason,
          childConversationUrl: `https://chatgpt.com/c/${id}`
        };
      }
      return { ok: false, reason };
    },
    async observeConversationSpawnResult(intent) {
      const current = Object.values(storage[campaignKey].children)
        .find(item => item.intent.tab_id === intent.tab_id);
      const id = current?.id || "unknown";
      observed.push(id);
      const queue = plan[id] || [];
      const reason = queue.length ? queue.shift() : "child_result_ready";
      const childConversationUrl = `https://chatgpt.com/c/${id}`;
      if (reason === "child_result_ready") {
        return {
          ok: true,
          reason,
          childConversationUrl,
          assistantIdentity: `assistant-${id}`,
          assistantText: `final-${id}`,
          truncated: false
        };
      }
      const ok = reason !== "child_route_not_ready" &&
        reason !== "child_result_unavailable" &&
        reason !== "spawn_claim_conflict";
      return {
        ok,
        reason,
        ...(ok ? { childConversationUrl } : {})
      };
    },
    async closeConversationSpawnTab(intent) {
      closed.push(intent.tab_id);
      return { ok: true, reason: "child_closed" };
    },
    async runFeedbackCycle() {
      feedbackDeliveries += 1;
      const stored = clone(storage[campaignKey]);
      stored.feedback_delivered = true;
      storage[campaignKey] = stored;
      return { ok: true, reason: "sent" };
    }
  });

  vm.runInContext(
    fs.readFileSync(path.join(root, "worker_conversation_fabric.js"), "utf8"),
    context,
    { filename: "worker_conversation_fabric.js" }
  );
  vm.runInContext(
    fs.readFileSync(path.join(root, "worker_conversation_fabric_recovery.js"), "utf8"),
    context,
    { filename: "worker_conversation_fabric_recovery.js" }
  );

  return {
    context,
    storage,
    observed,
    closed,
    feedbackDeliveries: () => feedbackDeliveries,
    stored: () => clone(storage[campaignKey])
  };
}

(async () => {
  // Restart during spawning after A/B submitted, before C completes: never replay C.
  {
    const h = createHarness(campaign([
      child("a", "submitted", 101),
      child("b", "submitted", 102),
      child("c", "pending", 103)
    ], { state: "spawning" }));
    await h.context.pollConversationFabricCampaigns();
    const stored = h.stored();
    assert.equal(stored.state, "completed");
    assert.deepEqual(stored.results.map(item => item.id), ["a", "b"]);
    assert.equal(stored.failed_children.length, 1);
    assert.equal(stored.failed_children[0].id, "c");
    assert.equal(stored.failed_children[0].reason, "spawn_interrupted_before_submission");
  }

  // Restart after every child submitted but before spawning -> running checkpoint.
  {
    const h = createHarness(campaign([
      child("a", "submitted", 101),
      child("b", "submitted", 102)
    ], { state: "spawning" }));
    await h.context.pollConversationFabricCampaigns();
    const stored = h.stored();
    assert.equal(stored.state, "completed");
    assert.equal(stored.failed_children.length, 0);
    assert.deepEqual(stored.results.map(item => item.id), ["a", "b"]);
    const vaultKeys = Object.keys(h.storage).filter(key => key.startsWith("conversation-fabric-result:"));
    assert.equal(vaultKeys.length, 2, "restart recovery must vault both stable results before cleanup");
    assert.ok(vaultKeys.every(key => /^[0-9a-f]{64}$/.test(h.storage[key].text_sha256)));
  }

  // Restart during a post-click submitting checkpoint keeps the original child recoverable.
  // Lost storage.session ownership is rebuilt only after the child page proves the exact
  // transaction/request/bootstrap claim through the result observer.
  {
    const h = createHarness(campaign([
      child("a", "submitted", 101),
      child("b", "submitting", 102)
    ], { state: "spawning" }), {
      b: ["child_generating", "child_result_ready", "child_result_ready"]
    }, {
      b: ["spawn_tab_claim_mismatch"]
    });
    await h.context.pollConversationFabricCampaigns();
    const stored = h.stored();
    assert.equal(stored.state, "completed");
    assert.equal(stored.failed_children.length, 0);
    assert.deepEqual(stored.results.map(item => item.id), ["a", "b"]);
    const recovered = stored.children.find(item => item.id === "b");
    assert.equal(recovered.state, "submitted");
    assert.equal(recovered.recovered_submission_ambiguity, true);
    assert.equal(
      h.observed.filter(id => id === "b").length,
      4,
      "ambiguous child uses identity recovery, stable double result observation and final cleanup ownership proof"
    );
  }

  // child_route_not_ready is transient and recovers without delegation replay.
  {
    const h = createHarness(campaign([child("a", "submitted", 101)]), {
      a: ["child_route_not_ready", "child_result_ready", "child_result_ready"]
    });
    await h.context.pollConversationFabricCampaigns();
    assert.equal(h.stored().state, "running");
    assert.equal(h.stored().children[0].last_observation_reason, "child_route_not_ready");
    await h.context.pollConversationFabricCampaigns();
    assert.equal(h.stored().state, "completed");
    assert.equal(h.stored().results[0].assistant_text, "final-a");
  }

  // A manually closed submitted child becomes explicit retryable missing coverage.
  {
    const h = createHarness(campaign([
      child("kept", "submitted", 101),
      child("closed", "submitted", 102)
    ]), {
      kept: ["child_result_ready", "child_result_ready"],
      closed: ["spawn_tab_unavailable"]
    });
    await h.context.pollConversationFabricCampaigns();
    const stored = h.stored();
    assert.equal(stored.state, "completed");
    assert.deepEqual(stored.results.map(item => item.id), ["kept"]);
    const failed = stored.failed_children.find(item => item.id === "closed");
    assert.ok(failed);
    assert.equal(failed.reason, "spawn_tab_unavailable");
    assert.equal(failed.retryable, true);
    assert.match(h.context.conversationFabricCompletedPrompt(stored), /Retryable missing child coverage: closed/);
  }

  // A crash after the independent vault write but before the campaign copy must
  // restore the result without re-observing a now-unavailable child tab.
  {
    const h = createHarness(campaign([child("vaulted", "submitted", 101)]), {
      vaulted: ["spawn_tab_unavailable"]
    });
    h.storage[`conversation-fabric-result:${campaignId}:vaulted`] = {
      schema_version: 1,
      campaign_id: campaignId,
      child_id: "vaulted",
      role: "verification",
      parent_conversation_url: parentUrl,
      child_conversation_url: "https://chatgpt.com/c/vaulted",
      assistant_identity: "assistant-vaulted",
      captured_at: "2026-10-06T03:00:00.000Z",
      assistant_text: "final-vaulted-from-checkpoint",
      truncated: false,
      campaign_text_truncated: false,
      text_sha256: "a".repeat(64)
    };
    await h.context.pollConversationFabricCampaigns();
    const stored = h.stored();
    assert.equal(stored.state, "completed");
    assert.equal(stored.results.length, 1);
    assert.equal(stored.results[0].id, "vaulted");
    assert.equal(stored.results[0].assistant_text, "final-vaulted-from-checkpoint");
    assert.equal(stored.results[0].vault_sha256, "a".repeat(64));
    assert.ok(
      !h.observed.includes("vaulted"),
      "vault checkpoint must be hydrated before any attempt to observe the closed child"
    );
  }

  // child_result_unavailable is transient and recovers to final.
  {
    const h = createHarness(campaign([child("a", "submitted", 101)]), {
      a: ["child_result_unavailable", "child_result_ready", "child_result_ready"]
    });
    await h.context.pollConversationFabricCampaigns();
    assert.equal(h.stored().state, "running");
    await h.context.pollConversationFabricCampaigns();
    assert.equal(h.stored().state, "completed");
  }

  // Reprocessing the same explicit collect after a restart/retry may observe the
  // same pending child, but its nonterminal feedback is claimed durably only once.
  {
    const h = createHarness(campaign([child("a", "submitted", 101)]), {
      a: ["child_generating", "child_generating"]
    });
    const authority = {
      conversationUrl: parentUrl,
      fingerprint: "1a2b3c4d",
      control: {
        schema_version: 1,
        action: "collect",
        campaign_id: campaignId
      }
    };
    const first = await h.context.collectConversationFabric(authority);
    assert.equal(first.reason, "conversation_fabric_pending");
    assert.match(first.feedbackPrompt, /still running/);

    const restarted = createHarness(h.stored(), {
      a: ["child_generating"]
    });
    const repeated = await restarted.context.collectConversationFabric(authority);
    assert.equal(repeated.reason, "conversation_fabric_pending");
    assert.equal(
      repeated.feedbackPrompt,
      undefined,
      "recovery collect retry must not re-surface the same nonterminal feedback"
    );
  }

  // Terminal feedback has one durable delivery authority and is delivered at most once.
  {
    const h = createHarness(campaign([child("a", "submitted", 101)]));
    await h.context.pollConversationFabricCampaigns();
    await h.context.pollConversationFabricCampaigns();
    assert.equal(h.feedbackDeliveries(), 1);
    assert.equal(h.stored().feedback_delivered, true);
  }

  // Terminal delivery must not suppress later cleanup retries. A campaign whose
  // feedback is already delivered remains eligible while cleanup_pending is true.
  {
    const h = createHarness(campaign([child("a", "submitted", 101)], {
      state: "completed",
      cleanup_pending: true,
      feedback_delivered: true,
      completed_at: new Date().toISOString()
    }));
    await h.context.pollConversationFabricCampaigns();
    assert.deepEqual(h.closed, [101]);
    assert.equal(h.stored().cleanup_pending, false);
    assert.equal(h.stored().feedback_delivered, true);
    assert.equal(h.feedbackDeliveries(), 0, "cleanup retry must not replay terminal feedback");
  }

  // Fast sibling is durably captured before slow sibling finishes; restart keeps it.
  {
    const first = createHarness(campaign([
      child("fast", "submitted", 101),
      child("slow", "submitted", 102)
    ]), {
      fast: ["child_result_ready", "child_result_ready"],
      slow: ["child_generating"]
    });
    await first.context.pollConversationFabricCampaigns();
    assert.equal(first.stored().state, "running");
    assert.deepEqual(first.stored().results.map(item => item.id), ["fast"]);

    const restarted = createHarness(first.stored(), {
      slow: ["child_result_ready", "child_result_ready"]
    });
    await restarted.context.pollConversationFabricCampaigns();
    assert.equal(restarted.stored().state, "completed");
    assert.deepEqual(restarted.stored().results.map(item => item.id), ["fast", "slow"]);
    assert.ok(!restarted.observed.includes("fast"), "durably captured sibling must not be re-observed after restart");
  }

  // A result that becomes final immediately before timeout wins the final safe collect.
  {
    const old = new Date(Date.now() - (16 * 60 * 1000)).toISOString();
    const h = createHarness(campaign([child("a", "submitted", 101)], { created_at: old }), {
      a: ["child_result_ready", "child_result_ready"]
    });
    await h.context.pollConversationFabricCampaigns();
    assert.equal(h.stored().state, "completed");
    assert.equal(h.stored().results[0].id, "a");
    assert.notEqual(h.stored().failure, "campaign_timed_out_with_pending_children");
  }

  // A truly ambiguous child that never proves ownership remains pending until the
  // bounded campaign deadline, then fails closed without being promoted or replayed.
  {
    const old = new Date(Date.now() - (16 * 60 * 1000)).toISOString();
    const ambiguous = child("a", "submission_ambiguous", 101);
    ambiguous.ambiguity_started_at = old;
    const h = createHarness(campaign([ambiguous], { created_at: old }), {
      a: ["child_route_not_ready"]
    }, {
      a: ["spawn_submission_ambiguous"]
    });
    await h.context.pollConversationFabricCampaigns();
    const stored = h.stored();
    assert.equal(stored.state, "failed");
    assert.equal(stored.failure, "campaign_timed_out_with_pending_children");
    assert.equal(stored.children[0].state, "failed");
    assert.equal(stored.children[0].failure.reason, "spawn_submission_ambiguous_timeout");
    assert.equal(stored.results.length, 0);
  }

  console.log("Conversation Fabric recovery tests passed.");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
