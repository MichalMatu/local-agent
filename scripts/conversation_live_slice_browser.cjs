"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const readline = require("node:readline");

let chromium;
try {
  ({ chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright"));
} catch (error) {
  process.stderr.write(
    "Conversation live slice requires Playwright. Install the pinned DEV dependency with " +
    "`npm install --no-save --package-lock=false playwright@1.57.0`.\n"
  );
  throw error;
}

const MAX_PROTOCOL_LINE_CHARS = 128 * 1024;
const MAX_BOOTSTRAP_CHARS = 32_768;
const DEFAULT_LOGIN_TIMEOUT_MS = 10 * 60 * 1000;
const AUTH_SESSION_PROBE_TIMEOUT_MS = 1500;
const COMPOSER_WAIT_MS = 30_000;
const SUBMIT_IDENTITY_WAIT_MS = 30_000;
const CHILD_TRANSACTION_RE = /^spawn-[0-9a-f]{64}$/;
const CHILD_DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
const CHILD_CLAIM_PREFIX = "local-agent:conversation-spawn:";
const SPAWN_HASH_PREFIX = "la-spawn=";
const ownedChildPages = new Map();
const spawnPages = new Map();
const pageIds = new WeakMap();
let nextPageId = 0;

const ALLOWED_ACTIONS = new Set([
  "wait_ready",
  "create",
  "recover_create",
  "reattach_pre_submit",
  "probe",
  "submit",
  "reconcile",
  "open_child",
  "observe_child",
  "close_child",
  "shutdown"
]);

function parseArgs(argv) {
  const parsed = { profile: "", extension: "", headless: false };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === "--profile") parsed.profile = argv[++index] || "";
    else if (arg === "--extension") parsed.extension = argv[++index] || ""; // legacy, intentionally unused
    else if (arg === "--headless") parsed.headless = true;
    else throw new Error(`unsupported live slice browser argument: ${arg}`);
  }
  if (!parsed.profile || !path.isAbsolute(parsed.profile)) {
    throw new Error("--profile must be an absolute browser profile path");
  }
  return parsed;
}

function executableFile(candidate, field) {
  if (!candidate) return null;
  if (!path.isAbsolute(candidate)) throw new Error(`${field} must be an absolute path`);
  const stats = fs.statSync(candidate);
  if (!stats.isFile()) throw new Error(`${field} must point to a file`);
  fs.accessSync(candidate, fs.constants.X_OK);
  return candidate;
}

function chromeExecutable() {
  const explicit = String(process.env.LOCAL_AGENT_CONVERSATION_CHROME_EXECUTABLE || "").trim();
  if (explicit) return executableFile(explicit, "LOCAL_AGENT_CONVERSATION_CHROME_EXECUTABLE");

  if (process.platform === "darwin") {
    const branded = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
    if (fs.existsSync(branded)) return executableFile(branded, "Google Chrome executable");
  }

  const legacy = String(process.env.LOCAL_AGENT_CHROME_EXECUTABLE || "").trim();
  return legacy ? executableFile(legacy, "LOCAL_AGENT_CHROME_EXECUTABLE") : null;
}

function browserProfile(cliProfile) {
  const explicit = String(process.env.LOCAL_AGENT_CONVERSATION_BROWSER_PROFILE || "").trim();
  const selected = explicit || cliProfile;
  if (!path.isAbsolute(selected)) {
    throw new Error("conversation browser profile must be an absolute path");
  }
  fs.mkdirSync(selected, { recursive: true });
  const stats = fs.lstatSync(selected);
  if (stats.isSymbolicLink() || !stats.isDirectory()) {
    throw new Error("conversation browser profile must be a regular directory");
  }
  return selected;
}

function boundedInteger(value, { minimum, maximum, field }) {
  if (!Number.isInteger(value) || value < minimum || value > maximum) {
    throw new Error(`${field} must be ${minimum}..${maximum}`);
  }
  return value;
}

function validateRequest(message) {
  if (!message || typeof message !== "object" || Array.isArray(message)) {
    throw new Error("browser actuator request must be an object");
  }
  const id = boundedInteger(message.id, { minimum: 1, maximum: 2 ** 31 - 1, field: "request id" });
  const action = String(message.action || "");
  if (!ALLOWED_ACTIONS.has(action)) throw new Error(`unsupported browser actuator action: ${action}`);
  return { id, action, payload: message.payload || {} };
}

