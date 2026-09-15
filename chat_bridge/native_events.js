const NATIVE_HOST_NAME = "com.michalmatu.local_agent_bridge";
const NATIVE_PROTOCOL_VERSION = 1;
const NATIVE_RECONNECT_MIN_MS = 5000;
const NATIVE_RECONNECT_MAX_MS = 60000;

let nativePort = null;
let nativeReconnectTimer = null;
let nativeReconnectDelayMs = NATIVE_RECONNECT_MIN_MS;
let nativeHandshakeReady = false;

function scheduleNativeReconnect() {
  if (nativeReconnectTimer) return;
  const delay = nativeReconnectDelayMs;
  nativeReconnectDelayMs = Math.min(NATIVE_RECONNECT_MAX_MS, nativeReconnectDelayMs * 2);
  nativeReconnectTimer = setTimeout(() => {
    nativeReconnectTimer = null;
    connectNativeEventHost();
  }, delay);
}

function disconnectNativeEventHost(reason = "native_disconnect") {
  const port = nativePort;
  nativePort = null;
  nativeHandshakeReady = false;
  if (port) {
    try {
      port.disconnect();
    } catch (_error) {
      // Port may already be disconnected.
    }
  }
  updateNativeDiagnostics({
    nativeState: "disconnected",
    lastDisconnectAt: new Date().toISOString(),
    lastError: reason
  }).catch(console.error);
}

async function handleNativeMessage(message, port) {
  if (!message || typeof message !== "object") return;
  const messageType = String(message.type || "");
  const version = Number(message.protocol_version);

  if (messageType === "hello") {
    if (version !== NATIVE_PROTOCOL_VERSION || message.host_name !== NATIVE_HOST_NAME) {
      disconnectNativeEventHost("native_protocol_mismatch");
      return;
    }
    nativeHandshakeReady = true;
    nativeReconnectDelayMs = NATIVE_RECONNECT_MIN_MS;
    await updateNativeDiagnostics({
      nativeState: "connected",
      nativeProtocolVersion: version,
      lastConnectAt: new Date().toISOString(),
      lastError: null
    });
    return;
  }

  if (messageType !== "event" || !nativeHandshakeReady || version !== NATIVE_PROTOCOL_VERSION) return;
  const result = await acceptNativeTaskEvent(message.event);
  if (!result?.ok || port !== nativePort) {
    await updateNativeDiagnostics({ lastError: String(result?.reason || "native_event_rejected") });
    return;
  }
  const eventId = String(message.event?.event_id || "");
  port.postMessage({
    type: "ack",
    protocol_version: NATIVE_PROTOCOL_VERSION,
    event_id: eventId
  });
}

function connectNativeEventHost() {
  if (nativePort) return;
  try {
    const port = chrome.runtime.connectNative(NATIVE_HOST_NAME);
    nativePort = port;
    nativeHandshakeReady = false;
    updateNativeDiagnostics({ nativeState: "connecting", lastError: null }).catch(console.error);

    port.onMessage.addListener((message) => {
      handleNativeMessage(message, port).catch(async (error) => {
        console.error(error);
        await updateNativeDiagnostics({ lastError: `native_event_error:${String(error)}` });
      });
    });
    port.onDisconnect.addListener(() => {
      if (nativePort !== port) return;
      const error = chrome.runtime.lastError?.message || "native_host_disconnected";
      nativePort = null;
      nativeHandshakeReady = false;
      updateNativeDiagnostics({
        nativeState: "disconnected",
        lastDisconnectAt: new Date().toISOString(),
        lastError: error
      }).catch(console.error);
      scheduleNativeReconnect();
    });
    port.postMessage({ type: "hello", protocol_version: NATIVE_PROTOCOL_VERSION });
  } catch (error) {
    nativePort = null;
    nativeHandshakeReady = false;
    updateNativeDiagnostics({
      nativeState: "unavailable",
      lastDisconnectAt: new Date().toISOString(),
      lastError: String(error)
    }).catch(console.error);
    scheduleNativeReconnect();
  }
}

function initializeNativeEventTransport() {
  connectNativeEventHost();
}
