// Optional task-completion hint for one existing GitHub-managed Chrome parent.
// This module schedules the ordinary wake alarm, never sends a ChatGPT prompt.
const TASK_RESULT_WAKE_RECEIPTS_KEY = "bridgeTaskResultWakeReceiptsV1";
const TASK_RESULT_WAKE_LIMIT = 128;
const TASK_RESULT_WAKE_MAX_BYTES = 256 * 1024;
const TASK_RESULT_WAKE_FETCH_TIMEOUT_MS = 5000;
let taskResultWakeQueue = Promise.resolve();

async function readGithubTaskResultTerminal(repository, taskId) {
  const parts = String(repository).split("/");
  if (parts.length !== 2 ||
      !parts.every((part) => /^[A-Za-z0-9_.-]+$/.test(part)) ||
      !/^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/.test(taskId)) {
    throw new Error("task completion watch locator is invalid");
  }
  const url = `https://raw.githubusercontent.com/${parts[0]}/${parts[1]}/agent-control/.agent/results/${taskId}.json?ts=${Date.now()}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TASK_RESULT_WAKE_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url, { cache: "no-store", signal: controller.signal });
    if (response.status === 404) return false;
    if (!response.ok) throw new Error(`task completion read returned HTTP ${response.status}`);
    if (!response.body?.getReader) throw new Error("task completion read requires bounded streaming");
    const reader = response.body.getReader();
    const chunks = [];
    let total = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        total += value.byteLength;
        if (total > TASK_RESULT_WAKE_MAX_BYTES) {
          try { await reader.cancel(); } catch (_error) {}
          throw new Error("task completion result exceeds byte limit");
        }
        chunks.push(value);
      }
    } finally {
      try { reader.releaseLock(); } catch (_error) {}
    }
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    const result = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    if (!result || result.id !== taskId || typeof result.status !== "string") {
      throw new Error("task completion result identity is invalid");
    }
    return ["done", "failed", "cancelled"].includes(result.status);
  } finally {
    clearTimeout(timeout);
  }
}

async function pollGithubTaskResultWakesOnce() {
  const state = await getBridgeState();
  if (!state.settings.masterEnabled) return { triggered: 0, status: "master_disabled" };
  const [runtime, applied] = await Promise.all([
    fetchRuntime(state.settings),
    readAppliedGithubControls()
  ]);
  if (runtime.source !== "remote") return { triggered: 0, status: "runtime_unavailable" };
  let triggered = 0;
  for (const control of runtime.conversationControls) {
    if (!control.enabled || !control.taskResultWatch) continue;
    const conversation = state.conversations?.[control.conversationId];
    const cached = applied[control.conversationId];
    if (!conversation?.enabled ||
        !stateModel.isTransportReady(conversation) ||
        cached?.generation !== control.controlGeneration ||
        cached?.controlSignature !== githubControlSignature(control)) continue;

    const receiptId = `${control.conversationId}:${control.controlGeneration}`;
    const old = (await chrome.storage.local.get(TASK_RESULT_WAKE_RECEIPTS_KEY))[TASK_RESULT_WAKE_RECEIPTS_KEY] || {};
    if (Object.hasOwn(old, receiptId)) continue;

    const agent = runtime.agents.find((item) =>
      item.repositoryId === control.taskResultWatch.repositoryId &&
      item.executionEnabled === true
    );
    if (!agent) continue;

    let terminal = false;
    try {
      terminal = await readGithubTaskResultTerminal(agent.repository, control.taskResultWatch.taskId);
    } catch (error) {
      console.warn("Task result wake read unavailable:", String(error));
      continue;
    }
    if (!terminal) continue;

    // The GET is a hint only. Recheck live local/remote authority immediately
    // before touching a Chrome alarm, not after the next poll/restart.
    const latest = await getBridgeState();
    const live = latest.conversations?.[control.conversationId];
    const current = (await readAppliedGithubControls())[control.conversationId];
    if (!latest.settings.masterEnabled || !live?.enabled ||
        !stateModel.isTransportReady(live) ||
        current?.generation !== control.controlGeneration ||
        current.controlSignature !== githubControlSignature(control) ||
        current.localGeneration !== live.generation) continue;

    // A durable at-most-once claim is written before advancing a wake deadline.
    // Ambiguous alarm scheduling is consumed rather than retried after restart.
    const prior = (await chrome.storage.local.get(TASK_RESULT_WAKE_RECEIPTS_KEY))[TASK_RESULT_WAKE_RECEIPTS_KEY] || {};
    if (Object.hasOwn(prior, receiptId)) continue;
    const receipts = Object.entries({ ...prior, [receiptId]: Date.now() })
      .sort((a, b) => b[1] - a[1])
      .slice(0, TASK_RESULT_WAKE_LIMIT);
    await chrome.storage.local.set({ [TASK_RESULT_WAKE_RECEIPTS_KEY]: Object.fromEntries(receipts) });
    await scheduleAt(control.conversationId, Date.now() + 1000, live.generation);
    triggered++;
  }
  return { triggered, status: "checked" };
}

function pollGithubTaskResultWakes() {
  const pending = taskResultWakeQueue
    .catch(() => undefined)
    .then(pollGithubTaskResultWakesOnce);
  taskResultWakeQueue = pending.catch(() => undefined);
  return pending;
}
