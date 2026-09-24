const NATIVE_HOST_NAME = "com.michalmatu.local_agent_bridge";
const NATIVE_PROTOCOL_VERSION = 1;
const NATIVE_RECONNECT_MIN_MS = 5000;
const NATIVE_RECONNECT_MAX_MS = 60000;
const NATIVE_HANDSHAKE_TIMEOUT_MS = 5000;

const nativeTransport = {
  port: null,
  reconnectTimer: null,
  handshakeTimer: null,
  reconnectDelayMs: NATIVE_RECONNECT_MIN_MS,
  handshakeReady: false,
  wanted: false
};

function clearNativeReconnectTimer() {
  if (!nativeTransport.reconnectTimer) return;
  clearTimeout(nativeTransport.reconnectTimer);
  nativeTransport.reconnectTimer = null;
}

function clearNativeHandshakeTimer() {
  if (!nativeTransport.handshakeTimer) return;
  clearTimeout(nativeTransport.handshakeTimer);
  nativeTransport.handshakeTimer = null;
}

function recordNativeDiagnostics(patch) {
  updateNativeDiagnostics(patch).catch(console.error);
}

function scheduleNativeReconnect() {
  if (!nativeTransport.wanted || nativeTransport.reconnectTimer) return;
  const delay = nativeTransport.reconnectDelayMs;
  nativeTransport.reconnectDelayMs = Math.min(
    NATIVE_RECONNECT_MAX_MS,
    nativeTransport.reconnectDelayMs * 2
  );
  nativeTransport.reconnectTimer = setTimeout(() => {
    nativeTransport.reconnectTimer = null;
    connectNativeEventHost();
  }, delay);
}

function closeNativeEventHost(reason = null, { state = "idle", reconnect = false } = {}) {
  const port = nativeTransport.port;
  nativeTransport.port = null;
  nativeTransport.handshakeReady = false;
  clearNativeHandshakeTimer();
  if (!reconnect) clearNativeReconnectTimer();
  if (port) {
    try {
      port.disconnect();
    } catch (_error) {
      // The port may already have been disconnected by Chrome.
    }
  }
  recordNativeDiagnostics({
    nativeState: state,
    nativeProtocolVersion: state === "connected" ? NATIVE_PROTOCOL_VERSION : null,
    lastDisconnectAt: new Date().toISOString(),
    lastError: state === "idle" ? null : String(reason || "native_disconnect")
  });
  if (reconnect) scheduleNativeReconnect();
}

function failNativeProtocol(reason) {
  closeNativeEventHost(reason, { state: "incompatible", reconnect: false });
}

async function acceptNativeTaskEvent(rawEvent) {
  const result = await persistNativeTaskEvent(rawEvent);
  if (!result?.ok) return result;

  let immediateScheduled = false;
  if (result.matchedChatId && result.schedulable) {
    try {
      immediateScheduled = await scheduleAt(
        result.matchedChatId,
        Date.now() + 1000,
        result.generation
      );
      if (!immediateScheduled) {
        await updateNativeDiagnostics({ lastError: "event_schedule_deferred" });
      }
    } catch (error) {
      await updateNativeDiagnostics({ lastError: `event_schedule_error:${String(error)}` });
    }
  }
  return { ...result, immediateScheduled };
}

async function handleNativeMessage(message, port) {
  if (port !== nativeTransport.port) return;
  if (!message || typeof message !== "object") {
    failNativeProtocol("native_message_invalid");
    return;
  }

  const messageType = String(message.type || "");
  const version = Number(message.protocol_version);
  if (messageType === "hello") {
    if (version !== NATIVE_PROTOCOL_VERSION || message.host_name !== NATIVE_HOST_NAME) {
      failNativeProtocol("native_protocol_mismatch");
      return;
    }
    clearNativeHandshakeTimer();
    nativeTransport.handshakeReady = true;
    nativeTransport.reconnectDelayMs = NATIVE_RECONNECT_MIN_MS;
    await updateNativeDiagnostics({
      nativeState: "connected",
      nativeProtocolVersion: version,
      lastConnectAt: new Date().toISOString(),
      lastError: null
    });
    return;
  }

  if (messageType === "error") {
    failNativeProtocol(`native_host_error:${String(message.reason || "unknown")}`);
    return;
  }

  if (messageType !== "event") {
    failNativeProtocol("native_message_type_invalid");
    return;
  }
  if (!nativeTransport.handshakeReady) {
    failNativeProtocol("native_event_before_handshake");
    return;
  }
  if (version !== NATIVE_PROTOCOL_VERSION) {
    failNativeProtocol("native_protocol_mismatch");
    return;
  }

  const result = await acceptNativeTaskEvent(message.event);
  if (!result?.ok || port !== nativeTransport.port) {
    const reason = String(result?.reason || "native_event_rejected");
    await updateNativeDiagnostics({ lastError: reason });
    if (reason === "native_event_invalid") failNativeProtocol(reason);
    return;
  }

  const eventId = String(message.event?.event_id || "");
  port.postMessage({
    type: "ack",
    protocol_version: NATIVE_PROTOCOL_VERSION,
    event_id: eventId
  });
  setTimeout(() => reconcileNativeEventTransport().catch(console.error), 0);
}

