/* Conversation Fabric lifecycle recovery hardening.
 * Loaded immediately after worker_conversation_fabric.js so the durable recovery
 * policy stays isolated from the already-stable spawn/result primitives.
 */

const CONVERSATION_FABRIC_TRANSIENT_OBSERVATION_REASONS = new Set([
  "child_route_not_ready",
  "child_result_unavailable",
  "child_result_missing",
  "child_generating",
  "child_result_unstable"
]);

const baseDelegateConversationFabric =
  typeof delegateConversationFabric === "function" ? delegateConversationFabric : null;
const baseApplyConversationFabricControl = applyConversationFabricControl;
const basePollConversationFabricCampaigns = pollConversationFabricCampaigns;

// A new delegation must not become authoritative while an older terminal campaign for
// the same parent is still waiting for durable terminal delivery. Otherwise the normal
// parent delivery path can later select the stale terminal campaign by storage order.
if (baseDelegateConversationFabric) {
  delegateConversationFabric = async function delegateConversationFabricRecovered(authority) {
    const campaignId = await conversationFabricCampaignId(authority);
    const existing = await loadConversationFabricCampaign(campaignId);
    if (existing) return baseDelegateConversationFabric(authority);

    const campaigns = await listConversationFabricCampaigns();
    const pendingTerminal = campaigns.find((campaign) =>
      campaign.parent_conversation_url === authority.conversationUrl &&
      ["completed", "failed"].includes(campaign.state) &&
      !campaign.feedback_delivered
    );
    if (pendingTerminal) {
      return {
        ok: false,
        reason: "conversation_fabric_terminal_feedback_pending",
        campaignId: pendingTerminal.id
      };
    }
    return baseDelegateConversationFabric(authority);
  };
}

function conversationFabricStoredResult(campaign, childId) {
  return (campaign.results || []).find((result) => result.id === childId) || null;
}

function conversationFabricResultRecord(child, observed) {
  const text = String(observed.assistantText || "");
  return {
    id: child.id,
    role: child.role,
    child_conversation_url: child.child_conversation_url,
    assistant_identity: String(observed.assistantIdentity || ""),
    assistant_text: text.slice(0, CONVERSATION_FABRIC_RESULT_CHARS),
    truncated: observed.truncated === true || text.length > CONVERSATION_FABRIC_RESULT_CHARS
  };
}

function conversationFabricObservationIsTransient(observed) {
  return CONVERSATION_FABRIC_TRANSIENT_OBSERVATION_REASONS.has(String(observed?.reason || ""));
}

async function recoverConversationFabricSpawningCampaign(campaign) {
  if (campaign?.state !== "spawning") return campaign;
  const submitted = [];
  const ambiguous = [];
  const failed = conversationFabricFailedChildren(campaign);
  for (const child of campaign.children || []) {
    if (child.state === "submitted" && child.child_conversation_url) {
      submitted.push(child);
      continue;
    }
    if (child.state === CONVERSATION_FABRIC_AMBIGUOUS_CHILD_STATE) {
      ambiguous.push(child);
      continue;
    }
    if (child.state === "failed") continue;
    if (child.state === "submitting") {
      // The worker may have died after the click crossed the send boundary. Preserve
      // the existing tab/intent and reconcile it later; never replay the bootstrap.
      child.state = CONVERSATION_FABRIC_AMBIGUOUS_CHILD_STATE;
      child.last_reason = "spawn_interrupted_submission_ambiguous";
      child.last_error = "service worker restarted during submission; awaiting exact child identity proof";
      child.ambiguity_started_at = child.ambiguity_started_at || new Date().toISOString();
      delete child.failure;
      ambiguous.push(child);
      continue;
    }
    const reason = child.state === "tab_created"
      ? "spawn_interrupted_after_tab_creation"
      : "spawn_interrupted_before_submission";
    child.state = "failed";
    child.failure = {
      id: child.id,
      role: child.role,
      attempt: Number(child.attempts || 0),
      reason,
      error: "service worker restarted before submission began; child was not replayed"
    };
    child.last_reason = reason;
    child.last_error = child.failure.error;
    failed.push(conversationFabricChildFailure(child));
  }
  campaign.failed_children = failed;
  campaign.partial_failure = failed.length > 0;
  campaign.recovered_spawning = true;
  if (submitted.length || ambiguous.length) {
    campaign.state = "running";
  } else {
    campaign.state = "failed";
    campaign.failure = "spawn_interrupted_without_submitted_children";
    campaign.feedback_delivered = false;
  }
  await saveConversationFabricCampaign(campaign);
  return campaign;
}