function validateIntent(intent) {
  if (!intent || typeof intent !== "object" || Array.isArray(intent)) {
    throw new Error("conversation spawn intent must be an object");
  }
  if (intent.schema_version !== 1) throw new Error("conversation spawn schema_version must be 1");
  if (!CHILD_TRANSACTION_RE.test(String(intent.transaction_id || ""))) {
    throw new Error("conversation spawn transaction_id is invalid");
  }
  if (!CHILD_DIGEST_RE.test(String(intent.child_request_digest || ""))) {
    throw new Error("conversation spawn child_request_digest is invalid");
  }
  if (!CHILD_DIGEST_RE.test(String(intent.bootstrap_digest || ""))) {
    throw new Error("conversation spawn bootstrap_digest is invalid");
  }
  if (
    typeof intent.bootstrap_text !== "string" ||
    !intent.bootstrap_text.trim() ||
    intent.bootstrap_text.length > MAX_BOOTSTRAP_CHARS
  ) {
    throw new Error("conversation spawn bootstrap_text must be bounded non-empty text");
  }
  if (intent.tab_id !== null && (!Number.isInteger(intent.tab_id) || intent.tab_id < 1)) {
    throw new Error("conversation spawn tab_id must be a positive integer or null");
  }
  const digest = `sha256:${crypto.createHash("sha256").update(intent.bootstrap_text, "utf8").digest("hex")}`;
  if (digest !== intent.bootstrap_digest) throw new Error("conversation spawn bootstrap digest mismatch");
  return intent;
}

function jsonLine(payload) {
  return `${JSON.stringify(payload)}\n`;
}

function writeResponse(id, result) {
  process.stdout.write(jsonLine({ id, ok: true, result: result ?? null }));
}

function writeError(id, error) {
  process.stdout.write(jsonLine({ id, ok: false, error: String(error?.stack || error) }));
}

function composerSelector() {
  return [
    "#prompt-textarea",
    'form [contenteditable="true"][data-lexical-editor="true"]',
    'form [contenteditable="true"]',
    "form textarea"
  ].join(",");
}

function submitSelector() {
  return [
    'button[data-testid="send-button"]',
    'button[data-testid="composer-send-button"]',
    "#composer-submit-button",
    'form button[type="submit"]'
  ].join(",");
}

function canonicalChatHome(rawUrl) {
  try {
    const url = new URL(String(rawUrl || ""));
    const pathName = url.pathname.replace(/\/+$/, "") || "/";
    return url.protocol === "https:" &&
      ["chatgpt.com", "chat.openai.com"].includes(url.hostname) &&
      pathName === "/";
  } catch (_error) {
    return false;
  }
}

function canonicalConversationUrl(rawUrl) {
  try {
    const url = new URL(String(rawUrl || ""));
    const match = url.pathname.replace(/\/+$/, "").match(/^\/c\/([A-Za-z0-9-]+)$/);
    if (url.protocol !== "https:" || !["chatgpt.com", "chat.openai.com"].includes(url.hostname) || !match || url.search || url.hash) return "";
    return `https://chatgpt.com/c/${match[1]}`;
  } catch (_error) {
    return "";
  }
}

function spawnMarkerUrl(transactionId) {
  return `https://chatgpt.com/#${SPAWN_HASH_PREFIX}${encodeURIComponent(transactionId)}`;
}

function transactionFromUrl(rawUrl) {
  try {
    const url = new URL(String(rawUrl || ""));
    if (!canonicalChatHome(url.href)) return "";
    const hash = url.hash.replace(/^#/, "");
    if (!hash.startsWith(SPAWN_HASH_PREFIX)) return "";
    const value = decodeURIComponent(hash.slice(SPAWN_HASH_PREFIX.length));
    return CHILD_TRANSACTION_RE.test(value) ? value : "";
  } catch (_error) {
    return "";
  }
}

function claimKey(transactionId) {
  return `${CHILD_CLAIM_PREFIX}${transactionId}`;
}

function claimValue(intent, state, childConversationUrl = "") {
  return {
    transactionId: intent.transaction_id,
    childRequestDigest: intent.child_request_digest,
    bootstrapDigest: intent.bootstrap_digest,
    state,
    childConversationUrl
  };
}

async function writeClaim(page, intent, state, childConversationUrl = "") {
  const claim = claimValue(intent, state, childConversationUrl);
  await page.evaluate(({ key, value }) => {
    const raw = JSON.stringify(value);
    sessionStorage.setItem(key, raw);
    localStorage.setItem(key, raw);
  }, { key: claimKey(intent.transaction_id), value: claim });
}

async function readClaim(page, transactionId) {
  if (!page || page.isClosed()) return null;
  try {
    return await page.evaluate((key) => {
      for (const storage of [sessionStorage, localStorage]) {
        try {
          const raw = storage.getItem(key);
          if (!raw) continue;
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed === "object") return parsed;
        } catch (_error) {}
      }
      return null;
    }, claimKey(transactionId));
  } catch (_error) {
    return null;
  }
}

