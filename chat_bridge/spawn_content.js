(() => {
  "use strict";

  const protocol = globalThis.LocalAgentBridgeProtocol;
  if (!protocol) throw new Error("Local Agent Chat Bridge protocol is unavailable");
  const { normalizeConversationUrl } = protocol;
  const SPAWN_PROTOCOL_VERSION = 1;
  const MAX_BOOTSTRAP_CHARS = 32_768;
  const TRANSACTION_RE = /^spawn-[0-9a-f]{64}$/;
  const DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
  const COMMIT_SHA_RE = /^[0-9a-f]{40}$/;
  const CLAIM_PREFIX = "local-agent:conversation-spawn:";
  const BOOTSTRAP_HEADER = "LOCAL AGENT CHILD BOOTSTRAP";
  const BOOTSTRAP_INSTRUCTIONS = Object.freeze([
    "Treat this bootstrap as the complete admitted startup authority for this child conversation.",
    "Work only from the immutable request fields and content-addressed context references below.",
    "Do not substitute browser state, a moved repository ref, or unreferenced transcript history for admitted authority."
  ]);
  const BOOTSTRAP_RECORD_KEYS = Object.freeze([
    "bootstrap_contract_version",
    "child_request_digest",
    "instructions",
    "request"
  ]);
  const CHILD_REQUEST_IDENTITY_KEYS = Object.freeze([
    "agent_binding",
    "bootstrap_contract_version",
    "context_refs",
    "id",
    "parent_conversation_url",
    "repository_commit_sha",
    "repository_id",
    "repository_ref",
    "role",
    "schema_version",
    "scope",
    "workflow_id",
    "workflow_node_id",
    "workflow_node_introduction_digest",
    "workflow_node_revision"
  ]);
  const COMPOSER_BLOCK_TAGS = new Set([
    "ADDRESS",
    "ARTICLE",
    "ASIDE",
    "BLOCKQUOTE",
    "DIV",
    "FIGCAPTION",
    "FIGURE",
    "FOOTER",
    "H1",
    "H2",
    "H3",
    "H4",
    "H5",
    "H6",
    "HEADER",
    "LI",
    "MAIN",
    "NAV",
    "P",
    "PRE",
    "SECTION"
  ]);

  const existing = globalThis.__localAgentConversationSpawnContent;
  if (existing?.protocolVersion === SPAWN_PROTOCOL_VERSION) return;
  try { existing?.dispose?.(); } catch (_error) {}

  function routeState() {
    try {
      const url = new URL(location.href);
      if (url.protocol !== "https:" || !["chatgpt.com", "chat.openai.com"].includes(url.hostname)) {
        return { kind: "unexpected" };
      }
      const path = url.pathname.replace(/\/+$/, "") || "/";
      if (
        /^\/uc\/[^/]+$/.test(path) ||
        /^\/c\/local-chatgpt%3a[A-Za-z0-9-]+$/i.test(path)
      ) {
        return { kind: "provisional" };
      }
      const childConversationUrl = normalizeConversationUrl(url.href);
      if (childConversationUrl) return { kind: "child", childConversationUrl };
      return path === "/" ? { kind: "fresh" } : { kind: "unexpected" };
    } catch (_error) {
      return { kind: "unexpected" };
    }
  }

  function findComposer() {
    return (
      document.querySelector("#prompt-textarea") ||
      document.querySelector('form [contenteditable="true"][data-lexical-editor="true"]') ||
      document.querySelector('form [contenteditable="true"]') ||
      document.querySelector("form textarea")
    );
  }

  function normalizeContentEditableText(text) {
    return String(text || "").replace(/\u00a0/g, " ");
  }

  function descendantText(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      return normalizeContentEditableText(node.nodeValue || "");
    }
    if (node instanceof HTMLBRElement) return "\n";
    if (!(node instanceof HTMLElement)) return "";
    return Array.from(node.childNodes, (child) => descendantText(child)).join("");
  }

  function blockLineText(block) {
    if (
      block.childNodes.length === 1 &&
      block.firstChild instanceof HTMLBRElement
    ) {
      return "";
    }
    return Array.from(block.childNodes, (child) => descendantText(child)).join("");
  }

  function blockStructuredComposerText(composer) {
    if (!(composer instanceof HTMLElement)) return null;
    const children = Array.from(composer.childNodes).filter((node) => !(
      node.nodeType === Node.TEXT_NODE && (node.nodeValue || "") === ""
    ));
    if (!children.length) return "";
    if (!children.every((node) => (
      node instanceof HTMLElement && COMPOSER_BLOCK_TAGS.has(node.tagName)
    ))) {
      return null;
    }
    return children.map((block) => blockLineText(block)).join("\n");
  }

  function composerTextVariants(composer) {
    if (composer instanceof HTMLTextAreaElement || composer instanceof HTMLInputElement) {
      return [composer.value || ""];
    }
    if (!(composer instanceof HTMLElement)) return [""];
    const variants = [];
    const addVariant = (text) => {
      if (typeof text !== "string") return;
      variants.push(text);
      variants.push(normalizeContentEditableText(text));
    };
    addVariant(composer.innerText);
    addVariant(composer.textContent);
    const structured = blockStructuredComposerText(composer);
    if (typeof structured === "string") variants.push(structured);
    return Array.from(new Set(variants));
  }

  function composerText(composer) {
    return composerTextVariants(composer)[0] || "";
  }

  function composerMatchesText(composer, expected) {
    return composerTextVariants(composer).some((variant) => variant === expected);
  }

  function exactObjectKeys(value, expected) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const actual = Object.keys(value).sort();
    return actual.length === expected.length && actual.every((key, index) => key === expected[index]);
  }

  function exactStringArray(value, expected) {
    return Array.isArray(value) &&
      value.length === expected.length &&
      value.every((item, index) => item === expected[index]);
  }

  function canonicalJson(value) {
    if (value === null) return "null";
    if (typeof value === "string" || typeof value === "boolean") return JSON.stringify(value);
    if (typeof value === "number") {
      if (!Number.isFinite(value)) throw new Error("non-finite canonical JSON number");
      return JSON.stringify(value);
    }
    if (Array.isArray(value)) {
      return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
    }
    if (typeof value === "object") {
      return `{${Object.keys(value).sort().map((key) => (
        `${JSON.stringify(key)}:${canonicalJson(value[key])}`
      )).join(",")}}`;
    }
    throw new Error("unsupported canonical JSON value");
  }

  async function ownedBootstrapDraftText(composer) {
    for (const variant of composerTextVariants(composer)) {
      const normalized = normalizeContentEditableText(variant);
      if (!normalized.startsWith(`${BOOTSTRAP_HEADER}\n`)) continue;
      let record;
      try {
        record = JSON.parse(normalized.slice(BOOTSTRAP_HEADER.length + 1).trim());
      } catch (_error) {
        continue;
      }
      if (!exactObjectKeys(record, BOOTSTRAP_RECORD_KEYS)) continue;
      if (record.bootstrap_contract_version !== 1) continue;
      if (!DIGEST_RE.test(String(record.child_request_digest || ""))) continue;
      if (!exactStringArray(record.instructions, BOOTSTRAP_INSTRUCTIONS)) continue;
      const request = record.request;
      if (!exactObjectKeys(request, CHILD_REQUEST_IDENTITY_KEYS)) continue;
      if (request.schema_version !== 2 || request.bootstrap_contract_version !== 1) continue;
      if (!COMMIT_SHA_RE.test(String(request.repository_commit_sha || ""))) continue;
      if (!DIGEST_RE.test(String(request.workflow_node_introduction_digest || ""))) continue;
      if (!Number.isInteger(request.workflow_node_revision) || request.workflow_node_revision < 0) continue;
      if (!["research", "implementation", "verification", "integration"].includes(request.role)) continue;
      if (!Array.isArray(request.context_refs)) continue;
      if (!request.scope || typeof request.scope !== "object" || Array.isArray(request.scope)) continue;
      if (typeof request.scope.summary !== "string" || !request.scope.summary.trim()) continue;
      if (normalizeConversationUrl(request.parent_conversation_url) !== request.parent_conversation_url) continue;
      let actualRequestDigest;
      try {
        actualRequestDigest = `sha256:${await sha256(canonicalJson(request))}`;
      } catch (_error) {
        continue;
      }
      if (actualRequestDigest !== record.child_request_digest) continue;
      return variant;
    }
    return null;
  }

  function selectContent(element) {
    const selection = window.getSelection();
    if (!selection) return;
    const range = document.createRange();
    range.selectNodeContents(element);
    selection.removeAllRanges();
    selection.addRange(range);
  }

  function setComposerText(composer, text) {
    composer.focus();
    if (composer instanceof HTMLTextAreaElement) {
      const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
      if (!setter) throw new Error("textarea value setter unavailable");
      setter.call(composer, text);
      composer.dispatchEvent(new Event("input", { bubbles: true }));
      return;
    }
    if (!(composer instanceof HTMLElement) || composer.contentEditable !== "true") {
      throw new Error("unsupported composer element");
    }
    selectContent(composer);
    const inserted = document.execCommand("insertText", false, text);
    if (!inserted) {
      composer.textContent = text;
      composer.dispatchEvent(new InputEvent("input", {
        bubbles: true,
        inputType: "insertText",
        data: text
      }));
    }
  }

  function clearComposer(composer, insertedText) {
    if (!composer?.isConnected || !composerMatchesText(composer, insertedText)) return;
    try { setComposerText(composer, ""); } catch (_error) {}
  }

  function assistantIsGenerating() {
    const buttons = document.querySelectorAll(
      'button[data-testid="stop-button"], button[data-testid="composer-stop-button"]'
    );
    return Array.from(buttons).some((button) => button.checkVisibility({
      checkVisibilityCSS: true,
      checkOpacity: true
    }));
  }

  function findSendButton(composer) {
    const selectors = [
      "#composer-submit-button",
      'button[data-testid="send-button"]',
      'button[data-testid="composer-submit-button"]',
      'button[aria-label="Send prompt"]',
      'button[aria-label="Send message"]',
      'button[aria-label="Send"]'
    ];
    const form = composer?.closest("form");
    for (const scope of form ? [form, document] : [document]) {
      for (const selector of selectors) {
        const button = scope.querySelector(selector);
        if (button instanceof HTMLButtonElement && !button.disabled) return button;
      }
    }
    return null;
  }

  async function preSubmitReadiness() {
    const route = routeState();
    if (route.kind !== "fresh") {
      return { ok: false, reason: "spawn_unexpected_route", route: route.kind };
    }
    if (document.visibilityState === "prerender") {
      return { ok: false, reason: "spawn_page_not_ready" };
    }
    if (assistantIsGenerating()) {
      return { ok: false, reason: "spawn_assistant_busy" };
    }
    const composer = findComposer();
    if (!composer) return { ok: false, reason: "spawn_composer_not_found" };
    if (composerText(composer).trim()) {
      const ownedDraft = await ownedBootstrapDraftText(composer);
      if (!ownedDraft) return { ok: false, reason: "spawn_composer_not_empty" };
      return { ok: true, reason: "spawn_ready", ownedBootstrapDraft: true };
    }
    return { ok: true, reason: "spawn_ready" };
  }

  async function waitForSendButton(composer, timeoutMs = 4500) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (assistantIsGenerating()) return null;
      const button = findSendButton(composer);
      if (button) return button;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return null;
  }

  function latestExactUserMessage(prompt) {
    const normalized = (text) => String(text || "").trim().replace(/\s+/g, " ");
    const messages = document.querySelectorAll('[data-message-author-role="user"]');
    const latest = messages[messages.length - 1];
    if (!latest) return false;
    return normalized(latest.innerText || latest.textContent) === normalized(prompt);
  }

  async function sha256(text) {
    const bytes = new TextEncoder().encode(String(text));
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, "0")).join("");
  }

  async function validateSpawnMessage(message) {
    const transactionId = String(message.transactionId || "");
    const childRequestDigest = String(message.childRequestDigest || "");
    const bootstrapDigest = String(message.bootstrapDigest || "");
    const bootstrapText = String(message.bootstrapText || "");
    if (!TRANSACTION_RE.test(transactionId)) throw new Error("invalid spawn transaction id");
    if (!DIGEST_RE.test(childRequestDigest)) throw new Error("invalid spawn child request digest");
    if (!DIGEST_RE.test(bootstrapDigest)) throw new Error("invalid spawn bootstrap digest");
    if (!bootstrapText.trim() || bootstrapText.length > MAX_BOOTSTRAP_CHARS) {
      throw new Error("invalid spawn bootstrap text");
    }
    const actual = `sha256:${await sha256(bootstrapText)}`;
    if (actual !== bootstrapDigest) throw new Error("spawn bootstrap digest mismatch");
    return { transactionId, childRequestDigest, bootstrapDigest, bootstrapText };
  }

  function claimKey(transactionId) {
    return `${CLAIM_PREFIX}${transactionId}`;
  }

  function readClaim(transactionId) {
    try {
      const raw = sessionStorage.getItem(claimKey(transactionId));
      if (!raw) return null;
      const claim = JSON.parse(raw);
      return claim && typeof claim === "object" ? claim : null;
    } catch (_error) {
      return null;
    }
  }

  function writeClaim(validated, state, evidence = {}) {
    const existing = readClaim(validated.transactionId);
    const claim = {
      transactionId: validated.transactionId,
      childRequestDigest: validated.childRequestDigest,
      bootstrapDigest: validated.bootstrapDigest,
      state,
      sawProvisionalRoute: Boolean(
        evidence.sawProvisionalRoute ||
        (claimMatches(existing, validated) && existing.sawProvisionalRoute === true)
      )
    };
    sessionStorage.setItem(claimKey(validated.transactionId), JSON.stringify(claim));
    return claim;
  }

  function clearClaim(transactionId) {
    try { sessionStorage.removeItem(claimKey(transactionId)); } catch (_error) {}
  }

  function claimMatches(claim, validated) {
    return Boolean(
      claim &&
      claim.transactionId === validated.transactionId &&
      claim.childRequestDigest === validated.childRequestDigest &&
      claim.bootstrapDigest === validated.bootstrapDigest
    );
  }

  function provisionalDiagnostic(validated) {
    const claim = readClaim(validated.transactionId);
    if (!claim) return { ok: false, reason: "spawn_claim_missing" };
    if (!claimMatches(claim, validated)) {
      return { ok: false, reason: "spawn_claim_conflict" };
    }
    const composer = findComposer();
    const userMessages = document.querySelectorAll('[data-message-author-role="user"]');
    const assistantMessages = document.querySelectorAll('[data-message-author-role="assistant"]');
    const latestAssistant = assistantMessages[assistantMessages.length - 1];
    return {
      ok: true,
      reason: "spawn_provisional_diagnostic",
      claimState: typeof claim.state === "string" ? claim.state : "unknown",
      sawProvisionalRoute: claim.sawProvisionalRoute === true,
      contentRoute: routeState().kind,
      exactUserMessage: latestExactUserMessage(validated.bootstrapText),
      userMessageCount: userMessages.length,
      assistantMessageCount: assistantMessages.length,
      assistantGenerating: assistantIsGenerating(),
      latestAssistantTextLength: String(
        latestAssistant?.innerText || latestAssistant?.textContent || ""
      ).length,
      composerPresent: Boolean(composer),
      composerHasText: Boolean(composer && composerText(composer).trim()),
      sendButtonReady: Boolean(composer && findSendButton(composer)),
      visibilityState: String(document.visibilityState || "")
    };
  }

  function reconcileValidatedSpawn(validated) {
    const claim = readClaim(validated.transactionId);
    if (!claim) return { ok: false, reason: "spawn_claim_missing" };
    if (!claimMatches(claim, validated)) {
      return { ok: false, reason: "spawn_claim_conflict" };
    }
    const route = routeState();
    if (route.kind === "child" && latestExactUserMessage(validated.bootstrapText)) {
      return {
        ok: true,
        reason: "identity_discovered",
        childConversationUrl: route.childConversationUrl
      };
    }
    return {
      ok: false,
      reason: "spawn_submission_ambiguous",
      route: route.kind,
      exactUserMessage: latestExactUserMessage(validated.bootstrapText),
      claimState: typeof claim.state === "string" ? claim.state : "unknown",
      sawProvisionalRoute: claim.sawProvisionalRoute === true
    };
  }

  async function submitSpawnBootstrap(message) {
    let validated;
    try {
      validated = await validateSpawnMessage(message);
    } catch (error) {
      return { ok: false, reason: "spawn_intent_invalid", error: String(error) };
    }

    const existingClaim = readClaim(validated.transactionId);
    if (existingClaim) return reconcileValidatedSpawn(validated);
    if (routeState().kind !== "fresh") {
      return { ok: false, reason: "spawn_unexpected_route" };
    }
    if (document.visibilityState === "prerender") {
      return { ok: false, reason: "spawn_page_not_ready" };
    }
    if (assistantIsGenerating()) {
      return { ok: false, reason: "spawn_assistant_busy" };
    }

    let composer = findComposer();
    if (!composer) return { ok: false, reason: "spawn_composer_not_found" };
    if (composerText(composer).trim()) {
      const ownedDraft = await ownedBootstrapDraftText(composer);
      if (!ownedDraft) return { ok: false, reason: "spawn_composer_not_empty" };
      clearComposer(composer, ownedDraft);
      await new Promise((resolve) => setTimeout(resolve, 50));
      composer = findComposer() || composer;
      if (composerText(composer).trim()) {
        return { ok: false, reason: "spawn_composer_not_empty" };
      }
    }

    try {
      setComposerText(composer, validated.bootstrapText);
    } catch (error) {
      return { ok: false, reason: "spawn_composer_write_failed", error: String(error) };
    }
    const insertedText = validated.bootstrapText;
    const writtenComposer = findComposer() || composer;
    if (!composerText(writtenComposer).trim()) {
      return { ok: false, reason: "spawn_composer_write_failed" };
    }

    let button = await waitForSendButton(writtenComposer);
    if (!button) {
      clearComposer(findComposer() || writtenComposer, insertedText);
      return { ok: false, reason: "spawn_send_button_not_ready" };
    }
    const activeComposer = findComposer();
    if (
      routeState().kind !== "fresh" ||
      !activeComposer ||
      !composerMatchesText(activeComposer, insertedText)
    ) {
      return { ok: false, reason: "spawn_composer_changed" };
    }
    button = findSendButton(activeComposer) || await waitForSendButton(activeComposer, 1200);
    if (!button) {
      clearComposer(findComposer() || activeComposer, insertedText);
      return { ok: false, reason: "spawn_send_button_not_ready" };
    }

    try {
      writeClaim(validated, "submitting");
    } catch (error) {
      clearComposer(activeComposer, insertedText);
      return { ok: false, reason: "spawn_claim_write_failed", error: String(error) };
    }

    try {
      button.click();
      writeClaim(validated, "submitted");
    } catch (error) {
      return {
        ok: false,
        reason: "spawn_submission_ambiguous",
        error: String(error)
      };
    }

    const deadline = Date.now() + 5000;
    let sawProvisionalRoute = false;
    while (Date.now() < deadline) {
      const route = routeState();
      if (route.kind === "child" && latestExactUserMessage(validated.bootstrapText)) {
        return {
          ok: true,
          reason: "identity_discovered",
          childConversationUrl: route.childConversationUrl
        };
      }
      if (route.kind === "provisional") {
        sawProvisionalRoute = true;
        writeClaim(validated, "submitted", { sawProvisionalRoute: true });
      } else if (sawProvisionalRoute && ["fresh", "unexpected"].includes(route.kind)) {
        return {
          ok: false,
          reason: "spawn_submission_ambiguous",
          route: "unexpected_after_provisional"
        };
      } else if (route.kind === "unexpected") {
        return {
          ok: false,
          reason: "spawn_submission_ambiguous",
          route: "unexpected"
        };
      }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return reconcileValidatedSpawn(validated);
  }

  async function reconcileSpawn(message) {
    let validated;
    try {
      validated = await validateSpawnMessage(message);
    } catch (error) {
      return { ok: false, reason: "spawn_intent_invalid", error: String(error) };
    }
    return reconcileValidatedSpawn(validated);
  }

  async function inspectSpawnDiagnostic(message) {
    let validated;
    try {
      validated = await validateSpawnMessage(message);
    } catch (error) {
      return { ok: false, reason: "spawn_intent_invalid", error: String(error) };
    }
    return provisionalDiagnostic(validated);
  }

  const listener = (message, _sender, sendResponse) => {
    if (message?.type === "bridge:spawn-capabilities") {
      preSubmitReadiness()
        .then((readiness) => sendResponse({
          ok: true,
          reason: "ready",
          protocolVersion: SPAWN_PROTOCOL_VERSION,
          route: routeState().kind,
          readiness
        }))
        .catch((error) => sendResponse({
          ok: false,
          reason: "spawn_unexpected_error",
          error: String(error),
          protocolVersion: SPAWN_PROTOCOL_VERSION
        }));
      return true;
    }
    if (message?.type === "bridge:spawn-diagnostic") {
      inspectSpawnDiagnostic(message)
        .then((response) => sendResponse({ ...response, protocolVersion: SPAWN_PROTOCOL_VERSION }))
        .catch((error) => sendResponse({
          ok: false,
          reason: "spawn_unexpected_error",
          error: String(error),
          protocolVersion: SPAWN_PROTOCOL_VERSION
        }));
      return true;
    }
    if (message?.type === "bridge:spawn-bootstrap") {
      submitSpawnBootstrap(message)
        .then((response) => sendResponse({ ...response, protocolVersion: SPAWN_PROTOCOL_VERSION }))
        .catch((error) => sendResponse({
          ok: false,
          reason: "spawn_unexpected_error",
          error: String(error),
          protocolVersion: SPAWN_PROTOCOL_VERSION
        }));
      return true;
    }
    if (message?.type === "bridge:spawn-reconcile") {
      reconcileSpawn(message)
        .then((response) => sendResponse({ ...response, protocolVersion: SPAWN_PROTOCOL_VERSION }))
        .catch((error) => sendResponse({
          ok: false,
          reason: "spawn_unexpected_error",
          error: String(error),
          protocolVersion: SPAWN_PROTOCOL_VERSION
        }));
      return true;
    }
    return false;
  };

  chrome.runtime.onMessage.addListener(listener);
  globalThis.__localAgentConversationSpawnContent = {
    protocolVersion: SPAWN_PROTOCOL_VERSION,
    dispose() {
      try { chrome.runtime.onMessage.removeListener(listener); } catch (_error) {}
    }
  };
})();
