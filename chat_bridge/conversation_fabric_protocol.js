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
  const OPEN = "<<<LOCAL_AGENT_CF";
  const CLOSE = "LOCAL_AGENT_CF>>>";

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
      if ([child.id, child.role, child.prompt].some(field => typeof field !== "string")) return null;
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

  function validateInspect(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return null;
    const keys = Object.keys(value).sort();
    const recentOnly = keys.length === 2 &&
      keys[0] === "action" && keys[1] === "schema_version";
    const campaignScoped = exactKeys(value, ["schema_version", "action", "campaign_id"]);
    const childScoped = exactKeys(value, ["schema_version", "action", "campaign_id", "child_id"]);
    if (!recentOnly && !campaignScoped && !childScoped) return null;
    if (value.schema_version !== SCHEMA_VERSION || value.action !== "inspect") return null;
    if (recentOnly) return { schema_version: SCHEMA_VERSION, action: "inspect" };
    const campaignId = String(value.campaign_id || "");
    if (!CAMPAIGN_ID_RE.test(campaignId)) return null;
    if (!childScoped) return { schema_version: SCHEMA_VERSION, action: "inspect", campaign_id: campaignId };
    const childId = String(value.child_id || "");
    if (!CHILD_ID_RE.test(childId)) return null;
    return {
      schema_version: SCHEMA_VERSION,
      action: "inspect",
      campaign_id: campaignId,
      child_id: childId
    };
  }

  function validateRetire(value) {
    if (!exactKeys(value, ["schema_version", "action", "campaign_id", "child_id"])) return null;
    const campaignId = String(value.campaign_id || "");
    const childId = String(value.child_id || "");
    if (
      value.schema_version !== SCHEMA_VERSION ||
      value.action !== "retire" ||
      !CAMPAIGN_ID_RE.test(campaignId) ||
      !CHILD_ID_RE.test(childId)
    ) return null;
    return {
      schema_version: SCHEMA_VERSION,
      action: "retire",
      campaign_id: campaignId,
      child_id: childId
    };
  }

  function normalizeControl(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return value;
    if (value.control_close !== true) return value;
    const { control_close: _ignoredControlClose, ...canonical } = value;
    return canonical;
  }

  function validateControl(value) {
    const canonical = normalizeControl(value);
    if (!canonical || typeof canonical !== "object" || Array.isArray(canonical)) return null;
    if (canonical.action === "delegate") return validateDelegate(canonical);
    if (canonical.action === "collect") return validateCollect(canonical);
    if (canonical.action === "inspect") return validateInspect(canonical);
    if (canonical.action === "retire") return validateRetire(canonical);
    return null;
  }

  function schemaDiagnosticDetail(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return "The control payload must be one JSON object.";
    }
    const action = String(value.action || "");
    const describe = (name, allowedKeys) => {
      const unexpected = Object.keys(value).filter((key) => !allowedKeys.includes(key)).sort();
      const suffix = unexpected.length ? `; unexpected keys: ${unexpected.join(", ")}` : "";
      return `${name} JSON keys must be exactly ${allowedKeys.join(", ")}${suffix}. The literal closing delimiter LOCAL_AGENT_CF>>> belongs after the JSON object and is not a JSON field.`;
    };
    if (action === "delegate") return describe("delegate", ["schema_version", "action", "children"]);
    if (action === "collect") return describe("collect", ["schema_version", "action", "campaign_id"]);
    if (action === "inspect") {
      return "inspect JSON may contain only schema_version, action, optional campaign_id, and optional child_id. The literal closing delimiter LOCAL_AGENT_CF>>> belongs after the JSON object and is not a JSON field.";
    }
    if (action === "retire") return describe("retire", ["schema_version", "action", "campaign_id", "child_id"]);
    return "Supported actions are delegate, collect, inspect, and retire. Use only the keys defined for the selected action.";
  }

  function diagnoseConversationFabricControl(text) {
    const source = String(text || "");
    const start = source.lastIndexOf(OPEN);
    if (start < 0) return { present: false, ok: false, reason: "control_absent" };

    const end = source.indexOf(CLOSE, start + OPEN.length);
    if (end < 0) {
      return {
        present: true,
        ok: false,
        reason: "control_close_missing",
        detail: "Append the literal closing delimiter LOCAL_AGENT_CF>>> after the JSON object. Do not add a control_close field to the JSON."
      };
    }
    if (source.slice(end + CLOSE.length).trim()) {
      return { present: true, ok: false, reason: "control_not_terminal" };
    }

    const raw = source.slice(start + OPEN.length, end);
    if (!raw.trim()) return { present: true, ok: false, reason: "control_empty" };
    if (raw.length > MAX_CONTROL_CHARS) {
      return { present: true, ok: false, reason: "control_too_large" };
    }

    let decoded;
    try {
      decoded = JSON.parse(raw);
    } catch (_error) {
      return { present: true, ok: false, reason: "control_json_invalid" };
    }

    const control = validateControl(decoded);
    if (!control) {
      return {
        present: true,
        ok: false,
        reason: "control_schema_invalid",
        detail: schemaDiagnosticDetail(decoded)
      };
    }
    return {
      present: true,
      ok: true,
      reason: "control_valid",
      control: { ...control, marker: source.slice(start, end + CLOSE.length) }
    };
  }

  function parseConversationFabricControl(text) {
    const diagnostic = diagnoseConversationFabricControl(text);
    return diagnostic.ok ? diagnostic.control : null;
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
    normalizeControl,
    validateInspect,
    validateRetire,
    diagnoseConversationFabricControl,
    parseConversationFabricControl
  });
});