function pageId(page) {
  const existing = pageIds.get(page);
  if (existing) return existing;
  const id = ++nextPageId;
  pageIds.set(page, id);
  return id;
}

function pageById(context, id) {
  if (!Number.isInteger(id) || id < 1) return null;
  return context.pages().find((page) => !page.isClosed() && pageIds.get(page) === id) || null;
}

async function pageMatchesIntent(page, intent) {
  if (!page || page.isClosed()) return false;
  if (transactionFromUrl(page.url()) === intent.transaction_id) return true;
  const claim = await readClaim(page, intent.transaction_id);
  return Boolean(
    claim &&
    claim.transactionId === intent.transaction_id &&
    claim.childRequestDigest === intent.child_request_digest &&
    claim.bootstrapDigest === intent.bootstrap_digest
  );
}

async function recoverSpawnPage(context, intent) {
  const cached = spawnPages.get(intent.transaction_id);
  if (cached && !cached.isClosed() && await pageMatchesIntent(cached, intent)) return cached;
  spawnPages.delete(intent.transaction_id);

  if (intent.tab_id !== null) {
    const byId = pageById(context, intent.tab_id);
    if (byId && await pageMatchesIntent(byId, intent)) {
      spawnPages.set(intent.transaction_id, byId);
      return byId;
    }
  }

  const matches = [];
  for (const page of context.pages()) {
    if (await pageMatchesIntent(page, intent)) matches.push(page);
  }
  if (matches.length > 1) throw new Error("multiple browser pages claim the same conversation spawn transaction");
  if (matches.length === 1) {
    spawnPages.set(intent.transaction_id, matches[0]);
    return matches[0];
  }
  return null;
}

async function createSpawnPage(context, rawIntent, reason = "tab_created") {
  const intent = validateIntent(rawIntent);
  const recovered = await recoverSpawnPage(context, intent);
  if (recovered) return { ok: true, reason: "tab_recovered", tabId: pageId(recovered) };

  const page = await context.newPage();
  await page.goto(spawnMarkerUrl(intent.transaction_id), {
    waitUntil: "domcontentloaded",
    timeout: 15_000
  }).catch(() => null);
  if (!canonicalChatHome(page.url())) {
    await page.close().catch(() => null);
    return { ok: false, reason: "spawn_page_not_ready" };
  }
  await writeClaim(page, intent, "created");
  spawnPages.set(intent.transaction_id, page);
  return { ok: true, reason, tabId: pageId(page) };
}

async function recoverOrRecreateSpawnPage(context, rawIntent, reason = "tab_recreated") {
  const intent = validateIntent(rawIntent);
  const recovered = await recoverSpawnPage(context, intent);
  if (recovered) return { ok: true, reason: "tab_recovered", tabId: pageId(recovered) };
  // A missing pre-submit browser page is safe to recreate: the durable transaction
  // still proves no child identity was discovered and no registration was published.
  return createSpawnPage(context, { ...intent, tab_id: null }, reason);
}

async function pageComposerReady(page) {
  if (!page || page.isClosed() || !canonicalChatHome(page.url())) return false;
  try {
    return await page.locator(composerSelector()).first().isVisible({ timeout: 500 });
  } catch (_error) {
    return false;
  }
}

