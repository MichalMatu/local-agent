const CONVERSATION_SPAWN_BROWSER_SCHEMA_VERSION = 1;
const CONVERSATION_SPAWN_CONTENT_PROTOCOL_VERSION = 1;
const MAX_CONVERSATION_SPAWN_BOOTSTRAP_CHARS = 32_768;
const CONVERSATION_SPAWN_TRANSACTION_RE = /^spawn-[0-9a-f]{64}$/;
const CONVERSATION_SPAWN_DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
const CONVERSATION_SPAWN_FIELDS = new Set([
  "schema_version",
  "transaction_id",
  "child_request_digest",
  "bootstrap_digest",
  "bootstrap_text",
  "tab_id"
]);
const CONVERSATION_SPAWN_MARKER = "la-spawn";

function validateConversationSpawnBrowserIntent(intent, { requireTab = false } = {}) {
  if (!intent || typeof intent !== "object" || Array.isArray(intent)) {
    throw new Error("conversation spawn browser intent must be an object");
  }
  const keys = Object.keys(intent);
  const extra = keys.filter((key) => !CONVERSATION_SPAWN_FIELDS.has(key));
  const missing = Array.from(CONVERSATION_SPAWN_FIELDS).filter((key) => !Object.hasOwn(intent, key));
  if (extra.length) {
    throw new Error(`conversation spawn browser intent contains unsupported fields: ${extra.sort().join(",")}`);
  }
  if (missing.length) {
    throw new Error(`conversation spawn browser intent is missing fields: ${missing.sort().join(",")}`);
  }
  if (intent.schema_version !== CONVERSATION_SPAWN_BROWSER_SCHEMA_VERSION) {
    throw new Error(`conversation spawn browser schema_version must be ${CONVERSATION_SPAWN_BROWSER_SCHEMA_VERSION}`);
  }
  if (!CONVERSATION_SPAWN_TRANSACTION_RE.test(String(intent.transaction_id || ""))) {
    throw new Error("conversation spawn transaction_id is invalid");
  }
  if (!CONVERSATION_SPAWN_DIGEST_RE.test(String(intent.child_request_digest || ""))) {
    throw new Error("conversation spawn child_request_digest is invalid");
  }
  if (!CONVERSATION_SPAWN_DIGEST_RE.test(String(intent.bootstrap_digest || ""))) {
    throw new Error("conversation spawn bootstrap_digest is invalid");
  }
  if (
    typeof intent.bootstrap_text !== "string" ||
    !intent.bootstrap_text.trim() ||
    intent.bootstrap_text.length > MAX_CONVERSATION_SPAWN_BOOTSTRAP_CHARS
  ) {
    throw new Error("conversation spawn bootstrap_text must be non-empty bounded text");
  }
  if (intent.tab_id !== null && (!Number.isInteger(intent.tab_id) || intent.tab_id < 1)) {
    throw new Error("conversation spawn tab_id must be a positive integer or null");
  }
  if (requireTab && !Number.isInteger(intent.tab_id)) {
    throw new Error("conversation spawn browser action requires the original tab_id");
  }
  return intent;
}

async function conversationSpawnSha256(text) {
  const bytes = new TextEncoder().encode(String(text));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
}

async function requireConversationSpawnBootstrapDigest(intent) {
  validateConversationSpawnBrowserIntent(intent);
  const actual = `sha256:${await conversationSpawnSha256(intent.bootstrap_text)}`;
  if (actual !== intent.bootstrap_digest) {
    throw new Error("conversation spawn bootstrap digest mismatch");
  }
}

function conversationSpawnMarkerUrl(transactionId) {
  if (!CONVERSATION_SPAWN_TRANSACTION_RE.test(String(transactionId || ""))) {
    throw new Error("conversation spawn transaction_id is invalid");
  }
  return `https://chatgpt.com/#${CONVERSATION_SPAWN_MARKER}=${encodeURIComponent(transactionId)}`;
}

