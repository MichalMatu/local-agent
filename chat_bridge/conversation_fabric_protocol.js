(function initLocalAgentConversationFabricProtocol(root, factory) {
  const api = factory();
  root.LocalAgentConversationFabricProtocol = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createConversationFabricProtocol() {
  "use strict";

  const SCHEMA_VERSION = 1;
  const MAX_CHILDREN = 4;
  const MAX_PROMPT_CHARS = 6_000;
  const MAX_CONTROL_CHARS = 32_768;
  const CHILD_ID_RE = /^[A-Za-z0-9._-]{1,64}$/;
  const CAMPAIGN_ID_RE = /^cf-[0-9a-f]{16}$/;
  const CHILD_ROLES = new Set(["research", "implementation", "verification", "integration"]);
  const OPEN = "<<<LOCAL_AGENT_CF\n";
  const CLOSE = "\nLOCAL_AGENT_CF>>>";

  function exactKeys(value, expected) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const actual = Object.keys(value).sort();
    const wanted = [...expected].sort();
    return actual.length === wanted.length && actual.every((key, index) => key === wanted[index]);
  }

  function validateDelegate(value) {
    if (!exactKeys(value, ["schema_version", "action", "children"])) return null;
    if (value.schema_version !== SCHEMA_VERSION || value.action !== "delegate") return null;
    if (!Array.isArray(value.children) || !value.children.length || value.children.length > MAX_CHILDREN) return null;
    const seen = new Set();
    const children = [];
    for (const child of value.children) {
      if (!exactKeys(child, ["id", "role", "prompt"])) return null;
      const id = String(child.id || "");
      const role = String(child.role || "");
      const prompt = String(child.prompt || "");
      if (!CHILD_ID_RE.test(id) || seen.has(id)) return null;
      if (!CHILD_ROLES.has(role)) return null;
      if (!prompt.trim() || prompt.length > MAX_PROMPT_CHARS) return null;
      seen.add(id);
      children.push({ id, role, prompt });
    }
    return { schema_version: SCHEMA_VERSION, action: "delegate", children };
  }

  function validateCollect(value) {
    if (!exactKeys(value, ["schema_version", "action", "campaign_id"])) return null;
    const campaignId = String(value.campaign_id || "");
    if (value.schema_version !== SCHEMA_VERSION || value.action !== "collect" || !CAMPAIGN_ID_RE.test(campaignId)) return null;
    return { schema_version: SCHEMA_VERSION, action: "collect", campaign_id: campaignId };
  }

  function validateControl(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    if (value.action === "delegate") return validateDelegate(value);
    if (value.action === "collect") return validateCollect(value);
    return null;
  }

  function parseConversationFabricControl(text) {
    const source = String(text || "");
    const start = source.lastIndexOf(OPEN);
    if (start < 0) return null;
    const end = source.indexOf(CLOSE, start + OPEN.length);
    if (end < 0) return null;
    if (source.slice(end + CLOSE.length).trim()) return null;
    const raw = source.slice(start + OPEN.length, end);
    if (!raw.trim() || raw.length > MAX_CONTROL_CHARS) return null;
    let decoded;
    try {
      decoded = JSON.parse(raw);
    } catch (_error) {
      return null;
    }
    const control = validateControl(decoded);
    return control ? { ...control, marker: source.slice(start, end + CLOSE.length) } : null;
  }

  return Object.freeze({
    SCHEMA_VERSION,
    MAX_CHILDREN,
    MAX_PROMPT_CHARS,
    MAX_CONTROL_CHARS,
    CHILD_ID_RE,
    CAMPAIGN_ID_RE,
    CHILD_ROLES,
    OPEN,
    CLOSE,
    validateControl,
    parseConversationFabricControl
  });
});