async function probeBeforeSubmit(context, rawIntent) {
  const intent = validateIntent(rawIntent);
  let page = await recoverSpawnPage(context, intent);
  if (!page) {
    const recreated = await recoverOrRecreateSpawnPage(context, intent);
    if (!recreated.ok) return recreated;
    page = await recoverSpawnPage(context, { ...intent, tab_id: recreated.tabId });
  }
  if (!page) return { ok: false, reason: "spawn_tab_unavailable" };
  if (!canonicalChatHome(page.url())) return { ok: false, reason: "spawn_unexpected_route", route: page.url() };

  const deadline = Date.now() + COMPOSER_WAIT_MS;
  while (Date.now() < deadline) {
    if (await pageComposerReady(page)) return { ok: true, reason: "spawn_ready" };
    await page.waitForTimeout(100);
  }
  return { ok: false, reason: "spawn_composer_not_found" };
}

async function fillComposer(page, text) {
  const composer = page.locator(composerSelector()).first();
  await composer.waitFor({ state: "visible", timeout: COMPOSER_WAIT_MS });
  const tagName = await composer.evaluate((element) => element.tagName.toLowerCase());
  if (tagName === "textarea" || tagName === "input") {
    await composer.fill(text);
  } else {
    await composer.click();
    await composer.fill(text).catch(async () => {
      await page.evaluate(({ selector, value }) => {
        const element = document.querySelector(selector);
        if (!(element instanceof HTMLElement)) throw new Error("composer element unavailable");
        element.focus();
        element.textContent = value;
        element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
      }, { selector: composerSelector(), value: text });
    });
  }
}

async function submitSpawn(context, rawIntent) {
  const intent = validateIntent(rawIntent);
  let page = await recoverSpawnPage(context, intent);
  if (!page) {
    const recreated = await recoverOrRecreateSpawnPage(context, intent);
    if (!recreated.ok) return recreated;
    page = await recoverSpawnPage(context, { ...intent, tab_id: recreated.tabId });
  }
  if (!page) return { ok: false, reason: "spawn_tab_unavailable" };

  const existingChildUrl = canonicalConversationUrl(page.url());
  if (existingChildUrl) {
    await writeClaim(page, intent, "submitted", existingChildUrl).catch(() => null);
    return { ok: true, reason: "spawn_already_submitted", childConversationUrl: existingChildUrl };
  }
  if (!canonicalChatHome(page.url())) return { ok: false, reason: "spawn_unexpected_route", route: page.url() };

  await writeClaim(page, intent, "submitting");
  await fillComposer(page, intent.bootstrap_text);

  const button = page.locator(submitSelector()).first();
  let submitted = false;
  if (await button.count().catch(() => 0)) {
    const visible = await button.isVisible().catch(() => false);
    const disabled = await button.isDisabled().catch(() => false);
    if (visible && !disabled) {
      await button.click();
      submitted = true;
    }
  }
  if (!submitted) {
    await page.locator(composerSelector()).first().press("Enter");
  }

  const deadline = Date.now() + SUBMIT_IDENTITY_WAIT_MS;
  while (Date.now() < deadline) {
    const childUrl = canonicalConversationUrl(page.url());
    if (childUrl) {
      await writeClaim(page, intent, "submitted", childUrl).catch(() => null);
      spawnPages.set(intent.transaction_id, page);
      return { ok: true, reason: "spawn_submitted", childConversationUrl: childUrl };
    }
    await page.waitForTimeout(100);
  }
  return { ok: false, reason: "spawn_identity_timeout", route: page.url() };
}

async function reconcileSpawn(context, rawIntent) {
  const intent = validateIntent(rawIntent);
  const page = await recoverSpawnPage(context, intent);
  if (page) {
    const childUrl = canonicalConversationUrl(page.url());
    if (childUrl) {
      await writeClaim(page, intent, "submitted", childUrl).catch(() => null);
      return { ok: true, reason: "spawn_identity_recovered", childConversationUrl: childUrl };
    }
    const claim = await readClaim(page, intent.transaction_id);
    const claimedUrl = canonicalConversationUrl(claim?.childConversationUrl || "");
    if (claimedUrl) return { ok: true, reason: "spawn_identity_recovered", childConversationUrl: claimedUrl };
  }

  const existingProbe = context.pages().find((candidate) => !candidate.isClosed() && canonicalChatHome(candidate.url())) || null;
  const probe = existingProbe || await context.newPage();
  const createdProbe = existingProbe === null;
  try {
    if (!canonicalChatHome(probe.url())) {
      await probe.goto("https://chatgpt.com/", { waitUntil: "domcontentloaded", timeout: 10_000 }).catch(() => null);
    }
    const claim = await readClaim(probe, intent.transaction_id);
    const claimedUrl = canonicalConversationUrl(claim?.childConversationUrl || "");
    if (claimedUrl) return { ok: true, reason: "spawn_identity_recovered", childConversationUrl: claimedUrl };
  } finally {
    if (createdProbe && !probe.isClosed()) await probe.close().catch(() => null);
  }
  return { ok: false, reason: "spawn_identity_unresolved" };
}

