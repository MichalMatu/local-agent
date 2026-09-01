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
  const MIN_NEXT_SECONDS = 30;
  const MAX_NEXT_SECONDS = 86400;
  const LONG_PREFIX = "[LOCAL_AGENT_BRIDGE:";
  const SHORT_PREFIX = "[LAB:";

  function normalizeConversationUrl(rawUrl) {
    if (!rawUrl) return "";
    try {
      const url = new URL(rawUrl);
      if (url.protocol !== "https:") return "";
      if (!["chatgpt.com", "chat.openai.com"].includes(url.hostname)) return "";
      url.hostname = "chatgpt.com";
      url.search = "";
      url.hash = "";
      const pathname = url.pathname.replace(/\/$/, "");
      if (!/^\/c\/[^/]+$/.test(pathname)) return "";
      return `${url.origin}${pathname}`;
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

  function parseDurationToken(token, { allowAuto = false } = {}) {
    const value = String(token || "").trim().toUpperCase();
    if (allowAuto && value === "AUTO") return { mode: "auto" };

    const match = value.match(/^(\d{1,5})(S|M)?$/);
    if (!match) return null;
    const amount = Number(match[1]);
    const unit = match[2] || "M";
    if (!Number.isInteger(amount)) return null;
    return { mode: "fixed", amount, unit };
  }

  function parseAssistantControl(text) {
    const marker = lastNonEmptyLine(text);
    const isLong = marker.startsWith(LONG_PREFIX) && marker.endsWith("]");
    const isShort = marker.startsWith(SHORT_PREFIX) && marker.endsWith("]");
    if (!isLong && !isShort) return null;

    const prefix = isLong ? LONG_PREFIX : SHORT_PREFIX;
    const body = marker.slice(prefix.length, -1);

    if (body === "STOP") return { action: "stop", marker };
    if (body === "PAUSE") return { action: "pause", marker };
    if (body === "RESUME") return { action: "resume", marker };

    if (body.startsWith("INTERVAL=")) {
      const parsed = parseDurationToken(body.slice("INTERVAL=".length), { allowAuto: true });
      if (!parsed) return null;
      if (parsed.mode === "auto") {
        return { action: "interval", mode: "auto", marker };
      }
      const minutes = parsed.unit === "S" ? parsed.amount / 60 : parsed.amount;
      if (
        !Number.isInteger(minutes) ||
        minutes < MIN_INTERVAL_MINUTES ||
        minutes > MAX_INTERVAL_MINUTES
      ) {
        return null;
      }
      return { action: "interval", mode: "fixed", minutes, marker };
    }

    if (body.startsWith("NEXT=")) {
      const parsed = parseDurationToken(body.slice("NEXT=".length));
      if (!parsed || parsed.mode !== "fixed") return null;
      const seconds = parsed.unit === "S" ? parsed.amount : parsed.amount * 60;
      if (
        !Number.isInteger(seconds) ||
        seconds < MIN_NEXT_SECONDS ||
        seconds > MAX_NEXT_SECONDS
      ) {
        return null;
      }
      return { action: "next", seconds, marker };
    }

    return null;
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

  function conversationId(conversationUrl) {
    const normalizedUrl = normalizeConversationUrl(conversationUrl);
    return normalizedUrl ? `chat-${fnv1a32(normalizedUrl)}` : "";
  }

  function controlFingerprint(conversationUrl, assistantText, control, messageIdentity = "") {
    const normalizedUrl = normalizeConversationUrl(conversationUrl);
    const marker = control && typeof control.marker === "string" ? control.marker : "";
    return fnv1a32(
      `${normalizedUrl}\n${String(messageIdentity || "")}\n${String(assistantText || "")}\n${marker}`
    );
  }

  return Object.freeze({
    MIN_INTERVAL_MINUTES,
    MAX_INTERVAL_MINUTES,
    MIN_NEXT_SECONDS,
    MAX_NEXT_SECONDS,
    normalizeConversationUrl,
    parseAssistantControl,
    conversationId,
    controlFingerprint,
    fnv1a32
  });
});
