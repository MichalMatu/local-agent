/* Durable at-most-once delivery guard for terminal Conversation Fabric feedback.
 *
 * Terminal feedback is special: after chrome.tabs.sendMessage() crosses into the content
 * script, a timeout/restart can make the outcome ambiguous. Retrying an ambiguous send is
 * unsafe because ChatGPT may already have accepted the prompt. Prefer at-most-once delivery
 * for terminal Fabric feedback: persist a claim before the send, retry only when the result
 * proves that nothing was submitted, and consume surviving/ambiguous claims durably.
 */

const CONVERSATION_FABRIC_DEFINITE_NO_SEND_REASONS = new Set([
  "assistant_busy",
  "assistant_recovery_pending",
  "composer_changed",
  "composer_not_empty",
  "composer_not_found",
  "composer_write_failed",
  "content_script_protocol_mismatch",
  "content_script_unavailable",
  "delivery_cancelled",
  "page_not_ready",
  "send_button_not_ready",
  "wrong_conversation"
]);

const conversationFabricActiveTerminalClaims = new Map();
const baseConversationFabricFeedbackForParentForDeliveryGuard = conversationFabricFeedbackForParent;
const baseDeliverConversationForFabricDeliveryGuard = deliverConversation;

function conversationFabricDeliveryClaimMatches(campaign, claim) {
  return Boolean(
    campaign?.feedback_delivery_claim?.id &&
    claim?.id &&
    campaign.feedback_delivery_claim.id === claim.id
  );
}

async function conversationFabricAssumeClaimDelivered(campaign, reason) {
  const now = new Date().toISOString();
  campaign.feedback_delivered = true;
  campaign.feedback_delivered_at = campaign.feedback_delivered_at || now;
  campaign.feedback_delivery_assumed = true;
  campaign.feedback_delivery_assumed_at = campaign.feedback_delivery_assumed_at || now;
  campaign.feedback_delivery_claim = {
    ...(campaign.feedback_delivery_claim || {}),
    state: "assumed_delivered",
    reason: String(reason || "delivery_unconfirmed"),
    completed_at: now
  };
  await saveConversationFabricCampaign(campaign, { allowDeliveryClaimMutation: true });
  return campaign;
}

async function conversationFabricConfirmClaimDelivered(campaign) {
  const now = new Date().toISOString();
  campaign.feedback_delivered = true;
  campaign.feedback_delivered_at = campaign.feedback_delivered_at || now;
  campaign.feedback_delivery_claim = {
    ...(campaign.feedback_delivery_claim || {}),
    state: "confirmed",
    completed_at: now
  };
  await saveConversationFabricCampaign(campaign, { allowDeliveryClaimMutation: true });
  return campaign;
}

conversationFabricFeedbackForParent = async function conversationFabricFeedbackForParentGuarded(parentUrl) {
  const feedback = await baseConversationFabricFeedbackForParentForDeliveryGuard(parentUrl);
  if (!feedback?.campaign?.id) return feedback;

  const campaign = await loadConversationFabricCampaign(feedback.campaign.id);
  if (!campaign || campaign.feedback_delivered) return null;

  // A surviving claim means a previous worker crossed the durable at-most-once boundary.
  // The outer delivery wrapper consumes it before invoking the normal delivery path.
  if (campaign.feedback_delivery_claim?.id) return feedback;

  const claim = {
    id: crypto.randomUUID(),
    state: "claimed",
    started_at: new Date().toISOString(),
    parent_conversation_url: String(parentUrl || "")
  };
  campaign.feedback_delivery_claim = claim;
  await saveConversationFabricCampaign(campaign, { allowDeliveryClaimMutation: true });
  conversationFabricActiveTerminalClaims.set(String(parentUrl || ""), {
    campaignId: campaign.id,
    id: claim.id
  });
  return { ...feedback, deliveryClaimId: claim.id };
};

deliverConversation = async function deliverConversationWithFabricAtMostOnce(chatId, manual) {
  let parentUrl = "";
  try {
    const state = await getBridgeState();
    parentUrl = String(state.conversations?.[chatId]?.url || "");
  } catch (_error) {}

  // If a claim survived a worker restart, do not call the normal delivery path at all.
  // We cannot distinguish "crashed before submit" from "submitted but ACK was lost";
  // at-most-once semantics deliberately prefer a missed terminal notification to replay spam.
  if (parentUrl) {
    const pending = await baseConversationFabricFeedbackForParentForDeliveryGuard(parentUrl);
    if (pending?.campaign?.id) {
      const campaign = await loadConversationFabricCampaign(pending.campaign.id);
      if (campaign?.feedback_delivery_claim?.id && !campaign.feedback_delivered) {
        await conversationFabricAssumeClaimDelivered(campaign, "delivery_claim_recovered_after_restart");
        return {
          ok: true,
          reason: "conversation_fabric_feedback_assumed_delivered",
          status: "sent",
          conversationId: chatId,
          bridgeMode: "wake"
        };
      }
    }
  }

  const result = await baseDeliverConversationForFabricDeliveryGuard(chatId, manual);
  const activeClaim = parentUrl ? conversationFabricActiveTerminalClaims.get(parentUrl) : null;
  if (!activeClaim) return result;
  conversationFabricActiveTerminalClaims.delete(parentUrl);

  const campaign = await loadConversationFabricCampaign(activeClaim.campaignId);
  if (!campaign || !conversationFabricDeliveryClaimMatches(campaign, activeClaim)) return result;

  if (result?.ok) {
    await conversationFabricConfirmClaimDelivered(campaign);
    return result;
  }

  const reason = String(result?.reason || result?.status || "delivery_unconfirmed");
  if (CONVERSATION_FABRIC_DEFINITE_NO_SEND_REASONS.has(reason)) {
    delete campaign.feedback_delivery_claim;
    delete campaign.feedback_delivery_assumed;
    delete campaign.feedback_delivery_assumed_at;
    await saveConversationFabricCampaign(campaign, { allowDeliveryClaimMutation: true });
    return result;
  }

  await conversationFabricAssumeClaimDelivered(campaign, reason);
  return result;
};
