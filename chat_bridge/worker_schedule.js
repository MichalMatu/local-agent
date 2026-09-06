function alarmName(chatId) {
  return `${ALARM_PREFIX}${chatId}`;
}

async function getScheduleSnapshot(state) {
  const alarms = await chrome.alarms.getAll();
  const alarmByName = new Map(alarms.map((alarm) => [alarm.name, alarm]));
  return Object.fromEntries(
    Object.values(state.conversations).map((conversation) => {
      const alarm = alarmByName.get(alarmName(conversation.id));
      const when = Number(alarm?.scheduledTime ?? alarm?.when);
      return [conversation.id, {
        scheduled: Number.isFinite(when),
        nextRunAt: Number.isFinite(when) ? new Date(when).toISOString() : null
      }];
    })
  );
}

async function clearConversationAlarm(chatId, expectedGeneration = null, clearNextRunAt = true) {
  await mutateState(async (state) => {
    const conversation = state.conversations[chatId];
    if (expectedGeneration !== null && conversation?.generation !== expectedGeneration) return state;
    await chrome.alarms.clear(alarmName(chatId));
    if (!conversation || !clearNextRunAt) return state;
    return stateModel.patchConversation(state, chatId, { nextRunAt: null }).state;
  });
}

async function scheduleAt(chatId, when, expectedGeneration = null) {
  const result = await mutateState(async (state) => {
    const conversation = state.conversations[chatId];
    if (!conversation || !conversation.enabled || !stateModel.isBoundConversation(conversation)) {
      await chrome.alarms.clear(alarmName(chatId));
      return { state, value: false };
    }
    if (expectedGeneration !== null && conversation.generation !== expectedGeneration) {
      return { state, value: false };
    }
    const safeWhen = Math.max(Date.now() + 1000, Number(when));
    if (!Number.isFinite(safeWhen)) throw new Error("invalid alarm deadline");

    if (state.settings.masterEnabled) {
      await chrome.alarms.create(alarmName(chatId), { when: safeWhen });
    } else {
      await chrome.alarms.clear(alarmName(chatId));
    }
    return {
      state: stateModel.patchConversation(state, chatId, {
        nextRunAt: new Date(safeWhen).toISOString()
      }).state,
      value: state.settings.masterEnabled
    };
  });
  return result.value;
}

async function scheduleAfterMinutes(chatId, minutes, expectedGeneration = null) {
  const delayMinutes = clampNumber(minutes, 10, MIN_INTERVAL_MINUTES, MAX_INTERVAL_MINUTES);
  return scheduleAt(chatId, Date.now() + delayMinutes * 60_000, expectedGeneration);
}

async function scheduleDefault(chatId, useBusyRetry = false, expectedGeneration = null) {
  const state = await getBridgeState();
  const conversation = state.conversations[chatId];
  if (!conversation || (expectedGeneration !== null && conversation.generation !== expectedGeneration)) return false;
  const runtime = await loadRuntimeConfig(state, conversation);
  return scheduleAfterMinutes(
    chatId,
    useBusyRetry ? runtime.busyRetryMinutes : runtime.intervalMinutes,
    conversation.generation
  );
}

async function reconcileSchedules() {
  await chrome.alarms.clear(LEGACY_ALARM_NAME);
  const state = await getBridgeState();
  const alarms = await chrome.alarms.getAll();
  const validAlarmNames = new Set(Object.keys(state.conversations).map((chatId) => alarmName(chatId)));
  await Promise.all(
    alarms
      .filter((alarm) => alarm.name.startsWith(ALARM_PREFIX) && !validAlarmNames.has(alarm.name))
      .map((alarm) => chrome.alarms.clear(alarm.name))
  );

  if (!state.settings.masterEnabled) {
    await Promise.all(
      Object.keys(state.conversations).map((id) => clearConversationAlarm(id, null, false))
    );
    return;
  }

  for (const conversation of Object.values(state.conversations)) {
    if (!conversation.enabled || !stateModel.isBoundConversation(conversation)) {
      await clearConversationAlarm(conversation.id);
      continue;
    }
    const storedWhen = Date.parse(conversation.nextRunAt || "");
    if (Number.isFinite(storedWhen) && storedWhen > Date.now() + 1000) {
      await scheduleAt(conversation.id, storedWhen, conversation.generation);
    } else {
      await scheduleDefault(conversation.id);
    }
  }
}