function accountControlSelector() {
  return '[data-testid="accounts-profile-button"]';
}

async function pageAccountControlReady(page) {
  if (!page || page.isClosed() || !canonicalChatHome(page.url())) return false;
  try {
    return await page.locator(accountControlSelector()).count() > 0;
  } catch (_error) {
    return false;
  }
}

async function pageSessionAuthenticated(page) {
  if (!page || page.isClosed() || !canonicalChatHome(page.url())) return false;
  try {
    return await page.evaluate(async (timeoutMs) => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const response = await fetch("/api/auth/session", {
          credentials: "include",
          cache: "no-store",
          signal: controller.signal
        });
        if (!response.ok) return false;
        const session = await response.json().catch(() => null);
        return Boolean(session && typeof session === "object" && session.user && typeof session.user === "object");
      } catch (_error) {
        return false;
      } finally {
        clearTimeout(timer);
      }
    }, AUTH_SESSION_PROBE_TIMEOUT_MS);
  } catch (_error) {
    return false;
  }
}

async function pageAuthenticated(page) {
  if (await pageAccountControlReady(page)) return true;
  return pageSessionAuthenticated(page);
}

async function waitForLoginReady(context, timeoutMs) {
  boundedInteger(timeoutMs, { minimum: 1_000, maximum: 30 * 60 * 1000, field: "login timeout_ms" });
  const deadline = Date.now() + timeoutMs;
  const page = await context.newPage();
  try {
    await page.goto("https://chatgpt.com/", {
      waitUntil: "domcontentloaded",
      timeout: Math.min(Math.max(1, deadline - Date.now()), 5_000)
    }).catch(() => null);
    while (Date.now() < deadline) {
      if (await pageAuthenticated(page)) return { ok: true, reason: "chatgpt_ready", url: page.url() };
      await page.waitForTimeout(500);
    }
    return { ok: false, reason: "chatgpt_login_timeout", url: page.url() };
  } finally {
    await page.close().catch(() => null);
  }
}

function requireChildUrl(payload) {
  const raw = String(payload?.child_conversation_url || "");
  const canonical = canonicalConversationUrl(raw);
  if (!canonical || canonical !== raw) throw new Error("child lifecycle action requires canonical child_conversation_url");
  return canonical;
}

function childOwnership(payload) {
  const raw = payload?.ownership;
  if (raw === undefined || raw === null) return null;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) throw new Error("child ownership must be an object");
  const transactionId = String(raw.transaction_id || "");
  const childRequestDigest = String(raw.child_request_digest || "");
  const bootstrapDigest = String(raw.bootstrap_digest || "");
  if (!CHILD_TRANSACTION_RE.test(transactionId)) throw new Error("child ownership transaction_id is invalid");
  if (!CHILD_DIGEST_RE.test(childRequestDigest)) throw new Error("child ownership child_request_digest is invalid");
  if (!CHILD_DIGEST_RE.test(bootstrapDigest)) throw new Error("child ownership bootstrap_digest is invalid");
  return { transactionId, childRequestDigest, bootstrapDigest };
}

function sameChildOwnership(left, right) {
  if (left === null || right === null) return left === right;
  if (!left || !right) return false;
  return left.transactionId === right.transactionId &&
    left.childRequestDigest === right.childRequestDigest &&
    left.bootstrapDigest === right.bootstrapDigest;
}

async function pageMatchesChildOwnership(page, ownership) {
  if (!ownership || page.isClosed()) return false;
  const claim = await readClaim(page, ownership.transactionId);
  return Boolean(
    claim &&
    claim.transactionId === ownership.transactionId &&
    claim.childRequestDigest === ownership.childRequestDigest &&
    claim.bootstrapDigest === ownership.bootstrapDigest &&
    ["submitting", "submitted"].includes(String(claim.state || ""))
  );
}

