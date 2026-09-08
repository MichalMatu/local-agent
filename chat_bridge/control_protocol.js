(function initLocalAgentBridgeProtocol(root, factory) {
  const api = factory();
  root.LocalAgentBridgeProtocol = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function createProtocol() {
  "use strict";

  const CONTENT_PROTOCOL_VERSION = 4;
  const MIN_INTERVAL_MINUTES = 1;
  const MAX_INTERVAL_MINUTES = 1440;
  const MIN_NEXT_SECONDS = 30;
  const MAX_NEXT_SECONDS = 86400;
  const CHAT_ID_RE = /^chat-[0-9a-f]{8}$/;
  const REPOSITORY_ID_RE = /^[A-Za-z0-9._-]{1,120}$/;
  const TASK_ID_RE = /^[A-Za-z0-9._:-]{1,160}$/;

  const COMMAND_CATALOG = Object.freeze([
    Object.freeze({ marker: "HELP", privilege: "assistant", category: "inspect", description: "Show the supported LAB command catalog." }),
    Object.freeze({ marker: "CAPABILITIES", privilege: "assistant", category: "inspect", description: "Show Bridge/runtime capabilities and supported command families." }),
    Object.freeze({ marker: "STATUS", privilege: "assistant", category: "inspect", description: "Show status of this bound conversation." }),
    Object.freeze({ marker: "DEBUG", privilege: "assistant", category: "inspect", description: "Show protocol/runtime/delivery diagnostics for this conversation." }),
    Object.freeze({ marker: "SETTINGS", privilege: "assistant", category: "inspect", description: "Show effective settings for this conversation." }),
    Object.freeze({ marker: "CHATS", privilege: "assistant", category: "inspect", description: "List configured chats; global list is restricted to the local-agent infrastructure binding." }),
    Object.freeze({ marker: "CHAT=<chat-id>", privilege: "assistant", category: "inspect", description: "Inspect one configured chat; cross-chat inspection is restricted to the local-agent infrastructure binding." }),
    Object.freeze({ marker: "RELOAD=CONTENT", privilege: "assistant", category: "maintenance", description: "Replace content scripts in this exact ChatGPT tab and re-probe protocol readiness." }),
    Object.freeze({ marker: "RELOAD=BRIDGE", privilege: "assistant", category: "maintenance", description: "Reload the unpacked extension runtime after persisting control dedupe state." }),
    Object.freeze({ marker: "RESTART=WORKER", privilege: "assistant", category: "maintenance", description: "Alias for RELOAD=BRIDGE; Chrome exposes extension reload rather than an isolated service-worker restart API." }),
    Object.freeze({ marker: "PAUSE", privilege: "assistant", category: "schedule", description: "Pause scheduled wakes for this conversation." }),
    Object.freeze({ marker: "RESUME", privilege: "assistant", category: "schedule", description: "Resume scheduled wakes for this conversation." }),
    Object.freeze({ marker: "STOP", privilege: "assistant", category: "schedule", description: "Stop this conversation and clear its interval override." }),
    Object.freeze({ marker: "NEXT=<duration>", privilege: "assistant", category: "schedule", description: "Arm a one-shot wake; compatibility range is 30 seconds through 24 hours." }),
    Object.freeze({ marker: "INTERVAL=<minutes|AUTO>", privilege: "assistant", category: "schedule", description: "Set or clear this conversation's persistent wake interval." }),
    Object.freeze({ marker: "OP:ADD=<repository-id>", privilege: "operator", category: "binding", description: "Bind the current unconfigured chat to one runtime-catalog repository. Must originate from a user-authored message." }),
    Object.freeze({ marker: "OP:REMOVE", privilege: "operator", category: "binding", description: "Remove the current chat from Bridge. Must originate from a user-authored message." }),
    Object.freeze({ marker: "OP:ENABLE", privilege: "operator", category: "schedule", description: "Enable the current configured chat. Must originate from a user-authored message." }),
    Object.freeze({ marker: "OP:DISABLE", privilege: "operator", category: "schedule", description: "Disable the current configured chat. Must originate from a user-authored message." }),
    Object.freeze({ marker: "OP:INTERVAL=<minutes|AUTO>", privilege: "operator", category: "schedule", description: "Set or clear the current chat interval. Must originate from a user-authored message." }),
    Object.freeze({ marker: "OP:RELOAD=CONTENT", privilege: "operator", category: "maintenance", description: "Replace content scripts in the current tab. Must originate from a user-authored message." }),
    Object.freeze({ marker: "OP:RELOAD=BRIDGE", privilege: "operator", category: "maintenance", description: "Reload the extension runtime. Must originate from a user-authored message." })
  ]);

  function normalizeConversationUrl(rawUrl) {
    if (!rawUrl) return "";
    try {
      const url = new URL(rawUrl);
      if (url.protocol !== "https:") return "";
      if (!["chatgpt.com", "chat.openai.com"].includes(url.hostname)) return "";

      const pathname = url.pathname.replace(/\/$/, "");
      const match = pathname.match(/(?:^|\/)c\/([^/]+)$/);
      if (!match) return "";

      return `https://chatgpt.com/c/${match[1]}`;
    } catch (_error) {
      return "";
    }
  }

  function finalControlMarker(text) {
    const source = String(text || "");
    const start = Math.max(source.lastIndexOf("[LAB:"), source.lastIndexOf("[LOCAL_AGENT_BRIDGE:"));
    if (start < 0) return null;
    const end = source.indexOf("]", start);
    if (end < 0) return null;
    const suffix = source.slice(end + 1);
    if (!/^[\s"'“”„‘’‚«»‹›.,!?;:…\-–—*_`~)\]}]*$/u.test(suffix)) return null;
    return source.slice(start, end + 1);
  }

  function markerBody(text) {
    const marker = finalControlMarker(text);
    if (!marker) return null;
    const match = marker.match(/^\[(?:LAB|LOCAL_AGENT_BRIDGE):([^\[\]\r\n]+)\]$/);
    return match ? { marker, body: match[1] } : null;
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

  function parseIntervalBody(value) {
    const parsed = parseDurationToken(value, { allowAuto: true });
    if (!parsed) return null;
    if (parsed.mode === "auto") return { mode: "auto" };
    const minutes = parsed.unit === "S" ? parsed.amount / 60 : parsed.amount;
    if (!Number.isInteger(minutes) || minutes < MIN_INTERVAL_MINUTES || minutes > MAX_INTERVAL_MINUTES) {
      return null;
    }
    return { mode: "fixed", minutes };
  }

  function parseAssistantControl(text) {
    const candidate = markerBody(text);
    if (!candidate) return null;
    const { body, marker } = candidate;

    const inspect = {
      HELP: "help",
      CAPABILITIES: "capabilities",
      STATUS: "status",
      DEBUG: "debug",
      SETTINGS: "settings",
      CHATS: "chats"
    };
    if (Object.hasOwn(inspect, body)) {
      return { action: "inspect", command: inspect[body], marker };
    }
    if (body.startsWith("CHAT=")) {
      const chatId = body.slice("CHAT=".length);
      return CHAT_ID_RE.test(chatId)
        ? { action: "inspect", command: "chat", chatId, marker }
        : null;
    }
    if (body === "RELOAD=CONTENT") return { action: "maintenance", command: "reload_content", marker };
    if (body === "RELOAD=BRIDGE" || body === "RESTART=WORKER") {
      return { action: "maintenance", command: "reload_bridge", marker };
    }

    if (body === "STOP") return { action: "stop", marker };
    if (body === "PAUSE") return { action: "pause", marker };
    if (body === "RESUME") return { action: "resume", marker };

    if (body.startsWith("INTERVAL=")) {
      const interval = parseIntervalBody(body.slice("INTERVAL=".length));
      return interval ? { action: "interval", ...interval, marker } : null;
    }

    if (body.startsWith("NEXT=")) {
      const parsed = parseDurationToken(body.slice("NEXT=".length));
      if (!parsed || parsed.mode !== "fixed") return null;
      const seconds = parsed.unit === "S" ? parsed.amount : parsed.amount * 60;
      if (!Number.isInteger(seconds) || seconds < MIN_NEXT_SECONDS || seconds > MAX_NEXT_SECONDS) {
        return null;
      }
      return { action: "next", seconds, marker };
    }

    return null;
  }

  function parseOperatorControl(text) {
    const candidate = markerBody(text);
    if (!candidate || !candidate.body.startsWith("OP:")) return null;
    const body = candidate.body.slice("OP:".length);
    const marker = candidate.marker;

    if (body.startsWith("ADD=")) {
      const repositoryId = body.slice("ADD=".length);
      return REPOSITORY_ID_RE.test(repositoryId)
        ? { action: "operator", command: "add", repositoryId, marker }
        : null;
    }
    if (body === "REMOVE") return { action: "operator", command: "remove", marker };
    if (body === "ENABLE") return { action: "operator", command: "enable", marker };
    if (body === "DISABLE") return { action: "operator", command: "disable", marker };
    if (body === "RELOAD=CONTENT") return { action: "operator", command: "reload_content", marker };
    if (body === "RELOAD=BRIDGE") return { action: "operator", command: "reload_bridge", marker };
    if (body.startsWith("INTERVAL=")) {
      const interval = parseIntervalBody(body.slice("INTERVAL=".length));
      return interval ? { action: "operator", command: "interval", ...interval, marker } : null;
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

  function controlFingerprint(conversationUrl, messageText, control, messageIdentity = "") {
    const normalizedUrl = normalizeConversationUrl(conversationUrl);
    const marker = control && typeof control.marker === "string" ? control.marker : "";
    return fnv1a32(
      `${normalizedUrl}\n${String(messageIdentity || "")}\n${String(messageText || "")}\n${marker}`
    );
  }

  return Object.freeze({
    CONTENT_PROTOCOL_VERSION,
    MIN_INTERVAL_MINUTES,
    MAX_INTERVAL_MINUTES,
    MIN_NEXT_SECONDS,
    MAX_NEXT_SECONDS,
    CHAT_ID_RE,
    REPOSITORY_ID_RE,
    TASK_ID_RE,
    COMMAND_CATALOG,
    normalizeConversationUrl,
    parseAssistantControl,
    parseOperatorControl,
    conversationId,
    controlFingerprint,
    fnv1a32
  });
});
