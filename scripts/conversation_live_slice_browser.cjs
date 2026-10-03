"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline");

let chromium;
try {
  ({ chromium } = require(process.env.LOCAL_AGENT_PLAYWRIGHT_MODULE || "playwright"));
} catch (error) {
  process.stderr.write(
    "Conversation live slice requires Playwright. Install the pinned DEV dependency with " +
    "`npm install --no-save --package-lock=false playwright@1.57.0` and " +
    "`npx playwright install chromium`.\n"
  );
  throw error;
}

const MAX_PROTOCOL_LINE_CHARS = 128 * 1024;
const DEFAULT_LOGIN_TIMEOUT_MS = 10 * 60 * 1000;
const AUTH_SESSION_PROBE_TIMEOUT_MS = 1500;
const PRE_SUBMIT_CONTENT_WAIT_MS = 5000;
const PRE_SUBMIT_COMPOSER_STABILIZATION_MS = 30000;
const CHILD_TRANSACTION_RE = /^spawn-[0-9a-f]{64}$/;
const CHILD_DIGEST_RE = /^sha256:[0-9a-f]{64}$/;
const CHILD_CLAIM_PREFIX = "local-agent:conversation-spawn:";
const ownedChildPages = new Map();
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
    else if (arg === "--extension") parsed.extension = argv[++index] || "";
    else if (arg === "--headless") parsed.headless = true;
    else throw new Error(`unsupported live slice browser argument: ${arg}`);
  }
  if (!parsed.profile || !path.isAbsolute(parsed.profile)) {
    throw new Error("--profile must be an absolute DEV browser profile path");
  }
  if (!parsed.extension || !path.isAbsolute(parsed.extension)) {
    throw new Error("--extension must be an absolute DEV Chat Bridge path");
  }
  if (!fs.statSync(parsed.extension).isDirectory()) {
    throw new Error("DEV Chat Bridge extension path is not a directory");
  }
  return parsed;
}

function optionalChromeExecutable() {
  const candidate = String(process.env.LOCAL_AGENT_CHROME_EXECUTABLE || "").trim();
  if (!candidate) return null;
  if (!path.isAbsolute(candidate)) {
    throw new Error("LOCAL_AGENT_CHROME_EXECUTABLE must be an absolute path");
  }
  const stats = fs.statSync(candidate);
  if (!stats.isFile()) {
    throw new Error("LOCAL_AGENT_CHROME_EXECUTABLE must point to a file");
  }
  fs.accessSync(candidate, fs.constants.X_OK);
  return candidate;
}

function requireSafeDirectoryIfPresent(candidate, field) {
  if (!fs.existsSync(candidate)) return;
  const stats = fs.lstatSync(candidate);
  if (stats.isSymbolicLink()) throw new Error(`${field} must not be a symlink: ${candidate}`);
  if (!stats.isDirectory()) throw new Error(`${field} must be a directory: ${candidate}`);
}

function resetEphemeralServiceWorkerState(profile) {
  const parent = path.dirname(profile);
  requireSafeDirectoryIfPresent(parent, "DEV browser profile parent");
  requireSafeDirectoryIfPresent(profile, "DEV browser profile");
  fs.mkdirSync(profile, { recursive: true });
  const defaultProfile = path.join(profile, "Default");
  requireSafeDirectoryIfPresent(defaultProfile, "DEV browser Default profile");
  const serviceWorker = path.join(defaultProfile, "Service Worker");
  requireSafeDirectoryIfPresent(serviceWorker, "DEV browser Service Worker state");
  if (fs.existsSync(serviceWorker)) fs.rmSync(serviceWorker, { recursive: true, force: true });
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

function requireChildUrl(payload) {
  const raw = String(payload?.child_conversation_url || "");
  const canonical = canonicalConversationUrl(raw);
  if (!canonical || canonical !== raw) throw new Error("child lifecycle action requires canonical child_conversation_url");
  return canonical;
}

function exactChildPages(context, childUrl) {
  return context.pages().filter((page) => !page.isClosed() && canonicalConversationUrl(page.url()) === childUrl);
}

function childOwnership(payload) {
  const raw = payload?.ownership;
  if (raw === undefined || raw === null) return null;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    throw new Error("child ownership must be an object");
  }
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
  return (
    left.transactionId === right.transactionId &&
    left.childRequestDigest === right.childRequestDigest &&
    left.bootstrapDigest === right.bootstrapDigest
  );
}

async function pageMatchesChildOwnership(page, ownership) {
  if (!ownership || page.isClosed()) return false;
  try {
    return await page.evaluate(({ prefix, transactionId, childRequestDigest, bootstrapDigest }) => {
      try {
        const raw = sessionStorage.getItem(`${prefix}${transactionId}`);
        if (!raw) return false;
        const claim = JSON.parse(raw);
        return Boolean(
          claim &&
          claim.transactionId === transactionId &&
          claim.childRequestDigest === childRequestDigest &&
          claim.bootstrapDigest === bootstrapDigest &&
          ["submitting", "submitted"].includes(String(claim.state || ""))
        );
      } catch (_error) {
        return false;
      }
    }, { prefix: CHILD_CLAIM_PREFIX, ...ownership });
  } catch (_error) {
    return false;
  }
}

