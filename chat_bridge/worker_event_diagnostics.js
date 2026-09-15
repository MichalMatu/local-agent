async function eventWakeInspection(chatId) {
  const state = await loadEventWakeState();
  const watch = state.watches[chatId] || null;
  const pending = state.pendingWakes[chatId] || null;
  const diagnostics = state.diagnostics || {};

  return {
    supported: true,
    mode: "native_messaging_on_demand_with_alarm_fallback",
    transport: {
      state: String(diagnostics.nativeState || "unknown"),
      protocolVersion: diagnostics.nativeProtocolVersion ?? null,
      lastConnectAt: diagnostics.lastConnectAt || null,
      lastDisconnectAt: diagnostics.lastDisconnectAt || null,
      lastError: diagnostics.lastError || null
    },
    currentWatch: watch
      ? {
          repositoryId: watch.repositoryId,
          repository: watch.repository,
          taskId: watch.taskId,
          createdAt: watch.createdAt
        }
      : null,
    pendingWake: pending
      ? {
          eventId: pending.eventId,
          taskId: pending.taskId,
          receivedAt: pending.receivedAt
        }
      : null,
    recentEventCount: Object.keys(state.recentEvents || {}).length,
    lastAcceptedEventId: diagnostics.lastAcceptedEventId || null,
    lastAcceptedTaskId: diagnostics.lastAcceptedTaskId || null,
    lastAcceptedAt: diagnostics.lastAcceptedAt || null,
    lastDeliveredEventId: diagnostics.lastDeliveredEventId || null,
    lastDeliveredAt: diagnostics.lastDeliveredAt || null
  };
}
