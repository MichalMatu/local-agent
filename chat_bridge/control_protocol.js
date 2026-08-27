(function initLocalAgentBridgeProtocol(root, factory) {
  const api = factory();
  root.LocalAgentBridgeProtocol = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function createProtocol() {
  "use strict";

  const MIN_INTERVAL_MINUTES = 1;
  const MAX_INTERVAL_MINUTES = 1440;
  const PREFIX = "[LOCAL_AGENT_BRIDGE:";

  function normalizeConversationUrl(rawUrl) {
    if (!rawUrl) return "";
    try {
      const url = new URL(rawUrl);
      if (url.protocol !== "https:") return "";
      if (!["chatgpt.com", "chat.openai.com"].includes(url.hostname)) return "";
      url.search = "";
      url.hash = "";
      return `${url.origin}${url.pathname.replace(/\/$/, "")}`;
    } catch (_error) {
      return "";
    }
  }

  function lastNonEmptyLine(text) {
    const lines = String(text || "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    return lines.length ? lines[lines.length - 1] : "";
  }

  function parseAssistantControl(text) {
    const marker = lastNonEmptyLine(text);
    if (!marker.startsWith(PREFIX) || !marker.endsWith("]")) return null;

    if (marker === "[LOCAL_AGENT_BRIDGE:STOP]") {
      return { action: "stop", marker };
    }
    if (marker === "[LOCAL_AGENT_BRIDGE:PAUSE]") {
      return { action: "pause", marker };
    }
    if (marker === "[LOCAL_AGENT_BRIDGE:RESUME]") {
      return { action: "resume", marker };
    }
    if (marker === "[LOCAL_AGENT_BRIDGE:INTERVAL=AUTO]") {
      return { action: "interval", mode: "auto", marker };
    }

    const match = marker.match(/^\[LOCAL_AGENT_BRIDGE:INTERVAL=(\d{1,4})\]$/);
    if (!match) return null;
    const minutes = Number(match[1]);
    if (
      !Number.isInteger(minutes) ||
      minutes < MIN_INTERVAL_MINUTES ||
      minutes > MAX_INTERVAL_MINUTES
    ) {
      return null;
    }
    return { action: "interval", mode: "fixed", minutes, marker };
  }

  function fnv1a32(value) {
    let hash = 0x811c9dc5;
    const text = String(value || "");
    for (let index = 0; index < text.length; index += 1) {
      hash ^= text.charCodeAt(index);
      hash = Math.imul(hash, 0x01000193);
    }
    return (hash >>> 0).toString(16).padStart(8, "0");
  }

  function controlFingerprint(conversationUrl, assistantText, control) {
    const normalizedUrl = normalizeConversationUrl(conversationUrl);
    const marker = control && typeof control.marker === "string" ? control.marker : "";
    return fnv1a32(`${normalizedUrl}\n${String(assistantText || "")}\n${marker}`);
  }

  return Object.freeze({
    MIN_INTERVAL_MINUTES,
    MAX_INTERVAL_MINUTES,
    normalizeConversationUrl,
    parseAssistantControl,
    controlFingerprint
  });
});