function exactChildPages(context, childUrl) {
  return context.pages().filter((page) => !page.isClosed() && canonicalConversationUrl(page.url()) === childUrl);
}

async function resolveOwnedChildPage(context, payload, { createIfMissing }) {
  const childUrl = requireChildUrl(payload);
  const ownership = childOwnership(payload);
  const cached = ownedChildPages.get(childUrl);
  if (cached?.page && !cached.page.isClosed() && canonicalConversationUrl(cached.page.url()) === childUrl) {
    if (!sameChildOwnership(cached.ownership, ownership)) return { ok: false, reason: "child_ownership_conflict", childUrl };
    return { ok: true, page: cached.page, childUrl, ownership, source: "actuator_owned" };
  }
  ownedChildPages.delete(childUrl);

  if (ownership) {
    const claimed = [];
    for (const page of exactChildPages(context, childUrl)) {
      if (await pageMatchesChildOwnership(page, ownership)) claimed.push(page);
    }
    if (claimed.length > 1) return { ok: false, reason: "child_owned_tab_ambiguous", childUrl };
    if (claimed.length === 1) {
      ownedChildPages.set(childUrl, { page: claimed[0], ownership, source: "spawn_claim" });
      return { ok: true, page: claimed[0], childUrl, ownership, source: "spawn_claim" };
    }
  }

  if (!createIfMissing) return { ok: false, reason: "child_owned_tab_missing", childUrl };
  const page = await context.newPage();
  await page.goto(childUrl, { waitUntil: "domcontentloaded", timeout: 15_000 }).catch(() => null);
  const deadline = Date.now() + 10_000;
  while (Date.now() < deadline && canonicalConversationUrl(page.url()) !== childUrl) await page.waitForTimeout(100);
  if (canonicalConversationUrl(page.url()) !== childUrl) {
    if (!page.isClosed()) await page.close().catch(() => null);
    return { ok: false, reason: "child_route_not_ready", childUrl };
  }
  ownedChildPages.set(childUrl, { page, ownership, source: "observer_created" });
  return { ok: true, page, childUrl, ownership, source: "observer_created" };
}

async function openChild(context, payload) {
  const resolved = await resolveOwnedChildPage(context, payload, { createIfMissing: true });
  if (!resolved.ok) return { ok: false, reason: resolved.reason };
  return { ok: true, reason: "child_opened", child_conversation_url: resolved.childUrl, ownership_source: resolved.source };
}

async function observeChild(context, payload) {
  const childUrl = requireChildUrl(payload);
  const resolved = await resolveOwnedChildPage(context, payload, { createIfMissing: true });
  if (!resolved.ok) return { ok: false, reason: resolved.reason };
  const snapshot = await resolved.page.evaluate((maxChars) => {
    const visible = (element) => {
      if (!(element instanceof HTMLElement)) return false;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
    };
    const generating = Array.from(document.querySelectorAll('button[data-testid="stop-button"], button[data-testid="composer-stop-button"]')).some(visible);
    const clean = (root) => {
      const clone = root.cloneNode(true);
      clone.querySelectorAll('[data-message-author-role="user"], [data-conversation-role="user"], [data-user-message-bubble], button, [role="button"], form, textarea, .sr-only').forEach((item) => item.remove());
      return String(clone.textContent || "").trim();
    };
    const markerSelectors = 'h1,h2,h3,h4,h5,h6,[data-message-author-role="assistant"],[data-conversation-role="assistant"]';
    let text = "";
    let identity = "";
    const turns = Array.from(document.querySelectorAll('[data-turn-key]'));
    for (let index = turns.length - 1; index >= 0; index -= 1) {
      const turn = turns[index];
      const markers = Array.from(turn.querySelectorAll(markerSelectors)).filter((item) => String(item.textContent || "").trim() === "ChatGPT said:");
      const marker = markers[markers.length - 1] || null;
      if (marker?.parentElement) {
        const candidate = clean(marker.parentElement);
        if (candidate) {
          text = candidate;
          identity = String(turn.getAttribute("data-turn-key") || "");
          break;
        }
      }
      const clone = turn.cloneNode(true);
      clone.querySelectorAll('[data-message-author-role="user"], [data-conversation-role="user"], [data-user-message-bubble], button, [role="button"], form, textarea').forEach((item) => item.remove());
      const grouped = String(clone.textContent || "").trim();
      const anchor = grouped.lastIndexOf("ChatGPT said:");
      const candidate = anchor >= 0 ? grouped.slice(anchor + "ChatGPT said:".length).trim() : "";
      if (!candidate) continue;
      text = candidate;
      identity = String(turn.getAttribute("data-turn-key") || "");
      break;
    }
    const truncated = text.length > maxChars;
    if (truncated) text = text.slice(0, maxChars);
    return { generating, text, identity, truncated };
  }, 16_384);
  const fallbackIdentity = snapshot.text
    ? `assistant:${crypto.createHash("sha256").update(`${childUrl}\n${snapshot.text}`, "utf8").digest("hex")}`
    : "";
  return {
    ok: true,
    reason: snapshot.generating ? "child_generating" : (snapshot.text ? "child_result_ready" : "child_result_missing"),
    child_conversation_url: childUrl,
    assistant_identity: snapshot.identity || fallbackIdentity,
    assistant_text: snapshot.text,
    truncated: snapshot.truncated === true
  };
}

