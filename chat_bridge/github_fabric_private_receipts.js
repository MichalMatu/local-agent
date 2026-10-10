(function initPrivateFabricReceipts(root, factory) {
  const model = root.LocalAgentGithubFabricDispatchModel ||
    (typeof require === "function" ? require("./github_fabric_dispatch_model.js") : null);
  const api = factory(model);
  root.LocalAgentPrivateFabricReceipts = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function createPrivateFabricReceipts(dispatchModel) {
  "use strict";

  // This adapter is not imported into the production worker. A caller must
  // separately prove browser ownership, parent-mode fencing and real UI events.
  const API = "https://api.github.com/repos/MichalMatu/local-agent-fabric-private";
  const BRANCH = "fabric-data";
  const MAX_RESPONSE = 24 * 1024;
  const MAX_TEXT = 6000;
  const TOKEN_RE = /^[A-Za-z0-9_-]{12,256}$/;
  const URL_RE = /^https:\/\/chatgpt\.com\/c\/[A-Za-z0-9_-]{1,200}$/;
  const REQUEST_ID = /^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$/;

  function validateInput({ enabled, writeToken, dispatch, childRequestId }) {
    if (enabled !== true) throw new Error("Private Fabric receipt writer disabled");
    if (typeof writeToken !== "string" || !TOKEN_RE.test(writeToken)) {
      throw new Error("Private Fabric receipt write authorization missing");
    }
    if (!dispatchModel) throw new Error("Private Fabric dispatch contract unavailable");
    dispatchModel.validateDispatch(dispatch);
    if (typeof childRequestId !== "string" || !REQUEST_ID.test(childRequestId)) {
      throw new Error("Private Fabric receipt child request identity invalid");
    }
    const child = dispatch.children.find(item => item.request_id === childRequestId);
    if (!child) throw new Error("Private Fabric receipt child not in dispatch");
    return child;
  }

  function receiptPath(dispatch, childRequestId, kind) {
    if (!["claim", "ack", "result"].includes(kind)) {
      throw new Error("Private Fabric receipt kind invalid");
    }
    return "projects/local-agent/workflows/workflow-001/receipts/" +
      dispatch.id + "/" + kind + "/" + childRequestId + ".json";
  }

  function base64Encode(value) {
    const bytes = new TextEncoder().encode(JSON.stringify(value));
    if (bytes.length > MAX_RESPONSE) throw new Error("Private Fabric receipt exceeds bound");
    let output = "";
    for (const byte of bytes) output += String.fromCharCode(byte);
    return btoa(output);
  }

  function base64Decode(value) {
    if (typeof value !== "string" || value.length > MAX_RESPONSE * 2) {
      throw new Error("Private Fabric receipt base64 malformed");
    }
    const raw = atob(value.replace(/[\r\n]/g, ""));
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(
      Uint8Array.from(raw, ch => ch.charCodeAt(0))
    ));
  }

  async function boundedJson(response, url) {
    if (!response || response.redirected || (response.url && response.url !== url) ||
        !response.body?.getReader) {
      throw new Error("Private Fabric receipt GitHub response rejected");
    }
    const reader = response.body.getReader();
    const parts = [];
    let total = 0;
    try {
      while (true) {
        const next = await reader.read();
        if (next.done) break;
        total += next.value.byteLength;
        if (total > MAX_RESPONSE) throw new Error("Private Fabric receipt GitHub response oversized");
        parts.push(next.value);
      }
    } catch (_error) {
      await reader.cancel().catch(() => undefined);
      throw new Error("Private Fabric receipt GitHub response incomplete");
    } finally {
      try { reader.releaseLock(); } catch (_error) {}
    }
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const part of parts) { bytes.set(part, offset); offset += part.length; }
    try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
    catch (_error) { throw new Error("Private Fabric receipt GitHub JSON invalid"); }
  }

  async function request(fetchImpl, token, method, url, data) {
    const opts = {
      method, redirect: "error", credentials: "omit", cache: "no-store",
      headers: {
        Authorization: "Bearer " + token,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        ...(data ? { "Content-Type": "application/json" } : {})
      },
      ...(data ? { body: JSON.stringify(data) } : {})
    };
    let response;
    try { response = await fetchImpl(url, opts); }
    catch (_error) { return { status: 0, body: null }; }
    if (response.redirected || (response.url && response.url !== url)) {
      throw new Error("Private Fabric receipt GitHub redirect rejected");
    }
    if (![200, 201, 404, 409, 422].includes(response.status)) {
      throw new Error("Private Fabric receipt GitHub request rejected");
    }
    if (response.status === 404 || response.status === 409 || response.status === 422) {
      return { status: response.status, body: null };
    }
    return { status: response.status, body: await boundedJson(response, url) };
  }

  async function readExisting(fetchImpl, token, path) {
    const url = API + "/contents/" + path + "?ref=" + BRANCH;
    const response = await request(fetchImpl, token, "GET", url);
    if (response.status === 404) return null;
    if (response.status !== 200 || response.body?.encoding !== "base64" ||
        response.body?.path !== path || response.body?.type !== "file") {
      throw new Error("Private Fabric receipt existing record unavailable");
    }
    const result = base64Decode(response.body.content);
    if (!result || typeof result !== "object" || Array.isArray(result)) {
      throw new Error("Private Fabric receipt remote record invalid");
    }
    return result;
  }

  function canonical(value) {
    if (Array.isArray(value)) return value.map(canonical);
    if (value && typeof value === "object") {
      return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
    }
    return value;
  }

  async function createOnce({ writeToken, fetchImpl, path, record }) {
    const url = API + "/contents/" + path;
    const existing = await readExisting(fetchImpl, writeToken, path);
    if (existing !== null) {
      if (JSON.stringify(canonical(existing)) !== JSON.stringify(canonical(record))) {
        throw new Error("Private Fabric receipt immutable identity conflict");
      }
      return { status: "replay", path };
    }
    const result = await request(fetchImpl, writeToken, "PUT", url, {
      branch: BRANCH, message: "Record private Fabric browser evidence",
      content: base64Encode(record)
    });
    if (result.status === 201) return { status: "created", path };
    // 0 = unknown whether GitHub accepted PUT. Never issue another PUT.
    // A 409/422 race is also reconciled through an exact read, not retried.
    const reconciled = await readExisting(fetchImpl, writeToken, path);
    if (reconciled !== null) {
      if (JSON.stringify(canonical(reconciled)) !== JSON.stringify(canonical(record))) {
        throw new Error("Private Fabric receipt immutable identity conflict");
      }
      return { status: "converged", path };
    }
    return { status: "ambiguous", path };
  }

  async function claimBrowserChild({
    enabled = false, writeToken, fetchImpl = globalThis.fetch,
    dispatch, childRequestId, ownerId
  } = {}) {
    const child = validateInput({ enabled, writeToken, dispatch, childRequestId });
    if (typeof ownerId !== "string" ||
        !/^[a-f0-9]{32}$/.test(ownerId)) {
      throw new Error("Private Fabric browser claim requires immutable owner identity");
    }
    const record = {
      schema_version: 1, kind: "browser_child_claim",
      dispatch_id: dispatch.id, child_request_id: childRequestId,
      spawn_transaction_id: child.spawn.transaction_id,
      parent_conversation_url: dispatch.parent_conversation_url,
      owner_id: ownerId
    };
    return createOnce({
      writeToken, fetchImpl, path: receiptPath(dispatch, childRequestId, "claim"), record
    });
  }

  async function publishBrowserAck({
    enabled = false, writeToken, fetchImpl = globalThis.fetch,
    dispatch, childRequestId, childConversationUrl
  } = {}) {
    const child = validateInput({ enabled, writeToken, dispatch, childRequestId });
    if (typeof childConversationUrl !== "string" || !URL_RE.test(childConversationUrl)) {
      throw new Error("Private Fabric ACK requires canonical observed child URL");
    }
    const record = {
      schema_version: 1, kind: "browser_spawn_ack",
      dispatch_id: dispatch.id, child_request_id: childRequestId,
      spawn_transaction_id: child.spawn.transaction_id,
      bootstrap_digest: child.spawn.bootstrap_digest,
      child_conversation_url: childConversationUrl
    };
    const claimed = await readExisting(
      fetchImpl, writeToken, receiptPath(dispatch, childRequestId, "claim")
    );
    if (claimed?.kind !== "browser_child_claim" ||
        claimed.dispatch_id !== dispatch.id ||
        claimed.child_request_id !== childRequestId ||
        claimed.spawn_transaction_id !== child.spawn.transaction_id) {
      throw new Error("Private Fabric ACK requires durable matching child claim");
    }
    return createOnce({
      writeToken, fetchImpl, path: receiptPath(dispatch, childRequestId, "ack"), record
    });
  }

  async function publishBrowserResult({
    enabled = false, writeToken, fetchImpl = globalThis.fetch,
    dispatch, childRequestId, childConversationUrl, assistantIdentity, assistantText
  } = {}) {
    validateInput({ enabled, writeToken, dispatch, childRequestId });
    if (typeof childConversationUrl !== "string" || !URL_RE.test(childConversationUrl) ||
        typeof assistantIdentity !== "string" || !assistantIdentity || assistantIdentity.length > 256 ||
        typeof assistantText !== "string" || !assistantText.trim() || assistantText.length > MAX_TEXT) {
      throw new Error("Private Fabric terminal result evidence invalid");
    }
    const ack = await readExisting(
      fetchImpl, writeToken, receiptPath(dispatch, childRequestId, "ack")
    );
    const child = dispatch.children.find(item => item.request_id === childRequestId);
    if (ack?.kind !== "browser_spawn_ack" || ack.dispatch_id !== dispatch.id ||
        ack.child_request_id !== childRequestId ||
        ack.spawn_transaction_id !== child.spawn.transaction_id ||
        ack.bootstrap_digest !== child.spawn.bootstrap_digest ||
        ack.child_conversation_url !== childConversationUrl) {
      throw new Error("Private Fabric terminal result requires matching durable ACK");
    }
    const record = {
      schema_version: 1, kind: "browser_terminal_result",
      dispatch_id: dispatch.id, child_request_id: childRequestId,
      spawn_transaction_id: child.spawn.transaction_id,
      child_conversation_url: childConversationUrl,
      assistant_identity: assistantIdentity, assistant_text: assistantText
    };
    return createOnce({
      writeToken, fetchImpl, path: receiptPath(dispatch, childRequestId, "result"), record
    });
  }

  return Object.freeze({
    API, BRANCH, receiptPath, claimBrowserChild, publishBrowserAck, publishBrowserResult
  });
});
