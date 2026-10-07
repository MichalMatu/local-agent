/* Read-only GitHub-first Fabric intake. No Chrome tab operations or campaign activation.
 * A single existing GitHub-control alarm is the only production poll owner.
 */
const githubFabricIntakeModel = globalThis.LocalAgentGithubFabricIntakeModel;
const githubFabricDispatchModel = globalThis.LocalAgentGithubFabricDispatchModel;
const GITHUB_FABRIC_SEEN_KEY = "bridgeGithubFabricReadOnlySeen";
const GITHUB_FABRIC_FETCH_TIMEOUT_MS = 5000;
let githubFabricIntakeQueue = Promise.resolve();

async function readBoundedGithubFabricJson(url, maximum) {
  const abort = new AbortController();
  const timeout = setTimeout(() => abort.abort(), GITHUB_FABRIC_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(url + "?ts=" + Date.now(), {
      cache: "no-store",
      signal: abort.signal
    });
    if (!response.ok) throw new Error("GitHub Fabric read returned HTTP " + response.status);
    if (!response.body?.getReader) {
      throw new Error("GitHub Fabric intake requires bounded streaming response");
    }
    const reader = response.body.getReader();
    const chunks = [];
    let size = 0;
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > maximum) {
          try { await reader.cancel(); } catch (_error) {}
          throw new Error("GitHub Fabric intake response exceeds bound");
        }
        chunks.push(value);
      }
    } finally {
      try { reader.releaseLock(); } catch (_error) {}
    }
    const bytes = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      bytes.set(chunk, offset);
      offset += chunk.byteLength;
    }
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  } finally {
    clearTimeout(timeout);
  }
}

async function pollGithubFabricReadOnlyIntakeOnce() {
  const state = await getBridgeState();
  if (!state.settings.masterEnabled) return { ok: true, status: "master_disabled" };
  const runtime = await fetchRuntime(state.settings);
  if (runtime.source !== "remote" || runtime.githubFabricReadOnlyIntakeEnabled !== true) {
    return { ok: true, status: "disabled" };
  }
  const runtimeUrl = state.settings.runtimeUrl;
  const index = githubFabricIntakeModel.validateIndex(
    await readBoundedGithubFabricJson(
      githubFabricIntakeModel.indexUrl(runtimeUrl),
      githubFabricIntakeModel.MAX_INDEX_BYTES
    )
  );
  const stored = await chrome.storage.local.get(GITHUB_FABRIC_SEEN_KEY);
  let seen = stored[GITHUB_FABRIC_SEEN_KEY] || {};
  const result = { ok: true, status: "read_only", stored: 0, replayed: 0, conflicts: 0, skipped: 0 };
  for (const id of index.dispatch_ids) {
    const dispatch = githubFabricDispatchModel.validateDispatch(
      await readBoundedGithubFabricJson(
        githubFabricIntakeModel.dispatchUrl(runtimeUrl, id),
        githubFabricDispatchModel.MAX_DISPATCH_BYTES
      )
    );
    if (dispatch.id !== id) throw new Error("GitHub Fabric intake dispatch path identity mismatch");
    const chatId = conversationId(dispatch.parent_conversation_url);
    const conversation = state.conversations?.[chatId];
    const control = githubControlModel.findConversationControl(runtime, chatId);
    if (!conversation || !conversation.enabled || !control?.enabled ||
        !githubControlModel.controlMatchesConversation(control, conversation)) {
      result.skipped++;
      continue;
    }
    for (const child of dispatch.children) {
      const intent = githubFabricDispatchModel.toConversationSpawnIntent(child);
      await requireConversationSpawnBootstrapDigest(intent);
    }
    const fingerprint = await conversationSpawnSha256(githubFabricDispatchModel.canonicalJson(dispatch));
    const admitted = githubFabricIntakeModel.reconcileSeenDispatch(seen, id, fingerprint);
    if (admitted.status === "capacity") {
      throw new Error("GitHub Fabric intake identity capacity exhausted; explicit operator recovery required");
    }
    if (admitted.status === "conflict") {
      result.conflicts++;
      continue;
    }
    if (admitted.status === "stored") {
      seen = admitted.seen;
      await chrome.storage.local.set({ [GITHUB_FABRIC_SEEN_KEY]: seen });
      result.stored++;
    } else {
      result.replayed++;
    }
  }
  return result;
}

function pollGithubFabricReadOnlyIntake() {
  const pending = githubFabricIntakeQueue
    .catch(() => undefined)
    .then(pollGithubFabricReadOnlyIntakeOnce);
  githubFabricIntakeQueue = pending.catch(() => undefined);
  return pending;
}
