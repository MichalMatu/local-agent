(() => {
  "use strict";

  const bridgeProtocol = globalThis.LocalAgentBridgeProtocol;
  const fabricProtocol = globalThis.LocalAgentConversationFabricProtocol;
  const retryPolicy = globalThis.LocalAgentBridgeContentRetry;
  if (!bridgeProtocol || !fabricProtocol || !retryPolicy) {
    throw new Error("Conversation Fabric content dependencies are unavailable");
  }
  const { CONTENT_PROTOCOL_VERSION, normalizeConversationUrl, controlFingerprint, fnv1a32 } = bridgeProtocol;
  const {
    parseConversationFabricControl,
    diagnoseConversationFabricControl,
    MAX_PROMPT_CHARS
  } = fabricProtocol;

  const existing = globalThis.__localAgentConversationFabricContent;
  if (existing?.protocolVersion === CONTENT_PROTOCOL_VERSION) return;
  try { existing?.dispose?.(); } catch (_error) {}

  const retryGate = retryPolicy.createRetryGate();
  let scanTimer = null;
  let scanInFlight = false;
  let lastScannedSignature = "";
  let lastSubmittedFingerprint = "";
  let pendingIncompleteControlSignature = "";
  const ASSISTANT_SELECTORS = [
    '[data-message-author-role="assistant"]',
    '[data-conversation-role="assistant"]'
  ];
  const USER_SELECTORS = [
    '[data-message-author-role="user"]',
    '[data-user-message-bubble]'
  ];

  function assistantIsGenerating() {
    const buttons = document.querySelectorAll(
      'button[data-testid="stop-button"], button[data-testid="composer-stop-button"]'
    );
    return Array.from(buttons).some((button) => {
      try {
        return button.checkVisibility({ checkVisibilityCSS: true, checkOpacity: true });
      } catch (_error) {
        return true;
      }
    });
  }

  function childCompletionMarker(fingerprint, childId) {
    const checksum = fnv1a32(`${fingerprint}\n${childId}`);
    return `<<<LOCAL_AGENT_CF_CHILD_COMPLETE:${fingerprint}:${childId}:${checksum}>>>`;
  }

  function decorateDelegateControl(control, fingerprint) {
    if (control?.action !== "delegate") return control;
    const children = control.children.map((child) => {
      const completionMarker = childCompletionMarker(fingerprint, child.id);
      const suffix = [
        "When the bounded task is fully complete, append the exact marker below as the final non-whitespace text of your final answer.",
        "Never emit this marker in progress, commentary, tool-use, or any intermediate response.",
        completionMarker
      ].join("\n");
      const prompt = `${child.prompt.trimEnd()}\n\n${suffix}`;
      if (prompt.length > MAX_PROMPT_CHARS) {
        throw new Error("Conversation Fabric child prompt exceeds the bounded limit after completion guard");
      }
      return { ...child, prompt };
    });
    return { ...control, children };
  }

  function cleanTurnText(turn) {
    const bodies = turn?.querySelectorAll?.('[data-content-search-unit-key$=":assistant"] [data-chatgpt-selection-message-id], [data-chatgpt-search-unit-key$=":assistant"] [data-chatgpt-selection-message-id]');
    const body = bodies?.length ? bodies[bodies.length - 1] : turn;
    const clone = body?.cloneNode?.(true);
    if (!clone || typeof clone.querySelectorAll !== "function") return "";
    clone.querySelectorAll(
      `${USER_SELECTORS.join(",")}, button, [role="button"], form, textarea, .sr-only`
    ).forEach((node) => node.remove?.());
    return String(clone.textContent || "").replace(/^\s*ChatGPT said:\s*/i, "").trim();
  }

  function latestAssistantMessage() {
    const explicit = Array.from(document.querySelectorAll(ASSISTANT_SELECTORS.join(",")));
    if (explicit.length) {
      const message = explicit[explicit.length - 1];
      const turn = message.closest?.('[data-turn-key]') || message;
      const text = cleanTurnText(turn) || String(message.innerText || message.textContent || "").trim();
      const identity = String(
        turn.getAttribute?.("data-turn-key") ||
        message.getAttribute?.("data-message-id") ||
        message.id ||
        ""
      );
      return { text, identity: identity || `assistant:${fnv1a32(text)}` };
    }
    const turns = Array.from(document.querySelectorAll('[data-turn-key]')).reverse();
    for (const turn of turns) {
      const text = cleanTurnText(turn);
      if (!text) continue;
      const identity = String(turn.getAttribute("data-turn-key") || "");
      return { text, identity: identity || `assistant:${fnv1a32(text)}` };
    }
    return null;
  }

  async function scanLatestConversationFabricControl() {
    if (assistantIsGenerating() || scanInFlight) return;
    const latest = latestAssistantMessage();
    if (!latest) return;
    const url = normalizeConversationUrl(location.href);
    if (!url) return;
    const signature = fnv1a32(`${url}\n${latest.identity}\n${latest.text}`);
    if (signature === lastScannedSignature) return;

    const diagnostic = typeof diagnoseConversationFabricControl === "function"
      ? diagnoseConversationFabricControl(latest.text)
      : {
          present: latest.text.includes("<<<LOCAL_AGENT_CF"),
          ok: Boolean(parseConversationFabricControl(latest.text)),
          reason: "control_invalid",
          control: parseConversationFabricControl(latest.text)
        };
    const control = diagnostic.ok ? diagnostic.control : null;
    if (control) pendingIncompleteControlSignature = "";
    if (!control) {
      if (!diagnostic.present) {
        pendingIncompleteControlSignature = "";
        lastScannedSignature = signature;
        retryGate.reset(signature);
        return;
      }
      if (diagnostic.reason === "control_close_missing") {
        if (pendingIncompleteControlSignature !== signature) {
          pendingIncompleteControlSignature = signature;
          retryGate.defer(signature);
          return;
        }
      } else {
        pendingIncompleteControlSignature = "";
      }
      if (!retryGate.canAttempt(signature)) return;
      // Machine diagnostics must never be injected into the parent composer. A later
      // completed assistant turn has a different signature and will still be scanned.
      lastScannedSignature = signature;
      retryGate.reset(signature);
      console.warn(
        "Local Agent Conversation Fabric control rejected:",
        diagnostic.reason,
        diagnostic.detail || ""
      );
      return;
    }
    const fingerprint = controlFingerprint(location.href, latest.text, control, latest.identity);
    if (fingerprint === lastSubmittedFingerprint) return;
    if (!retryGate.canAttempt(signature)) return;

    let requestControl;
    try {
      requestControl = decorateDelegateControl(control, fingerprint);
    } catch (error) {
      // Deterministic control diagnostics are worker/operator evidence only. Never turn
      // them into synthetic user messages in the parent conversation.
      lastScannedSignature = signature;
      retryGate.reset(signature);
      console.warn("Local Agent Conversation Fabric completion guard failed:", error);
      return;
    }

    scanInFlight = true;
    try {
      const response = await chrome.runtime.sendMessage({
        type: "bridge:conversation-fabric-control",
        conversationUrl: url,
        fingerprint,
        assistantIdentity: latest.identity,
        contentProtocolVersion: CONTENT_PROTOCOL_VERSION,
        control: requestControl
      });
      if (!response?.ok) {
        // The worker acknowledgement settles this assistant control. Rejections are
        // machine state, not user messages, so the parent composer remains untouched.
        lastSubmittedFingerprint = fingerprint;
        lastScannedSignature = signature;
        retryGate.reset(signature);
        console.warn(
          "Local Agent Conversation Fabric worker rejected control:",
          response?.reason || "conversation_fabric_rejected",
          response?.error || ""
        );
        return;
      }
      // Nonterminal and terminal Fabric status/results are delivered by the worker's
      // single journaled feedback path. The control scanner never writes the composer.
      if (response.feedbackPrompt) {
        console.info(
          "Local Agent Conversation Fabric feedback queued by worker:",
          response.reason || "conversation_fabric_feedback"
        );
      }
      lastSubmittedFingerprint = fingerprint;
      lastScannedSignature = signature;
      retryGate.reset(signature);
    } catch (error) {
      retryGate.defer(signature);
      console.warn("Local Agent Conversation Fabric control failed:", error);
    } finally {
      scanInFlight = false;
    }
  }

  function scheduleScan() {
    if (scanTimer !== null) clearTimeout(scanTimer);
    scanTimer = setTimeout(() => {
      scanTimer = null;
      scanLatestConversationFabricControl().catch((error) => console.warn(error));
    }, 600);
  }

  const observerTarget = document.body || document.documentElement;
  const observer = observerTarget ? new MutationObserver(scheduleScan) : null;
  if (observer && observerTarget) {
    observer.observe(observerTarget, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["hidden", "style", "class", "data-testid"]
    });
  }
  scheduleScan();
  const retryInterval = setInterval(() => {
    scanLatestConversationFabricControl().catch((error) => console.warn(error));
  }, 5000);

  globalThis.__localAgentConversationFabricContent = {
    protocolVersion: CONTENT_PROTOCOL_VERSION,
    dispose() {
      try { observer?.disconnect(); } catch (_error) {}
      if (canTrackComposerInput) {
        try { document.removeEventListener("input", trackComposerInput, true); } catch (_error) {}
      }
      if (scanTimer !== null) clearTimeout(scanTimer);
      clearInterval(retryInterval);
    }
  };
})();
