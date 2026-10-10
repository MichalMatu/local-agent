(function initLocalAgentBridgeGithubControl(root, factory) {
  const protocol =
    root.LocalAgentBridgeProtocol ||
    (typeof require === "function" ? require("./control_protocol.js") : null);
  const api = factory(protocol);
  root.LocalAgentBridgeGithubControl = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createGithubControlModel(protocol) {
  "use strict";

  if (!protocol) throw new Error("Local Agent Bridge protocol is unavailable");

  const AGENT_BINDING_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
  const REPOSITORY_ID_RE = /^[A-Za-z0-9._-]{1,120}$/;
  const REPOSITORY_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

  function canonicalIso(value, label, { nullable = false } = {}) {
    if ((value === null || value === undefined || value === "") && nullable) return null;
    if (typeof value !== "string" || !value.trim()) throw new Error(`${label} must be an ISO timestamp`);
    const millis = Date.parse(value);
    if (!Number.isFinite(millis) || !/[zZ]|[+-]\d\d:\d\d$/.test(value.trim())) {
      throw new Error(`${label} must be an offset-aware ISO timestamp`);
    }
    return new Date(millis).toISOString();
  }

  function integerInRange(value, minimum, maximum, label) {
    const number = Number(value);
    if (!Number.isInteger(number) || number < minimum || number > maximum) {
      throw new Error(`${label} must be an integer in range ${minimum}..${maximum}`);
    }
    return number;
  }

  function legacyBindingMetadata(raw) {
    const values = [raw.repository_id, raw.repository, raw.agent_binding, raw.binding_revision];
    if (values.every((value) => value === undefined || value === null || value === "")) {
      return {
        repositoryId: null,
        repository: null,
        agentBinding: null,
        bindingRevision: 0
      };
    }
    const repositoryId = String(raw.repository_id || "").trim();
    const repository = String(raw.repository || "").trim();
    const agentBinding = String(raw.agent_binding || "").trim();
    if (!REPOSITORY_ID_RE.test(repositoryId)) throw new Error("invalid legacy conversation control repository_id");
    if (!REPOSITORY_RE.test(repository)) throw new Error("invalid legacy conversation control repository");
    if (!AGENT_BINDING_RE.test(agentBinding)) throw new Error("invalid legacy conversation control agent_binding");
    return {
      repositoryId,
      repository,
      agentBinding,
      bindingRevision: integerInRange(
        raw.binding_revision,
        1,
        Number.MAX_SAFE_INTEGER,
        "legacy conversation control binding_revision"
      )
    };
  }

  function sanitizeTaskResultWatch(raw) {
    if (raw === null || raw === undefined) return null;
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      throw new Error("task_result_watch must be an object");
    }
    const repositoryId = String(raw.repository_id || "");
    const taskId = String(raw.task_id || "");
    if (!REPOSITORY_ID_RE.test(repositoryId)) {
      throw new Error("task_result_watch repository_id is invalid");
    }
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/.test(taskId)) {
      throw new Error("task_result_watch task_id is invalid");
    }
    return Object.freeze({ repositoryId, taskId });
  }

  function sanitizeConversationControl(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
      throw new Error("conversation control must be an object");
    }
    const conversationId = String(raw.conversation_id || "").trim();
    if (!protocol.CHAT_ID_RE.test(conversationId)) throw new Error("invalid conversation control conversation_id");
    if (typeof raw.enabled !== "boolean") throw new Error("conversation control enabled must be a boolean");

    const legacy = legacyBindingMetadata(raw);
    const taskResultWatch = sanitizeTaskResultWatch(raw.task_result_watch);
    const intervalMinutes = raw.interval_minutes === null || raw.interval_minutes === undefined
      ? null
      : integerInRange(
          raw.interval_minutes,
          protocol.MIN_INTERVAL_MINUTES,
          protocol.MAX_INTERVAL_MINUTES,
          "conversation control interval_minutes"
        );
    const nextWakeAt = canonicalIso(raw.next_wake_at, "conversation control next_wake_at", { nullable: true });
    const updatedAt = canonicalIso(raw.updated_at, "conversation control updated_at");
    if (!raw.enabled && nextWakeAt) {
      throw new Error("disabled conversation control must not define next_wake_at");
    }
    if (nextWakeAt) {
      const nextWakeMs = Date.parse(nextWakeAt);
      const updatedMs = Date.parse(updatedAt);
      if (nextWakeMs < updatedMs) {
        throw new Error("conversation control next_wake_at must not precede updated_at");
      }
      if (nextWakeMs - updatedMs > protocol.MAX_NEXT_SECONDS * 1000) {
        throw new Error("conversation control next_wake_at exceeds maximum wake horizon");
      }
    }

    return Object.freeze({
      conversationId,
      ...legacy,
      controlGeneration: integerInRange(
        raw.control_generation,
        1,
        Number.MAX_SAFE_INTEGER,
        "conversation control control_generation"
      ),
      enabled: raw.enabled,
      intervalMinutes,
      nextWakeAt,
      taskResultWatch,
      updatedAt
    });
  }

  function validateConversationControls(rawControls, agents) {
    if (rawControls === undefined || rawControls === null) return [];
    if (!Array.isArray(rawControls)) throw new Error("runtime conversation_controls must be a list");
    if (rawControls.length > 128) throw new Error("runtime conversation_controls exceeds 128 entries");

    const seen = new Set();
    const validated = rawControls.map((raw) => {
      const control = sanitizeConversationControl(raw);
      if (control.taskResultWatch) {
        const agent = (agents || []).find((item) =>
          item.repositoryId === control.taskResultWatch.repositoryId
        );
        if (!agent || agent.executionEnabled !== true || !REPOSITORY_RE.test(agent.repository)) {
          throw new Error("task_result_watch requires an enabled configured repository");
        }
      }
      if (seen.has(control.conversationId)) {
        throw new Error(`duplicate runtime conversation control: ${control.conversationId}`);
      }
      seen.add(control.conversationId);
      return control;
    });
    if (validated.filter((control) => Boolean(control.taskResultWatch)).length > 4) {
      throw new Error("runtime task_result_watch exceeds four concurrent watches");
    }
    return validated;
  }

  function findConversationControl(runtime, conversationId) {
    return (runtime?.conversationControls || []).find((control) => control.conversationId === conversationId) || null;
  }

  function controlMatchesConversation(control, conversation) {
    return Boolean(control && conversation && control.conversationId === conversation.id);
  }

  function scheduleDeadline(control, fallbackIntervalMinutes, nowMs = Date.now()) {
    if (!control?.enabled) return null;
    if (control.nextWakeAt) {
      const parsed = Date.parse(control.nextWakeAt);
      if (!Number.isFinite(parsed)) throw new Error("invalid control next wake deadline");
      if (parsed > nowMs + protocol.MAX_NEXT_SECONDS * 1000) {
        throw new Error("control next wake deadline exceeds maximum horizon from now");
      }
      if (parsed > nowMs + 1000) return parsed;
    }
    const interval = control.intervalMinutes === null
      ? Number(fallbackIntervalMinutes)
      : control.intervalMinutes;
    if (!Number.isFinite(interval)) throw new Error("invalid fallback interval");
    return nowMs + interval * 60_000;
  }

  return Object.freeze({
    sanitizeConversationControl,
    validateConversationControls,
    findConversationControl,
    controlMatchesConversation,
    scheduleDeadline
  });
});
