"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const protocol = require("./control_protocol.js");
const runtimeExample = require("./runtime.example.json");
const { createHarness } = require("./worker_test_harness.js");

const parentUrl = "https://chatgpt.com/c/operator-observability";
const parentId = protocol.conversationId(parentUrl);
const campaignId = "cf-0123456789abcdef";

function operatorStatus() {
  return {
    schema_version: 1,
    updated_at: "2026-10-06T04:30:00+00:00",
    daemon: {
      daemon_version: "4.20.6",
      self_revision: "ab3306e267fb99184dd1486c678af3f3ddfd490e",
      execution_model: "parallel_repository_supervisor",
      supervisor_pid: 123,
      max_parallel_workers: 4,
      repository_count: 10
    },
    operator: {
      enabled: true,
      configured: true,
      running: true,
      configuration_error: null,
      active_request: {
        request_id: "obs-request",
        workflow_id: "workflow-observability",
        parent_conversation_url: parentUrl,
        repository_ids: ["local-agent"],
        children_total: 2
      },
      active_request_error: null,
      result_publish_pending: false
    },
    dedupe: {
      evidence_scope: "bounded_local_state",
      suppressed_count: 3,
      suppression_reasons: { queued_duplicate: 2, recent_duplicate: 1 },
      rejected_count: 1,
      rejection_reasons: { dedupe_intent_conflict: 1 },
      reconciled_count: 1,
      reconciliation_reasons: { published_run_after_claim_release: 1 },
      observed_run_records: 5,
      observed_receipt_records: 2,
      scan_truncated: false
    }
  };
}

(async () => {
  let runtimeFetches = 0;
  let statusFetches = 0;
  const statusUrl =
    "https://raw.githubusercontent.com/MichalMatu/host-ops/agent-control/.agent/status/operator.json";
  const storage = {
    [`conversation-fabric-campaign:${campaignId}`]: {
      schema_version: 1,
      id: campaignId,
      parent_conversation_url: parentUrl,
      state: "completed",
      created_at: "2026-10-06T04:20:00.000Z",
      completed_at: "2026-10-06T04:25:00.000Z",
      feedback_delivered: false,
      cleanup_pending: true,
      children: [
        { id: "research", role: "research", state: "submitted" },
        {
          id: "verify",
          role: "verification",
          state: "failed",
          failure: {
            id: "verify",
            role: "verification",
            reason: "operator_retired",
            error: "retired",
            retryable: true
          }
        }
      ],
      results: [
        {
          id: "research",
          role: "research",
          assistant_text: "captured",
          captured_at: "2026-10-06T04:24:00.000Z"
        }
      ],
      failed_children: [
        {
          id: "verify",
          role: "verification",
          reason: "operator_retired",
          error: "retired",
          retryable: true
        }
      ],
      partial_failure: true
    },
    [`conversation-fabric-result:${campaignId}:research`]: {
      schema_version: 1,
      campaign_id: campaignId,
      child_id: "research",
      role: "research",
      parent_conversation_url: parentUrl,
      child_conversation_url: "https://chatgpt.com/c/child-research",
      captured_at: "2026-10-06T04:24:00.000Z",
      assistant_text: "captured",
      text_sha256: "sha256:fixture"
    }
  };

  const h = createHarness({
    storage,
    fetch: async (url) => {
      const target = String(url);
      if (target.startsWith(statusUrl)) {
        statusFetches += 1;
        return { ok: true, async json() { return operatorStatus(); } };
      }
      runtimeFetches += 1;
      return {
        ok: true,
        async json() {
          return {
            ...runtimeExample,
            bootstrap_prompt: "BOOTSTRAP",
            wake_prompt: "WAKE",
            operator_status_url: statusUrl
          };
        }
      };
    }
  });

  const first = await h.sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(first.operatorStatus.available, true, JSON.stringify(first.operatorStatus));
  assert.equal(first.operatorStatus.source, "remote");
  assert.equal(first.operatorStatus.status.operator.running, true);
  assert.equal(first.operatorStatus.status.operator.active_request.workflow_id, "workflow-observability");
  assert.equal(first.operatorStatus.status.dedupe.suppressed_count, 3);
  assert.equal(first.bridgeInfo.extensionVersion, "0.7.0");
  assert.equal(first.bridgeInfo.contentProtocolVersion, h.CONTENT_PROTOCOL_VERSION);

  const fabric = first.fabricStatus[parentId];
  assert.ok(fabric, JSON.stringify(first.fabricStatus));
  assert.equal(fabric.currentCampaign.campaignId, campaignId);
  assert.equal(fabric.currentCampaign.state, "completed");
  assert.equal(fabric.currentCampaign.childCount, 2);
  assert.equal(fabric.currentCampaign.capturedResultCount, 1);
  assert.equal(fabric.currentCampaign.feedbackState, "pending");
  assert.equal(fabric.currentCampaign.cleanupPending, true);
  assert.deepEqual(
    Array.from(fabric.currentCampaign.retryableChildIds),
    ["verify"]
  );

  const second = await h.sendRuntimeMessage({ type: "bridge:get-state" });
  assert.equal(second.operatorStatus.available, true);
  assert.equal(statusFetches, 1, "operator status must use its bounded cache");
  assert.equal(runtimeFetches, 1, "runtime config must remain cached");

  await assert.rejects(
    h.evaluate("Promise.resolve().then(() => sanitizeOperatorStatusUrl('http://127.0.0.1/status.json'))"),
    /raw\.githubusercontent\.com/
  );
  assert.equal(
    h.evaluate("sanitizeOperatorStatusUrl('')"),
    "",
    "operator status remains optional for runtime schema v3"
  );

  const popup = fs.readFileSync(path.join(__dirname, "popup.js"), "utf8");
  const popupHtml = fs.readFileSync(path.join(__dirname, "popup.html"), "utf8");
  assert.match(popup, /function renderOperatorStatus/);
  assert.match(popup, /capturedResultCount/);
  assert.match(popup, /reconciled_count/);
  assert.match(popup, /bridgeInfo/);
  assert.match(popupHtml, /id="operatorStatusTitle"/);
  assert.match(popupHtml, /id="operatorFeedback"/);
  assert.match(popupHtml, /id="operatorDedupe"/);

  console.log("Unified operator observability tests passed.");
})().catch((error) => {
  console.error(error?.stack || error);
  process.exitCode = 1;
});