// Capture each stable child result immediately. A fast sibling therefore survives a
// service-worker restart while another child is still generating or temporarily
// unobservable. Transient observation failures remain pending until the campaign's
// existing 15-minute bound; delegation is never replayed.
collectConversationFabric = async function collectConversationFabricRecovered(authority) {
  const campaign = await loadConversationFabricCampaign(authority.control.campaign_id);
  if (!campaign) return { ok: false, reason: "conversation_fabric_campaign_missing" };
  if (campaign.parent_conversation_url !== authority.conversationUrl) {
    return { ok: false, reason: "conversation_fabric_parent_mismatch" };
  }
  if (campaign.state === "spawning") await recoverConversationFabricSpawningCampaign(campaign);
  if (campaign.state === "completed") {
    if (campaign.feedback_delivered) {
      return { ok: true, reason: "conversation_fabric_already_delivered", campaignId: campaign.id };
    }
    return {
      ok: true,
      reason: "conversation_fabric_completed",
      campaignId: campaign.id,
      feedbackPrompt: conversationFabricCompletedPrompt(campaign)
    };
  }

  const recoverableObservation = campaign.state === "failed" && campaign.children.length > 0 &&
    campaign.children.every(child => child.state === "submitted" && child.child_conversation_url);
  if (campaign.state !== "running" && !recoverableObservation) {
    return { ok: false, reason: `conversation_fabric_${campaign.state || "invalid"}` };
  }

  const failedChildren = conversationFabricFailedChildren(campaign);
  const pending = [];
  campaign.results = Array.isArray(campaign.results) ? campaign.results : [];

  for (const child of campaign.children) {
    if (child.state === "failed") continue;
    if (conversationFabricStoredResult(campaign, child.id)) continue;
    if (child.state === CONVERSATION_FABRIC_AMBIGUOUS_CHILD_STATE) {
      const recovered = await reconcileConversationFabricAmbiguousChild(child);
      if (!recovered.ok) {
        if (recovered.pending) {
          pending.push(child.id);
          await saveConversationFabricCampaign(campaign);
          continue;
        }
        const failure = {
          id: child.id,
          role: child.role,
          attempt: Number(child.attempts || 0),
          reason: recovered.reason,
          error: recovered.error
        };
        failedChildren.push(failure);
        child.state = "failed";
        child.failure = failure;
        await saveConversationFabricCampaign(campaign);
        continue;
      }
      await saveConversationFabricCampaign(campaign);
    }
    if (child.state !== "submitted" || !child.child_conversation_url) {
      const failure = {
        id: child.id,
        role: child.role,
        attempt: Number(child.attempts || 0),
        reason: `invalid_child_state_${child.state || "unknown"}`,
        error: ""
      };
      failedChildren.push(failure);
      child.state = "failed";
      child.failure = failure;
      await saveConversationFabricCampaign(campaign);
      continue;
    }

    const observed = await stableConversationFabricResult(child);
    if (observed?.ok && observed.reason === "child_result_ready") {
      campaign.results.push(conversationFabricResultRecord(child, observed));
      child.result_captured = true;
      child.result_captured_at = new Date().toISOString();
      child.last_observation_reason = "child_result_ready";
      await saveConversationFabricCampaign(campaign);
      continue;
    }
    if (conversationFabricObservationIsTransient(observed)) {
      child.observation_attempts = Number(child.observation_attempts || 0) + 1;
      child.last_observation_reason = String(observed?.reason || "child_result_unavailable");
      pending.push(child.id);
      await saveConversationFabricCampaign(campaign);
      continue;
    }

    const failure = {
      id: child.id,
      role: child.role,
      attempt: Number(child.attempts || 0),
      reason: String(observed?.reason || "conversation_fabric_child_observation_failed"),
      error: String(observed?.error || "")
    };
    failedChildren.push(failure);
    child.state = "failed";
    child.failure = failure;
    await saveConversationFabricCampaign(campaign);
  }

  campaign.failed_children = failedChildren;
  if (pending.length) {
    await saveConversationFabricCampaign(campaign);
    return {
      ok: true,
      reason: "conversation_fabric_pending",
      campaignId: campaign.id,
      pending,
      feedbackPrompt: conversationFabricPendingPrompt(campaign, pending)
    };
  }

  campaign.feedback_delivered = false;
  if (recoverableObservation) campaign.recovered_observation = true;
  campaign.partial_failure = failedChildren.length > 0;
  campaign.state = "completed";
  campaign.completed_at = new Date().toISOString();
  campaign.cleanup_pending = true;
  await saveConversationFabricCampaign(campaign);
  campaign.cleanup_pending = !await cleanupConversationFabricChildren(campaign.children);
  await saveConversationFabricCampaign(campaign);
  return {
    ok: true,
    reason: "conversation_fabric_completed",
    campaignId: campaign.id,
    feedbackPrompt: conversationFabricCompletedPrompt(campaign)
  };
};

// Direct assistant-control responses previously returned terminal feedback to the
// content script without any durable acknowledgement path. A later poll could then
// inject the same terminal campaign again. Terminal feedback is now delivered only by
// the normal worker delivery path, which persists feedback_delivered after a confirmed
// send. This gives one durable delivery authority instead of two competing paths.
applyConversationFabricControl = async function applyConversationFabricControlRecovered(message, sender) {
  const result = await baseApplyConversationFabricControl(message, sender);
  if (
    result?.ok &&
    ["conversation_fabric_completed", "conversation_fabric_already_delivered"].includes(result.reason)
  ) {
    const safe = { ...result };
    delete safe.feedbackPrompt;
    safe.feedback_deferred_to_worker = result.reason === "conversation_fabric_completed";
    return safe;
  }
  return result;
};

