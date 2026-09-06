importScripts("control_protocol.js", "bridge_state.js");

const protocol = globalThis.LocalAgentBridgeProtocol;
const stateModel = globalThis.LocalAgentBridgeState;
const {
  MIN_INTERVAL_MINUTES,
  MAX_INTERVAL_MINUTES,
  normalizeConversationUrl,
  parseAssistantControl,
  conversationId
} = protocol;

const LEGACY_ALARM_NAME = "local-agent-chat-bridge";
const ALARM_PREFIX = "local-agent-chat:";
const RUNTIME_CACHE_MS = 30_000;
const CONTENT_PROTOCOL_VERSION = 3;
const CONTENT_PREFLIGHT_TIMEOUT_MS = 1500;
const DELIVERY_TIMEOUT_MS = 8000;
const RETRY_REASONS = new Set([
  "assistant_busy",
  "composer_not_empty",
  "composer_not_found",
  "content_script_unavailable",
  "content_script_protocol_mismatch",
  "send_button_not_ready",
  "page_not_ready",
  "wrong_conversation"
]);

let runtimeCache = null;
const runtimeRequests = new Map();
const inFlightDeliveries = new Set();
const activeDeliveries = new Map();

function clampNumber(value, fallback, minimum, maximum) {
  return stateModel.clampNumber(value, fallback, minimum, maximum);
}