async function closeChild(context, payload) {
  const childUrl = requireChildUrl(payload);
  const resolved = await resolveOwnedChildPage(context, payload, { createIfMissing: false });
  if (!resolved.ok) {
    if (resolved.reason === "child_owned_tab_missing") return { ok: true, reason: "child_already_closed", child_conversation_url: childUrl };
    return { ok: false, reason: resolved.reason };
  }
  await resolved.page.close();
  ownedChildPages.delete(childUrl);
  return { ok: true, reason: "child_closed", child_conversation_url: childUrl };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const executablePath = chromeExecutable();
  const profile = browserProfile(args.profile);
  const launchOptions = {
    headless: args.headless,
    args: ["--restore-last-session"]
  };
  if (executablePath) launchOptions.executablePath = executablePath;
  const context = await chromium.launchPersistentContext(profile, launchOptions);

  let closing = false;
  async function closeContext() {
    if (closing) return;
    closing = true;
    await context.close().catch(() => null);
  }

  const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  let chain = Promise.resolve();
  input.on("line", (line) => {
    if (line.length > MAX_PROTOCOL_LINE_CHARS) {
      process.stderr.write("browser actuator request exceeded protocol bound\n");
      return;
    }
    chain = chain.then(async () => {
      let request;
      let id = 0;
      try {
        request = validateRequest(JSON.parse(line));
        id = request.id;
        let result;
        if (request.action === "wait_ready") {
          result = await waitForLoginReady(context, request.payload?.timeout_ms ?? DEFAULT_LOGIN_TIMEOUT_MS);
        } else if (request.action === "create") {
          result = await createSpawnPage(context, request.payload.intent);
        } else if (request.action === "recover_create") {
          result = await recoverOrRecreateSpawnPage(context, request.payload.intent);
        } else if (request.action === "reattach_pre_submit") {
          result = await recoverOrRecreateSpawnPage(context, request.payload.intent, "tab_reattached");
        } else if (request.action === "probe") {
          result = await probeBeforeSubmit(context, request.payload.intent);
        } else if (request.action === "submit") {
          result = await submitSpawn(context, request.payload.intent);
        } else if (request.action === "reconcile") {
          result = await reconcileSpawn(context, request.payload.intent);
        } else if (request.action === "open_child") {
          result = await openChild(context, request.payload);
        } else if (request.action === "observe_child") {
          result = await observeChild(context, request.payload);
        } else if (request.action === "close_child") {
          result = await closeChild(context, request.payload);
        } else {
          result = { ok: true, reason: "shutdown" };
          writeResponse(id, result);
          await closeContext();
          input.close();
          return;
        }
        writeResponse(id, result);
      } catch (error) {
        writeError(id || 1, error);
      }
    });
  });

  input.on("close", () => chain.finally(closeContext).catch(() => null));
  process.on("SIGINT", () => closeContext().finally(() => process.exit(130)));
  process.on("SIGTERM", () => closeContext().finally(() => process.exit(143)));
}

main().catch((error) => {
  process.stderr.write(`${String(error?.stack || error)}\n`);
  process.exitCode = 1;
});
