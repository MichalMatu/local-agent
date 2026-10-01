"use strict";

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
const ALLOWED_ACTIONS = new Set([
  "wait_ready",
  "create",
  "recover_create",
  "probe",
  "submit",
  "reconcile",
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

async function pageComposerReady(page) {
  if (!page || page.isClosed() || !canonicalChatHome(page.url())) return false;
  try {
    return await page.locator(composerSelector()).first().isVisible({ timeout: 500 });
  } catch (_error) {
    return false;
  }
}

async function waitForLoginReady(context, timeoutMs) {
  boundedInteger(timeoutMs, {
    minimum: 1_000,
    maximum: 30 * 60 * 1000,
    field: "login timeout_ms"
  });
  const page = await context.newPage();
  try {
    await page.goto("https://chatgpt.com/", {
      waitUntil: "domcontentloaded",
      timeout: Math.min(timeoutMs, 30_000)
    }).catch(() => null);
    const deadline = Date.now() + timeoutMs;
    let nextNotice = 0;
    while (Date.now() < deadline) {
      if (await pageComposerReady(page)) {
        return { ok: true, reason: "chatgpt_ready", url: page.url() };
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
  const existing = context.serviceWorkers().find((worker) =>
    worker.url().startsWith("chrome-extension://") && worker.url().endsWith("/service_worker.js")
  );
  if (existing) return existing;

  const candidate = await Promise.race([
    context.waitForEvent("serviceworker", { timeout: 8_000 }),
    (async () => {
      await new Promise((resolve) => setTimeout(resolve, 300));
      return null;
    })()
  ]).catch(() => null);
  if (candidate?.url().startsWith("chrome-extension://")) return candidate;

  for (const worker of context.serviceWorkers()) {
    if (worker.url().startsWith("chrome-extension://")) return worker;
  }
  throw new Error("DEV Chat Bridge service worker is unavailable");
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

async function workerExpression(context, expression) {
  const worker = await extensionWorker(context);
  return worker.evaluate(`Promise.resolve(${expression})`);
}

async function recoverCreate(context, intent) {
  const transactionId = String(intent?.transaction_id || "");
  if (!/^spawn-[0-9a-f]{64}$/.test(transactionId)) {
    throw new Error("conversation spawn transaction_id is invalid");
  }
  return workerExpression(
    context,
    `findConversationSpawnMarkerTabs(${JSON.stringify(transactionId)}).then((tabs) => {` +
      `if (tabs.length === 0) return {ok:false,reason:"spawn_create_recovery_missing"};` +
      `if (tabs.length > 1) return {ok:false,reason:"spawn_create_recovery_conflict"};` +
      `return {ok:true,reason:"tab_recovered",tabId:tabs[0].id};` +
    `})`
  );
}

async function probeBeforeSubmit(context, intent) {
  const tabId = Number(intent?.tab_id || 0);
  if (!Number.isInteger(tabId) || tabId < 1) {
    return { ok: false, reason: "spawn_tab_unavailable" };
  }
  const content = await callWorker(context, "probeConversationSpawnContent", tabId);
  if (!content?.ok) return content || { ok: false, reason: "spawn_content_unavailable" };
  if (content.route !== "fresh") {
    return { ok: false, reason: "spawn_unexpected_route", route: content.route || "unknown" };
  }
  const readiness = content.readiness;
  if (!readiness || typeof readiness !== "object" || typeof readiness.ok !== "boolean") {
    return { ok: false, reason: "spawn_readiness_unavailable" };
  }
  return readiness;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  fs.mkdirSync(args.profile, { recursive: true });
  const context = await chromium.launchPersistentContext(args.profile, {
    headless: args.headless,
    args: [
      `--disable-extensions-except=${args.extension}`,
      `--load-extension=${args.extension}`
    ]
  });

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
        } else if (request.action === "probe") {
          result = await probeBeforeSubmit(context, request.payload.intent);
        } else if (request.action === "submit") {
          result = await callWorker(context, "submitConversationSpawnBootstrap", request.payload.intent);
        } else if (request.action === "reconcile") {
          result = await callWorker(context, "reconcileConversationSpawn", request.payload.intent);
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
