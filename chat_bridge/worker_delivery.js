async function conversationFabricParentReserved(parentUrl) {
  if (typeof listConversationFabricCampaigns !== "function") return false;
  const campaigns = await listConversationFabricCampaigns();
  return campaigns.some((campaign) =>
    campaign?.parent_conversation_url === parentUrl &&
    ["spawning", "running"].includes(campaign?.state)
  );
}

async function runFeedbackCycle({ conversationId: chatId, manual = false, promptOverride = "" } = {}) {
  if (inFlightDeliveries.has(chatId)) return { ok: false, reason: "delivery_in_progress" };
  inFlightDeliveries.add(chatId);
  try {
    return await deliverConversation(chatId, manual, { promptOverride });
  } finally {
    inFlightDeliveries.delete(chatId);
    activeDeliveries.delete(chatId);
  }
}

async function conversationFabricTerminalFeedbackAlreadySubmitted(tabId, expectedUrl, prompt) {
  try {
    const executions = await chrome.scripting.executeScript({
      target: { tabId, frameIds: [0] },
      args: [String(expectedUrl || ""), String(prompt || "")],
      func: (expectedUrlValue, expectedPrompt) => {
        const normalizeUrl = (value) => {
          try {
            const parsed = new URL(String(value || ""), location.href);
            if (!["https://chatgpt.com", "https://chat.openai.com"].includes(parsed.origin)) return "";
            const match = parsed.pathname.match(/^\/c\/([^/?#]+)/);
            return match ? `${parsed.origin}/c/${match[1]}` : "";
          } catch (_error) {
            return "";
          }
        };
        const expectedConversation = normalizeUrl(expectedUrlValue);
        if (!expectedConversation || normalizeUrl(location.href) !== expectedConversation) return false;

        const seenTurns = new Set();
        const userMessages = [];
        const selectors = '[data-message-author-role="user"], [data-user-message-bubble]';
        for (const message of document.querySelectorAll(selectors)) {
          const turn = message.closest?.('[data-turn-key]') || message;
          if (seenTurns.has(turn)) continue;
          seenTurns.add(turn);
          userMessages.push(message);
        }
        if (!userMessages.length) return false;
        const normalizeText = (text) => String(text || "").trim().replace(/\s+/g, " ");
        const normalizedExpectedPrompt = normalizeText(expectedPrompt);
        if (!normalizedExpectedPrompt) return false;
        return userMessages.some((message) =>
          normalizeText(message.innerText || message.textContent) === normalizedExpectedPrompt
        );
      }
    });
    return executions?.[0]?.result === true;
  } catch (_error) {
    return false;
  }
}

async function deliverConversation(chatId, manual, { promptOverride = "" } = {}) {
  const state = await getBridgeState();
  const conversation = state.conversations[chatId];
  if (!conversation) return { ok: false, reason: "conversation_not_found" };
  if (!stateModel.isTransportReady(conversation)) {
    await updateConversationStatus(chatId, {
      enabled: false,
      lastStatus: "conversation_url_required",
      nextRunAt: null
    }, conversation.generation);
    await clearConversationAlarm(chatId, conversation.generation);
    return { ok: false, reason: "conversation_url_required" };
  }
  if (conversation.lastStatus === "conversation_exhausted") {
    await clearConversationAlarm(chatId, conversation.generation);
    return { ok: false, reason: "conversation_exhausted" };
  }
  if ((!state.settings.masterEnabled || !conversation.enabled) && !manual) {
    await clearConversationAlarm(chatId, conversation.generation);
    return { ok: false, reason: "disabled" };
  }

  const runtime = await loadRuntimeConfig(state, conversation);
  if (runtime.source === "unavailable") {
    await updateConversationStatus(chatId, {
      lastStatus: "runtime_unavailable",
      lastRuntimeSource: runtime.source
    }, conversation.generation);
    if (!manual) await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes, conversation.generation);
    return { ok: false, reason: "runtime_unavailable", runtime };
  }

  const explicitPrompt = typeof promptOverride === "string" ? promptOverride.trim() : "";
  const fabricFeedback = explicitPrompt
    ? null
    : await conversationFabricFeedbackForParent(conversation.url);
  if (!explicitPrompt && !fabricFeedback && await conversationFabricParentReserved(conversation.url)) {
    const runAt = new Date().toISOString();
    await updateConversationStatus(chatId, {
      lastRunAt: runAt,
      lastStatus: "conversation_fabric_parent_reserved",
      lastRuntimeSource: runtime.source
    }, conversation.generation);
    if (!manual) {
      await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes, conversation.generation);
    }
    return {
      ok: false,
      reason: "conversation_fabric_parent_reserved",
      status: "conversation_fabric_parent_reserved",
      runtime,
      conversationId: chatId,
      bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
    };
  }
  const runAt = new Date().toISOString();
  const tab = await findConversationTab(conversation);
  if (!tab?.id) {
    await updateConversationStatus(chatId, {
      lastRunAt: runAt,
      lastStatus: "conversation_tab_missing",
      lastRuntimeSource: runtime.source
    }, conversation.generation);
    if (!manual) await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes, conversation.generation);
    return { ok: false, reason: "conversation_tab_missing", runtime };
  }
  if (conversation.preferredTabId !== tab.id) {
    await updateConversationStatus(chatId, { preferredTabId: tab.id }, conversation.generation);
  }

  const contentReady = await ensureContentScript(tab, conversation.url);
  if (!contentReady.ok) {
    const status = String(contentReady.reason || "content_script_unavailable");
    await updateConversationStatus(chatId, {
      lastRunAt: runAt,
      lastStatus: status,
      lastRuntimeSource: runtime.source
    }, conversation.generation);
    if (!manual) {
      await scheduleAfterMinutes(
        chatId,
        RETRY_REASONS.has(status) ? runtime.busyRetryMinutes : runtime.intervalMinutes,
        conversation.generation
      );
    }
    return {
      ...contentReady,
      runtime,
      status,
      conversationId: chatId,
      bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
    };
  }

  if (contentReady.recoverableAssistantError) {
    const recovery = await kickAssistantRecovery(tab.id, conversation.url);
    if (!recovery.ok || recovery.recoverableAssistantError) {
      const status = "assistant_recovery_pending";
      await updateConversationStatus(chatId, {
        lastRunAt: runAt,
        lastStatus: status,
        lastRuntimeSource: runtime.source
      }, conversation.generation);
      if (!manual) {
        await scheduleAfterMinutes(chatId, runtime.busyRetryMinutes, conversation.generation);
      }
      return {
        ok: false,
        reason: status,
        status,
        recovery,
        runtime,
        conversationId: chatId,
        bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
      };
    }
  }

  const prompt = explicitPrompt || fabricFeedback?.prompt || (conversation.bootstrapPending
    ? buildBootstrapPrompt(runtime, conversation)
    : buildWakePrompt(runtime, conversation));
  const deliveryId = crypto.randomUUID();
  const active = {
    id: deliveryId,
    tabId: tab.id,
    generation: conversation.generation,
    bindingRevision: conversation.bindingRevision,
    manual,
    assistantBaseline: ""
  };
  const recoverBridgePrompt = ["delivery_unconfirmed", "send_button_not_ready"].includes(
    conversation.lastStatus
  );

  let response;
  let deliveryTimeout;
  const recoveredTerminalFeedback = Boolean(
    fabricFeedback &&
    ["delivery_unconfirmed", "send_button_not_ready"].includes(conversation.lastStatus) &&
    await conversationFabricTerminalFeedbackAlreadySubmitted(tab.id, conversation.url, prompt)
  );
  if (recoveredTerminalFeedback) {
    response = {
      ok: true,
      reason: "already_sent",
      protocolVersion: CONTENT_PROTOCOL_VERSION
    };
  } else {
    activeDeliveries.set(chatId, active);
    try {
      response = await Promise.race([
        chrome.tabs.sendMessage(tab.id, {
          type: "bridge:feedback",
          prompt,
          expectedUrl: conversation.url,
          deliveryId,
          recoverBridgePrompt,
          bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
        }, { frameId: 0 }),
        new Promise((resolve) => {
          deliveryTimeout = setTimeout(
            () => resolve({ ok: false, reason: "delivery_unconfirmed", protocolVersion: CONTENT_PROTOCOL_VERSION }),
            DELIVERY_TIMEOUT_MS
          );
        })
      ]);
    } catch (error) {
      response = definitelyNoContentReceiver(error)
        ? { ok: false, reason: "content_script_unavailable", protocolVersion: CONTENT_PROTOCOL_VERSION, error: String(error) }
        : { ok: false, reason: "delivery_unconfirmed", protocolVersion: CONTENT_PROTOCOL_VERSION, error: String(error) };
    } finally {
      clearTimeout(deliveryTimeout);
      if (activeDeliveries.get(chatId)?.id === deliveryId) activeDeliveries.delete(chatId);
    }
  }

  if (response?.protocolVersion !== CONTENT_PROTOCOL_VERSION) {
    response = { ok: false, reason: "content_script_protocol_mismatch", protocolVersion: response?.protocolVersion };
  }
  const status = response?.ok ? "sent" : String(response?.reason || "delivery_unconfirmed");
  if (response?.ok && fabricFeedback) {
    const campaign = await loadConversationFabricCampaign(fabricFeedback.campaign.id);
    if (campaign) {
      campaign.feedback_delivered = true;
      campaign.feedback_delivered_at = campaign.feedback_delivered_at || new Date().toISOString();
      await saveConversationFabricCampaign(campaign);
    }
  }
  await mutateState((current) => {
    const latest = current.conversations[chatId];
    if (!latest || latest.bindingRevision !== conversation.bindingRevision) return current;
    if (response?.ok) {
      if (!explicitPrompt) latest.bootstrapPending = false;
      latest.assistantBaseline = active.assistantBaseline || latest.assistantBaseline || "";
    }
    if (latest.generation === conversation.generation) {
      latest.lastRunAt = runAt;
      latest.lastStatus = status;
      latest.lastRuntimeSource = runtime.source;
    }
    return current;
  });

  if (!manual) {
    const delay = response?.ok
      ? runtime.intervalMinutes
      : status === "delivery_unconfirmed"
        ? runtime.intervalMinutes
        : RETRY_REASONS.has(status)
          ? runtime.busyRetryMinutes
          : runtime.intervalMinutes;
    await scheduleAfterMinutes(chatId, delay, conversation.generation);
  }

  return {
    ...response,
    runtime,
    status,
    conversationId: chatId,
    bridgeMode: conversation.bootstrapPending ? "bootstrap" : "wake"
  };
}