function conversationSpawnMarkerFromUrl(rawUrl) {
  try {
    const url = new URL(String(rawUrl || ""));
    if (url.protocol !== "https:" || url.hostname !== "chatgpt.com") return "";
    const params = new URLSearchParams(url.hash.replace(/^#/, ""));
    const transactionId = params.get(CONVERSATION_SPAWN_MARKER) || "";
    return CONVERSATION_SPAWN_TRANSACTION_RE.test(transactionId) ? transactionId : "";
  } catch (_error) {
    return "";
  }
}

function conversationSpawnMarkerFromTab(tab) {
  return (
    conversationSpawnMarkerFromUrl(tab?.url) ||
    conversationSpawnMarkerFromUrl(tab?.pendingUrl)
  );
}

async function findConversationSpawnMarkerTabs(transactionId) {
  // Query all tabs: a just-created tab can expose only pendingUrl until navigation
  // commits, and a URL-filtered query can miss exactly that lost-ACK recovery window.
  const tabs = await chrome.tabs.query({});
  return tabs.filter((tab) =>
    Number.isInteger(tab.id) && conversationSpawnMarkerFromTab(tab) === transactionId
  );
}

function validateConversationSpawnTabRoute(intent, tab) {
  const rawUrl = String(tab?.url || "");
  const childUrl = normalizeConversationUrl(rawUrl);
  if (childUrl) return { ok: true, route: "child", childConversationUrl: childUrl };
  const marker = conversationSpawnMarkerFromUrl(rawUrl);
  if (marker) {
    if (marker !== intent.transaction_id) {
      return { ok: false, reason: "spawn_tab_claim_mismatch" };
    }
    return { ok: true, route: "fresh" };
  }

  // A pending marker proves ownership but not page readiness. Never classify that
  // navigation window as an unrelated route or authorize a replacement tab.
  const pendingMarker = conversationSpawnMarkerFromUrl(tab?.pendingUrl);
  if (pendingMarker) {
    return pendingMarker === intent.transaction_id
      ? { ok: false, reason: "spawn_page_not_ready" }
      : { ok: false, reason: "spawn_tab_claim_mismatch" };
  }
  return { ok: false, reason: "spawn_unexpected_route" };
}

async function probeConversationSpawnContent(tabId) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, {
      type: "bridge:spawn-capabilities",
      protocolVersion: CONVERSATION_SPAWN_CONTENT_PROTOCOL_VERSION
    }, { frameId: 0 });
    return response?.protocolVersion === CONVERSATION_SPAWN_CONTENT_PROTOCOL_VERSION
      ? response
      : { ok: false, reason: "spawn_content_protocol_mismatch" };
  } catch (error) {
    return { ok: false, reason: "spawn_content_unavailable", error: String(error) };
  }
}

async function ensureConversationSpawnContent(tabId) {
  let probe = await probeConversationSpawnContent(tabId);
  if (probe?.ok) return probe;
  if (!["spawn_content_unavailable", "spawn_content_protocol_mismatch"].includes(String(probe?.reason || ""))) {
    return probe;
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId, frameIds: [0] },
      files: ["control_protocol.js", "spawn_content.js"]
    });
  } catch (error) {
    return { ok: false, reason: "spawn_content_unavailable", error: String(error) };
  }
  return probeConversationSpawnContent(tabId);
}

async function createConversationSpawnTab(intent) {
  validateConversationSpawnBrowserIntent(intent);
  await requireConversationSpawnBootstrapDigest(intent);
  if (intent.tab_id !== null) {
    try {
      const existing = await chrome.tabs.get(intent.tab_id);
      if (existing?.id) {
        return { ok: true, reason: "tab_recovered", tabId: existing.id };
      }
    } catch (_error) {}
    throw new Error("conversation spawn original tab is unavailable; replacement requires explicit recovery");
  }

  const marked = await findConversationSpawnMarkerTabs(intent.transaction_id);
  if (marked.length > 1) {
    throw new Error("multiple tabs claim the same conversation spawn transaction");
  }
  if (marked.length === 1) {
    return { ok: true, reason: "tab_recovered", tabId: marked[0].id };
  }

  const tab = await chrome.tabs.create({
    url: conversationSpawnMarkerUrl(intent.transaction_id),
    active: false
  });
  if (!Number.isInteger(tab?.id)) {
    throw new Error("conversation spawn tab creation did not return a tab id");
  }
  return { ok: true, reason: "tab_created", tabId: tab.id };
}

async function sendConversationSpawnContentMessage(intent, type) {
  validateConversationSpawnBrowserIntent(intent, { requireTab: true });
  await requireConversationSpawnBootstrapDigest(intent);
  let tab;
  try {
    tab = await chrome.tabs.get(intent.tab_id);
  } catch (error) {
    return { ok: false, reason: "spawn_tab_unavailable", error: String(error) };
  }
  if (!tab?.id) return { ok: false, reason: "spawn_tab_unavailable" };

  const route = validateConversationSpawnTabRoute(intent, tab);
  if (!route.ok) return route;
  const ready = await ensureConversationSpawnContent(tab.id);
  if (!ready?.ok) return ready;
  try {
    const response = await chrome.tabs.sendMessage(tab.id, {
      type,
      protocolVersion: CONVERSATION_SPAWN_CONTENT_PROTOCOL_VERSION,
      transactionId: intent.transaction_id,
      childRequestDigest: intent.child_request_digest,
      bootstrapDigest: intent.bootstrap_digest,
      bootstrapText: intent.bootstrap_text
    }, { frameId: 0 });
    if (response?.protocolVersion !== CONVERSATION_SPAWN_CONTENT_PROTOCOL_VERSION) {
      return { ok: false, reason: "spawn_content_protocol_mismatch" };
    }
    if (response?.childConversationUrl) {
      const canonical = normalizeConversationUrl(response.childConversationUrl);
      if (!canonical || canonical !== response.childConversationUrl) {
        return { ok: false, reason: "spawn_child_identity_invalid" };
      }
      return { ...response, childConversationUrl: canonical };
    }
    return response || { ok: false, reason: "spawn_content_unavailable" };
  } catch (error) {
    return { ok: false, reason: "spawn_content_unavailable", error: String(error) };
  }
}

async function submitConversationSpawnBootstrap(intent) {
  return sendConversationSpawnContentMessage(intent, "bridge:spawn-bootstrap");
}

async function reconcileConversationSpawn(intent) {
  return sendConversationSpawnContentMessage(intent, "bridge:spawn-reconcile");
}
