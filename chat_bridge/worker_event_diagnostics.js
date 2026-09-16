async function eventWakeInspection(chatId) {
  const bridgeState = await getBridgeState();
  const state = await reconcileEventWakeOwnership(bridgeState);
  const watch = state.watches[chatId] || null;
  const pending = state.pendingWakes[chatId] || null;
  const diagnostics = state.diagnostics;

  return {
    supported: true,
    mode: "native_messaging_on_demand_with_alarm_fallback",
    transport: {
      state: diagnostics.nativeState,
      protocolVersion: diagnostics.nativeProtocolVersion,
      lastConnectAt: diagnostics.lastConnectAt,
      lastDisconnectAt: diagnostics.lastDisconnectAt,
      lastError: diagnostics.lastError
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
    recentEventCount: Object.keys(state.recentEvents).length,
    lastAcceptedEventId: diagnostics.lastAcceptedEventId,
    lastAcceptedTaskId: diagnostics.lastAcceptedTaskId,
    lastAcceptedAt: diagnostics.lastAcceptedAt,
    lastDeliveredEventId: diagnostics.lastDeliveredEventId,
    lastDeliveredAt: diagnostics.lastDeliveredAt
  };
}
