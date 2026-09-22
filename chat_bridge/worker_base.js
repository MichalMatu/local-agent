importScripts("control_protocol.js", "bridge_state.js");

const protocol = globalThis.LocalAgentBridgeProtocol;
const stateModel = globalThis.LocalAgentBridgeState;
const {
  CONTENT_PROTOCOL_VERSION,
  MIN_INTERVAL_MINUTES,
  MAX_INTERVAL_MINUTES,
  normalizeConversationUrl,
  parseAssistantControl,
  parseOperatorControl,
  conversationId
} = protocol;

const LEGACY_ALARM_NAME = "local-agent-chat-bridge";
const ALARM_PREFIX = "local-agent-chat:";
const RUNTIME_CACHE_MS = 30_000;
const EXHAUSTION_GUARD_VERSION = 5;
const CONTENT_PREFLIGHT_TIMEOUT_MS = 1500;
const DELIVERY_TIMEOUT_MS = 12000;
const RETRY_REASONS = new Set([
  "assistant_busy",
  "assistant_connection_interrupted",
  "assistant_connection_interrupted_unowned",
  "assistant_connection_continue_pending",
  "assistant_connection_continue_sent",
  "assistant_connection_reload_exhausted",
  "assistant_extended_thinking",
  "assistant_stalled",
  "assistant_stalled_unowned",
  "assistant_stalled_after_reload",
  "assistant_tab_reloaded",
  "assistant_tab_reload_failed",
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