async function resolveOwnedChildPage(context, payload, { createIfMissing }) {
  const childUrl = requireChildUrl(payload);
  const ownership = childOwnership(payload);
  const cached = ownedChildPages.get(childUrl);
  if (
    cached?.page &&
    !cached.page.isClosed() &&
    canonicalConversationUrl(cached.page.url()) === childUrl
  ) {
    if (!sameChildOwnership(cached.ownership, ownership)) {
      return { ok: false, reason: "child_ownership_conflict", childUrl };
    }
    if (
      cached.source === "spawn_claim" &&
      ownership &&
      !await pageMatchesChildOwnership(cached.page, ownership)
    ) {
      ownedChildPages.delete(childUrl);
      return { ok: false, reason: "child_ownership_conflict", childUrl };
    }
    return {
      ok: true,
      page: cached.page,
      childUrl,
      ownership,
      source: "actuator_owned"
    };
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

  if (!createIfMissing) {
    return { ok: false, reason: "child_owned_tab_missing", childUrl };
  }
  const page = await context.newPage();
  await page.goto(childUrl, { waitUntil: "domcontentloaded", timeout: 15000 }).catch(() => null);
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline && canonicalConversationUrl(page.url()) !== childUrl) {
    await page.waitForTimeout(100);
  }
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
  return {
    ok: true,
    reason: "child_opened",
    child_conversation_url: resolved.childUrl,
    ownership_source: resolved.source
  };
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
      clone.querySelectorAll(
        '[data-message-author-role="user"], [data-conversation-role="user"], [data-user-message-bubble], button, [role="button"], form, textarea, .sr-only'
      ).forEach((item) => item.remove());
      return String(clone.textContent || "").trim();
    };
    const markerSelectors = 'h1,h2,h3,h4,h5,h6,[data-message-author-role="assistant"],[data-conversation-role="assistant"]';
    let text = "";
    let identity = "";
    const turns = Array.from(document.querySelectorAll('[data-turn-key]'));
    for (let index = turns.length - 1; index >= 0; index -= 1) {
      const turn = turns[index];
      const markers = Array.from(turn.querySelectorAll(markerSelectors)).filter(
        (item) => String(item.textContent || "").trim() === "ChatGPT said:"
      );
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
      clone.querySelectorAll(
        '[data-message-author-role="user"], [data-conversation-role="user"], [data-user-message-bubble], button, [role="button"], form, textarea'
      ).forEach((item) => item.remove());
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
  }, 16384);
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
    if (resolved.reason === "child_owned_tab_missing") {
      return { ok: true, reason: "child_already_closed", child_conversation_url: childUrl };
    }
    return { ok: false, reason: resolved.reason };
  }
  await resolved.page.close();
  ownedChildPages.delete(childUrl);
  return { ok: true, reason: "child_closed", child_conversation_url: childUrl };
}

async function pageComposerReady(page) {
  if (!page || page.isClosed() || !canonicalChatHome(page.url())) return false;
  try {
    return await page.locator(composerSelector()).first().isVisible({ timeout: 500 });
  } catch (_error) {
    return false;
  }
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
        const response = await fetch('/api/auth/session', {
          credentials: 'include',
          cache: 'no-store',
          signal: controller.signal
        });
        if (!response.ok) return false;
        const session = await response.json().catch(() => null);
        return Boolean(
          session && typeof session === 'object' &&
          session.user && typeof session.user === 'object'
        );
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
  if (!page || page.isClosed() || !canonicalChatHome(page.url())) return false;
  if (await pageAccountControlReady(page)) return true;
  return pageSessionAuthenticated(page);
}

async function waitForLoginReady(context, timeoutMs) {
  boundedInteger(timeoutMs, {
    minimum: 1_000,
    maximum: 30 * 60 * 1000,
    field: "login timeout_ms"
  });
  const deadline = Date.now() + timeoutMs;
  const page = await context.newPage();
  try {
    const navigationBudget = Math.max(1, deadline - Date.now());
    await page.goto("https://chatgpt.com/", {
      waitUntil: "domcontentloaded",
      timeout: Math.min(navigationBudget, 5_000)
    }).catch(() => null);
    let nextNotice = 0;
    let nextAuthProbe = 0;
    while (Date.now() < deadline) {
      const composerReady = await pageComposerReady(page);
      if (composerReady && Date.now() >= nextAuthProbe) {
        if (await pageAuthenticated(page)) {
          return { ok: true, reason: "chatgpt_ready", url: page.url() };
        }
        nextAuthProbe = Date.now() + 1000;
      }
      if (Date.now() >= nextNotice) {
        process.stderr.write(
          "DEV live slice browser is waiting for ChatGPT login in the isolated profile.\n"
        );
        nextNotice = Date.now() + 15_000;
      }
      await page.waitForTimeout(250);
    }
    return { ok: false, reason: "chatgpt_login_timeout", url: page.url() };
  } finally {
    await page.close().catch(() => null);
  }
}