function connectNativeEventHost() {
  if (!nativeTransport.wanted || nativeTransport.port) return;
  if (typeof chrome?.runtime?.connectNative !== "function") {
    recordNativeDiagnostics({
      nativeState: "unsupported",
      nativeProtocolVersion: null,
      lastError: "native_messaging_api_unavailable"
    });
    return;
  }

  try {
    const port = chrome.runtime.connectNative(NATIVE_HOST_NAME);
    nativeTransport.port = port;
    nativeTransport.handshakeReady = false;
    recordNativeDiagnostics({
      nativeState: "connecting",
      nativeProtocolVersion: null,
      lastError: null
    });

    nativeTransport.handshakeTimer = setTimeout(() => {
      if (nativeTransport.port === port && !nativeTransport.handshakeReady) {
        closeNativeEventHost("native_handshake_timeout", {
          state: "disconnected",
          reconnect: true
        });
      }
    }, NATIVE_HANDSHAKE_TIMEOUT_MS);

    port.onMessage.addListener((message) => {
      handleNativeMessage(message, port).catch((error) => {
        console.error(error);
        if (nativeTransport.port === port) {
          closeNativeEventHost(`native_event_error:${String(error)}`, {
            state: "disconnected",
            reconnect: true
          });
        }
      });
    });
    port.onDisconnect.addListener(() => {
      if (nativeTransport.port !== port) return;
      const error = chrome.runtime.lastError?.message || "native_host_disconnected";
      nativeTransport.port = null;
      nativeTransport.handshakeReady = false;
      clearNativeHandshakeTimer();
      recordNativeDiagnostics({
        nativeState: nativeTransport.wanted ? "disconnected" : "idle",
        nativeProtocolVersion: null,
        lastDisconnectAt: new Date().toISOString(),
        lastError: nativeTransport.wanted ? error : null
      });
      scheduleNativeReconnect();
    });
    port.postMessage({ type: "hello", protocol_version: NATIVE_PROTOCOL_VERSION });
  } catch (error) {
    nativeTransport.port = null;
    nativeTransport.handshakeReady = false;
    clearNativeHandshakeTimer();
    recordNativeDiagnostics({
      nativeState: "unavailable",
      nativeProtocolVersion: null,
      lastDisconnectAt: new Date().toISOString(),
      lastError: String(error)
    });
    scheduleNativeReconnect();
  }
}

function nativeWatchIsActive(watch, bridgeState) {
  const conversation = bridgeState.conversations[watch.conversationId];
  return Boolean(
    bridgeState.settings.masterEnabled &&
    conversation?.enabled &&
    eventWakeModel.watchMatchesConversation(watch, conversation)
  );
}

async function reconcileNativeEventTransport() {
  const bridgeState = await getBridgeState();
  const eventState = await reconcileEventWakeOwnership(bridgeState);
  const wanted = Object.values(eventState.watches).some((watch) =>
    nativeWatchIsActive(watch, bridgeState)
  );
  nativeTransport.wanted = wanted;

  if (wanted) {
    connectNativeEventHost();
    return;
  }

  nativeTransport.reconnectDelayMs = NATIVE_RECONNECT_MIN_MS;
  if (nativeTransport.port || nativeTransport.reconnectTimer || nativeTransport.handshakeTimer) {
    closeNativeEventHost(null, { state: "idle", reconnect: false });
    return;
  }
  if (eventState.diagnostics.nativeState !== "idle" || eventState.diagnostics.lastError !== null) {
    await updateNativeDiagnostics({
      nativeState: "idle",
      nativeProtocolVersion: null,
      lastError: null
    });
  }
}

function initializeNativeEventTransport() {
  return reconcileNativeEventTransport().catch(console.error);
}
