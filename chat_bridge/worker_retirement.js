const CONVERSATION_RETIREMENT_SCHEMA_VERSION = 1;
const CONVERSATION_RETIREMENT_ID_RE = /^[A-Za-z0-9._-]{1,200}$/;
const CONVERSATION_RETIREMENT_DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
const CONVERSATION_RETIREMENT_FIELDS = new Set([
  "schema_version",
  "child_request_id",
  "child_request_digest",
  "child_conversation_url",
  "terminal_digest"
]);

function validateConversationRetirementAuthority(authority) {
  if (!authority || typeof authority !== "object" || Array.isArray(authority)) {
    throw new Error("conversation retirement authority must be an object");
  }
  const keys = Object.keys(authority);
  const extra = keys.filter((key) => !CONVERSATION_RETIREMENT_FIELDS.has(key));
  const missing = Array.from(CONVERSATION_RETIREMENT_FIELDS).filter(
    (key) => !Object.hasOwn(authority, key)
  );
  if (extra.length) {
    throw new Error(
      `conversation retirement authority contains unsupported fields: ${extra.sort().join(",")}`
    );
  }
  if (missing.length) {
    throw new Error(
      `conversation retirement authority is missing fields: ${missing.sort().join(",")}`
    );
  }
  if (authority.schema_version !== CONVERSATION_RETIREMENT_SCHEMA_VERSION) {
    throw new Error(
      `conversation retirement schema_version must be ${CONVERSATION_RETIREMENT_SCHEMA_VERSION}`
    );
  }
  if (!CONVERSATION_RETIREMENT_ID_RE.test(String(authority.child_request_id || ""))) {
    throw new Error("conversation retirement child_request_id is invalid");
  }
  if (!CONVERSATION_RETIREMENT_DIGEST_RE.test(String(authority.child_request_digest || ""))) {
    throw new Error("conversation retirement child_request_digest is invalid");
  }
  if (!CONVERSATION_RETIREMENT_DIGEST_RE.test(String(authority.terminal_digest || ""))) {
    throw new Error("conversation retirement terminal_digest is invalid");
  }
  const childConversationUrl = normalizeConversationUrl(
    String(authority.child_conversation_url || "")
  );
  if (!childConversationUrl || childConversationUrl !== authority.child_conversation_url) {
    throw new Error("conversation retirement child_conversation_url must be canonical");
  }
  return {
    schemaVersion: authority.schema_version,
    childRequestId: authority.child_request_id,
    childRequestDigest: authority.child_request_digest,
    childConversationUrl,
    terminalDigest: authority.terminal_digest
  };
}

function conversationRetirementReceipt(validated, result) {
  if (!["closed", "already_closed"].includes(result)) {
    throw new Error("conversation retirement result is invalid");
  }
  return {
    schema_version: CONVERSATION_RETIREMENT_SCHEMA_VERSION,
    child_request_id: validated.childRequestId,
    child_request_digest: validated.childRequestDigest,
    child_conversation_url: validated.childConversationUrl,
    terminal_digest: validated.terminalDigest,
    result
  };
}

async function closeRetiredConversationTab(authority) {
  const validated = validateConversationRetirementAuthority(authority);
  const tabs = await chrome.tabs.query({});
  const matches = tabs.filter((tab) => {
    if (!Number.isInteger(tab?.id)) return false;
    const canonical = normalizeConversationUrl(String(tab?.url || ""));
    return canonical === validated.childConversationUrl;
  });

  if (matches.length > 1) {
    throw new Error("multiple tabs match the registered child conversation URL");
  }
  if (matches.length === 0) {
    return conversationRetirementReceipt(validated, "already_closed");
  }

  await chrome.tabs.remove(matches[0].id);
  return conversationRetirementReceipt(validated, "closed");
}