// A terminal prompt may still be in flight from an older direct-control path when the
// extension reloads. Its ACK is authoritative when the managed parent, campaign id and
// originating control all agree. Do not require action=collect: a repeated delegate can
// legitimately be the control that surfaced an already-completed campaign. Persist the
// receipt before returning success so later polls cannot replay the same terminal text.
acknowledgeConversationFabricFeedback = async function acknowledgeConversationFabricFeedbackRecovered(message, sender) {
  try {
    const authority = validateConversationFabricMessage(message, sender);
    if (!await conversationFabricManagedParent(authority)) {
      return { ok: false, reason: "conversation_fabric_parent_not_managed" };
    }
    const campaignId = String(message?.campaignId || "");
    const expectedCampaignId = authority.control.action === "delegate"
      ? await conversationFabricCampaignId(authority)
      : authority.control.action === "collect"
        ? String(authority.control.campaign_id || "")
        : "";
    if (!campaignId || campaignId !== expectedCampaignId) {
      return { ok: false, reason: "conversation_fabric_campaign_mismatch" };
    }
    const campaign = await loadConversationFabricCampaign(campaignId);
    if (!campaign || campaign.parent_conversation_url !== authority.conversationUrl) {
      return { ok: false, reason: "conversation_fabric_parent_mismatch" };
    }
    if (!["completed", "failed"].includes(campaign.state)) {
      return { ok: false, reason: `conversation_fabric_${campaign.state || "invalid"}` };
    }
    if (!campaign.feedback_delivered) {
      campaign.feedback_delivered = true;
      campaign.feedback_delivered_at = new Date().toISOString();
      await saveConversationFabricCampaign(campaign);
    }
    return { ok: true, reason: "conversation_fabric_feedback_acknowledged" };
  } catch (error) {
    return { ok: false, reason: "conversation_fabric_feedback_invalid", error: String(error) };
  }
};

// Recover durable spawning checkpoints without replaying any child. For running
// campaigns, collect first and only then apply the timeout. This final safe collect
// closes the race where a result becomes final immediately before the deadline.
pollConversationFabricCampaigns = async function pollConversationFabricCampaignsRecovered() {
  const state = await getBridgeState();
  if (!state.settings.masterEnabled) return;
  const campaigns = await listConversationFabricCampaigns();
  for (const listed of campaigns) {
    if (listed.feedback_delivered || conversationFabricOperations.has(listed.parent_conversation_url)) continue;
    const parent = state.conversations[conversationId(listed.parent_conversation_url)];
    if (!parent?.enabled) continue;
    await serializeConversationFabric(listed.parent_conversation_url, async () => {
      let current = await loadConversationFabricCampaign(listed.id);
      if (!current || current.feedback_delivered) return;
      if (current.state === "spawning") current = await recoverConversationFabricSpawningCampaign(current);

      const recoverableClaims = current.state === "failed" &&
        current.failure === "spawn_tab_claim_mismatch" &&
        current.children.every(child => child.state === "submitted" && child.child_conversation_url);
      if (current.state === "running" || recoverableClaims) {
        const collected = await collectConversationFabric({
          conversationUrl: parent.url,
          control: { campaign_id: current.id }
        });
        current = await loadConversationFabricCampaign(current.id);
        if (!collected.ok && current?.state !== "completed") {
          current.state = "failed";
          current.failure = collected.reason;
          await saveConversationFabricCampaign(current);
        }
      }

      current = await loadConversationFabricCampaign(listed.id);
      if (
        current?.state === "running" &&
        Date.now() - Date.parse(current.created_at) > CONVERSATION_FABRIC_TIMEOUT_MS
      ) {
        for (const child of current.children || []) {
          if (child.state !== CONVERSATION_FABRIC_AMBIGUOUS_CHILD_STATE) continue;
          child.state = "failed";
          child.failure = {
            id: child.id,
            role: child.role,
            attempt: Number(child.attempts || 0),
            reason: "spawn_submission_ambiguous_timeout",
            error: "bounded route/identity reconciliation expired without exact ownership proof"
          };
          child.last_reason = child.failure.reason;
          child.last_error = child.failure.error;
        }
        current.failed_children = (current.children || [])
          .filter((child) => child.state === "failed")
          .map(conversationFabricChildFailure);
        current.state = "failed";
        current.failure = "campaign_timed_out_with_pending_children";
        current.feedback_delivered = false;
        await saveConversationFabricCampaign(current);
      }

      const finished = await loadConversationFabricCampaign(listed.id);
      if (finished?.cleanup_pending || finished?.state === "failed") {
        finished.cleanup_pending = !await cleanupConversationFabricChildren(finished.children);
        await saveConversationFabricCampaign(finished);
      }
      if (["completed", "failed"].includes(finished?.state)) {
        await runFeedbackCycle({ conversationId: parent.id });
      }
    });
  }
};
