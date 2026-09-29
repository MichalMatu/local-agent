const GITHUB_CONTROL_APPLIED_KEY = "bridgeGithubControlApplied";
const GITHUB_CONTROL_APPLIED_LIMIT = 128;

async function readAppliedGithubControls() {
  const stored = await chrome.storage.local.get(GITHUB_CONTROL_APPLIED_KEY);
  const raw = stored[GITHUB_CONTROL_APPLIED_KEY];
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const result = {};
  for (const [chatId, value] of Object.entries(raw)) {
    const generation = Number(value?.generation);
    if (!protocol.CHAT_ID_RE.test(chatId) || !Number.isSafeInteger(generation) || generation < 1) continue;
    result[chatId] = { generation, at: Number(value?.at) || 0 };
  }
  return result;
}

async function writeAppliedGithubControl(chatId, generation) {
  const current = await readAppliedGithubControls();
  current[chatId] = { generation, at: Date.now() };
  const bounded = Object.entries(current)
    .sort((left, right) => Number(right[1]?.at || 0) - Number(left[1]?.at || 0))
    .slice(0, GITHUB_CONTROL_APPLIED_LIMIT);
  await chrome.storage.local.set({ [GITHUB_CONTROL_APPLIED_KEY]: Object.fromEntries(bounded) });
}

async function ensureGithubControlPollAlarm() {
  const alarms = await chrome.alarms.getAll();
  if (alarms.some((alarm) => alarm.name === GITHUB_CONTROL_ALARM_NAME)) return;
  await chrome.alarms.create(GITHUB_CONTROL_ALARM_NAME, { periodInMinutes: GITHUB_CONTROL_POLL_MINUTES });
}

async function reconcileGithubConversationControls() {
  const state = await getBridgeState();
  const runtime = await fetchRuntime(state.settings);
  if (runtime.source !== "remote") {
    return { ok: false, reason: "runtime_unavailable", applied: [] };
  }

  const applied = await readAppliedGithubControls();
  const appliedNow = [];

  for (const conversation of Object.values(state.conversations)) {
    const control = githubControlModel.findConversationControl(runtime, conversation.id);
    if (!control || !githubControlModel.controlMatchesConversation(control, conversation)) continue;
    if (control.controlGeneration <= Number(applied[conversation.id]?.generation || 0)) continue;

    const deadline = githubControlModel.scheduleDeadline(control, runtime.intervalMinutes);
    const mutation = await mutateState((currentState) => {
      const current = currentState.conversations[conversation.id];
      if (!current || !githubControlModel.controlMatchesConversation(control, current)) {
        return { state: currentState, value: { ok: false, reason: "binding_changed" } };
      }
      const localGeneration = current.generation + 1;
      const patched = stateModel.patchConversation(currentState, current.id, {
        enabled: control.enabled,
        intervalOverrideMinutes: control.intervalMinutes,
        generation: localGeneration,
        nextRunAt: null,
        lastControlAction: `github:${control.controlGeneration}`,
        lastControlAt: control.updatedAt,
        lastStatus: control.enabled ? "github_control_enabled" : "github_control_paused",
        lastRuntimeSource: runtime.source
      });
      return {
        state: patched.state,
        value: { ok: true, chatId: current.id, localGeneration }
      };
    });

    if (!mutation.value?.ok) continue;
    const { chatId, localGeneration } = mutation.value;
    if (control.enabled) {
      await scheduleAt(chatId, deadline, localGeneration);
    } else {
      await clearConversationAlarm(chatId, localGeneration);
    }
    await writeAppliedGithubControl(chatId, control.controlGeneration);
    appliedNow.push({ chatId, controlGeneration: control.controlGeneration, enabled: control.enabled });
  }

  return { ok: true, reason: "reconciled", applied: appliedNow };
}

async function initializeGithubControlPlane() {
  await ensureGithubControlPollAlarm();
  return reconcileGithubConversationControls();
}
