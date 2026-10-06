(() => {
  "use strict";

  const protocol = globalThis.LocalAgentBridgeProtocol;
  if (!protocol) throw new Error("Local Agent Chat Bridge protocol is unavailable");
  const { normalizeConversationUrl } = protocol;
  const SPAWN_PROTOCOL_VERSION = 2;
  const MAX_RESULT_CHARS = 24_000;
  const TRANSACTION_RE = /^spawn-[0-9a-f]{64}$/;
  const DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
  const COMPLETION_MARKER_RE = /^<<<LOCAL_AGENT_CF_CHILD_COMPLETE:[0-9a-f]{8}:[A-Za-z0-9._-]{1,64}:[0-9a-f]{8}>>>$/;
  const CLAIM_PREFIX = "local-agent:conversation-spawn:";

  const existing = globalThis.__localAgentConversationSpawnResultContent;
  // Reinstall the read-only listener after extension reload even when its wire
  // protocol is unchanged: the previous extension context may be detached.
  try { existing?.dispose?.(); } catch (_error) {}

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

  function readClaim(transactionId) {
    try {
      const raw = sessionStorage.getItem(`${CLAIM_PREFIX}${transactionId}`);
      if (!raw) return null;
      const value = JSON.parse(raw);
      return value && typeof value === "object" && !Array.isArray(value) ? value : null;
    } catch (_error) {
      return null;
    }
  }

  function validateMessage(message) {
    if (message?.protocolVersion !== SPAWN_PROTOCOL_VERSION) return null;
    const transactionId = String(message.transactionId || "");
    const childRequestDigest = String(message.childRequestDigest || "");
    const bootstrapDigest = String(message.bootstrapDigest || "");
    const completionMarker = String(message.completionMarker || "");
    if (!TRANSACTION_RE.test(transactionId)) return null;
    if (!DIGEST_RE.test(childRequestDigest) || !DIGEST_RE.test(bootstrapDigest)) return null;
    if (!COMPLETION_MARKER_RE.test(completionMarker)) return null;
    const claim = readClaim(transactionId);
    if (
      !claim ||
      claim.transactionId !== transactionId ||
      claim.childRequestDigest !== childRequestDigest ||
      claim.bootstrapDigest !== bootstrapDigest
    ) {
      return null;
    }
    const childConversationUrl = normalizeConversationUrl(location.href);
    if (!childConversationUrl) return null;
    return { transactionId, childRequestDigest, bootstrapDigest, completionMarker, childConversationUrl };
  }

  function cleanAssistantText(element) {
    const bodies = element?.querySelectorAll?.('[data-content-search-unit-key$=":assistant"] [data-chatgpt-selection-message-id], [data-chatgpt-search-unit-key$=":assistant"] [data-chatgpt-selection-message-id]');
    const body = bodies?.length ? bodies[bodies.length - 1] : element;
    const clone = body?.cloneNode?.(true);
    if (!clone || typeof clone.querySelectorAll !== "function") return "";
    clone.querySelectorAll(
      '[data-message-author-role="user"], [data-conversation-role="user"], [data-user-message-bubble], button, [role="button"], form, textarea, .sr-only'
    ).forEach((node) => node.remove?.());
    return String(clone.textContent || "").replace(/^\s*ChatGPT said:\s*/i, "").trim();
  }

  function latestAssistantSnapshot() {
    const explicit = Array.from(document.querySelectorAll(
      '[data-message-author-role="assistant"], [data-conversation-role="assistant"]'
    ));
    if (explicit.length) {
      const message = explicit[explicit.length - 1];
      const turn = message.closest?.('[data-turn-key]') || message;
      // Current ChatGPT role markers can be accessibility headings; the body is
      // a sibling in the same logical turn, so read the sanitized whole turn.
      const text = cleanAssistantText(turn);
      const identity = String(
        turn.getAttribute?.("data-turn-key") ||
        message.getAttribute?.("data-message-id") ||
        ""
      );
      return { text, identity };
    }

    const turns = Array.from(document.querySelectorAll('[data-turn-key]')).reverse();
    for (const turn of turns) {
      const text = cleanAssistantText(turn);
      if (!text) continue;
      return {
        text,
        identity: String(turn.getAttribute("data-turn-key") || "")
      };
    }
    return { text: "", identity: "" };
  }

  async function sha256(text) {
    const bytes = new TextEncoder().encode(String(text));
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
  }

  async function observeResult(message) {
    const validated = validateMessage(message);
    if (!validated) {
      return { ok: false, reason: "spawn_claim_conflict" };
    }
    if (assistantIsGenerating()) {
      return {
        ok: true,
        reason: "child_generating",
        childConversationUrl: validated.childConversationUrl
      };
    }
    const snapshot = latestAssistantSnapshot();
    if (!snapshot.text) {
      return {
        ok: true,
        reason: "child_result_missing",
        childConversationUrl: validated.childConversationUrl
      };
    }

    const visibleText = snapshot.text.trim();
    if (!visibleText.endsWith(validated.completionMarker)) {
      // A paused tool/reasoning turn may expose stable assistant text while no Stop
      // control is visible. Absence of Stop is therefore not terminal evidence.
      return {
        ok: true,
        reason: "child_generating",
        childConversationUrl: validated.childConversationUrl
      };
    }

    const completedText = visibleText.slice(0, -validated.completionMarker.length).trimEnd();
    if (!completedText.trim()) {
      return {
        ok: true,
        reason: "child_result_missing",
        childConversationUrl: validated.childConversationUrl
      };
    }
    const truncated = completedText.length > MAX_RESULT_CHARS;
    const text = truncated ? completedText.slice(0, MAX_RESULT_CHARS) : completedText;
    const identity = snapshot.identity || `assistant:${await sha256(`${validated.childConversationUrl}\n${text}`)}`;
    return {
      ok: true,
      reason: "child_result_ready",
      childConversationUrl: validated.childConversationUrl,
      assistantIdentity: identity,
      assistantText: text,
      truncated
    };
  }

  const listener = (message, _sender, sendResponse) => {
    if (message?.type !== "bridge:spawn-result") return false;
    observeResult(message)
      .then((response) => sendResponse({ ...response, protocolVersion: SPAWN_PROTOCOL_VERSION }))
      .catch((error) => sendResponse({
        ok: false,
        reason: "child_result_unavailable",
        error: String(error),
        protocolVersion: SPAWN_PROTOCOL_VERSION
      }));
    return true;
  };

  chrome.runtime.onMessage.addListener(listener);
  globalThis.__localAgentConversationSpawnResultContent = {
    protocolVersion: SPAWN_PROTOCOL_VERSION,
    dispose() {
      try { chrome.runtime.onMessage.removeListener(listener); } catch (_error) {}
    }
  };
})();