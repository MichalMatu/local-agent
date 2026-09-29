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

function repairedScheduleDeadline(control, runtime, nowMs = Date.now()) {
  if (!control.enabled) return null;
  const explicit = Date.parse(control.nextWakeAt || "");
  if (Number.isFinite(explicit) && explicit > nowMs + 1000) return explicit;
  const interval = control.intervalMinutes === null ? runtime.intervalMinutes : control.intervalMinutes;
  return nowMs + interval * 60_000;
}

async function reconcileGithubConversationControls() {
  await ensureGithubControlPollAlarm();
  const state = await getBridgeState();
  const runtime = await fetchRuntime(state.settings);
  if (runtime.source !== "remote") {
    return { ok: false, reason: "runtime_unavailable", configured: 0, applied: [] };
  }

  const configured = runtime.conversationControls.length;
  const applied = await readAppliedGithubControls();
  const appliedNow = [];

  for (const conversation of Object.values(state.conversations)) {
    const control = githubControlModel.findConversationControl(runtime, conversation.id);
    if (!control || !githubControlModel.controlMatchesConversation(control, conversation)) continue;

    const appliedGeneration = Number(applied[conversation.id]?.generation || 0);
    if (control.controlGeneration < appliedGeneration) continue;

    const mutation = await mutateState((currentState) => {
      const current = currentState.conversations[conversation.id];
      if (!current || !githubControlModel.controlMatchesConversation(control, current)) {
        return { state: currentState, value: { ok: false, reason: "binding_changed" } };
      }
      const fresh = control.controlGeneration > appliedGeneration;
      const drifted =
        current.enabled !== control.enabled ||
        current.intervalOverrideMinutes !== control.intervalMinutes;
      if (!fresh && !drifted) {
        return { state: currentState, value: { ok: true, changed: false } };
      }

      const localGeneration = current.generation + 1;
      const patched = stateModel.patchConversation(currentState, current.id, {
        enabled: control.enabled,
        intervalOverrideMinutes: control.intervalMinutes,
        generation: localGeneration,
        nextRunAt: null,
        lastControlAction: `github:${control.controlGeneration}`,
        lastControlAt: control.updatedAt,
        lastStatus: fresh
          ? (control.enabled ? "github_control_enabled" : "github_control_paused")
          : "github_control_reconciled",
        lastRuntimeSource: runtime.source
      });
      return {
        state: patched.state,
        value: { ok: true, changed: true, chatId: current.id, localGeneration, fresh }
      };
    });

    if (!mutation.value?.ok || !mutation.value.changed) continue;
    const { chatId, localGeneration, fresh } = mutation.value;
    if (control.enabled) {
      const deadline = fresh
        ? githubControlModel.scheduleDeadline(control, runtime.intervalMinutes)
        : repairedScheduleDeadline(control, runtime);
      await scheduleAt(chatId, deadline, localGeneration);
    } else {
      await clearConversationAlarm(chatId, localGeneration);
    }
    if (fresh) await writeAppliedGithubControl(chatId, control.controlGeneration);
    appliedNow.push({
      chatId,
      controlGeneration: control.controlGeneration,
      enabled: control.enabled,
      repaired: !fresh
    });
  }

  return { ok: true, reason: "reconciled", configured, applied: appliedNow };
}

async function initializeGithubControlPlane() {
  return reconcileGithubConversationControls();
}