async function extensionWorker(context) {
  const deadline = Date.now() + 8_000;
  while (true) {
    const existing = context.serviceWorkers().find((worker) =>
      worker.url().startsWith("chrome-extension://") && worker.url().endsWith("/service_worker.js")
    );
    if (existing) return existing;
    const remaining = deadline - Date.now();
    if (remaining <= 0) break;
    await new Promise((resolve) => setTimeout(resolve, Math.min(100, remaining)));
  }
  throw new Error("DEV Chat Bridge service worker is unavailable after bounded startup wait");
}

function safeFunctionName(value) {
  const name = String(value || "");
  if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(name)) throw new Error("invalid worker function name");
  return name;
}

async function callWorker(context, name, value) {
  const worker = await extensionWorker(context);
  const functionName = safeFunctionName(name);
  const expression = `Promise.resolve(${functionName}(${JSON.stringify(value)}))`;
  return worker.evaluate(expression);
}

async function recoverCreate(context, intent) {
  const recovered = await callWorker(context, "recoverConversationSpawnTab", intent);
  return recovered || { ok: false, reason: "spawn_create_recovery_missing" };
}

async function reattachPreSubmit(context, intent) {
  const originalTabId = Number(intent?.tab_id || 0);
  if (!Number.isInteger(originalTabId) || originalTabId < 1) {
    throw new Error("pre-submit reattach requires the durable original tab_id");
  }
  return callWorker(context, "reattachConversationSpawnTab", intent);
}

async function probeBeforeSubmit(context, intent) {
  const tabId = Number(intent?.tab_id || 0);
  if (!Number.isInteger(tabId) || tabId < 1) {
    return { ok: false, reason: "spawn_tab_unavailable" };
  }
  const contentDeadline = Date.now() + PRE_SUBMIT_CONTENT_WAIT_MS;
  let readinessDeadline = null;
  while (true) {
    const content = await callWorker(context, "ensureConversationSpawnContent", tabId);
    if (!content?.ok) {
      if (
        ["spawn_content_unavailable", "spawn_page_not_ready"].includes(String(content?.reason || "")) &&
        Date.now() < contentDeadline
      ) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        continue;
      }
      return content || { ok: false, reason: "spawn_content_unavailable" };
    }
    if (content.route !== "fresh") {
      return { ok: false, reason: "spawn_unexpected_route", route: content.route || "unknown" };
    }
    if (readinessDeadline === null) {
      readinessDeadline = Date.now() + PRE_SUBMIT_COMPOSER_STABILIZATION_MS;
    }
    const readiness = content.readiness;
    if (!readiness || typeof readiness !== "object" || typeof readiness.ok !== "boolean") {
      return { ok: false, reason: "spawn_readiness_unavailable" };
    }
    if (readiness.ok) return readiness;
    if (!["spawn_page_not_ready", "spawn_composer_not_found"].includes(String(readiness.reason || ""))) {
      return readiness;
    }
    if (Date.now() >= readinessDeadline) return readiness;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const executablePath = optionalChromeExecutable();
  resetEphemeralServiceWorkerState(args.profile);
  const launchOptions = {
    headless: args.headless,
    args: [
      "--restore-last-session",
      `--disable-extensions-except=${args.extension}`,
      `--load-extension=${args.extension}`
    ]
  };
  if (executablePath) launchOptions.executablePath = executablePath;
  const context = await chromium.launchPersistentContext(args.profile, launchOptions);

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
          const timeoutMs = request.payload?.timeout_ms ?? DEFAULT_LOGIN_TIMEOUT_MS;
          result = await waitForLoginReady(context, timeoutMs);
        } else if (request.action === "create") {
          result = await callWorker(context, "createConversationSpawnTab", request.payload.intent);
        } else if (request.action === "recover_create") {
          result = await recoverCreate(context, request.payload.intent);
        } else if (request.action === "reattach_pre_submit") {
          result = await reattachPreSubmit(context, request.payload.intent);
        } else if (request.action === "probe") {
          result = await probeBeforeSubmit(context, request.payload.intent);
        } else if (request.action === "submit") {
          result = await callWorker(context, "submitConversationSpawnBootstrap", request.payload.intent);
        } else if (request.action === "reconcile") {
          result = await callWorker(context, "reconcileConversationSpawn", request.payload.intent);
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

  input.on("close", () => {
    chain.finally(closeContext).catch(() => null);
  });
  process.on("SIGINT", () => closeContext().finally(() => process.exit(130)));
  process.on("SIGTERM", () => closeContext().finally(() => process.exit(143)));
}

main().catch((error) => {
  process.stderr.write(`${String(error?.stack || error)}\n`);
  process.exitCode = 1;
});
