const GITHUB_CONTROL_APPLIED_KEY = "bridgeGithubControlApplied";
const GITHUB_CONTROL_APPLIED_LIMIT = 128;
let githubControlQueue = Promise.resolve();

async function readAppliedGithubControls() {
  const stored = await chrome.storage.local.get(GITHUB_CONTROL_APPLIED_KEY);
  const raw = stored[GITHUB_CONTROL_APPLIED_KEY];
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return {};
  const result = {};
  for (const [chatId, value] of Object.entries(raw)) {
    const generation = Number(value?.generation);
    const bindingRevision = Number(value?.bindingRevision);
    const localGeneration = Number(value?.localGeneration);
    if (!protocol.CHAT_ID_RE.test(chatId) || !Number.isSafeInteger(generation) || generation < 1) continue;
    result[chatId] = {
      generation,
      bindingRevision: Number.isSafeInteger(bindingRevision) && bindingRevision >= 1 ? bindingRevision : 0,
      localGeneration: Number.isSafeInteger(localGeneration) && localGeneration >= 0 ? localGeneration : -1,
      at: Number(value?.at) || 0
    };
  }
  return result;
}

async function writeAppliedGithubControl(chatId, generation, bindingRevision, localGeneration) {
  const current = await readAppliedGithubControls();
  current[chatId] = { generation, bindingRevision, localGeneration, at: Date.now() };
  const bounded = Object.entries(current)
    .sort((left, right) => Number(right[1]?.at || 0) - Number(left[1]?.at || 0))
    .slice(0, GITHUB_CONTROL_APPLIED_LIMIT);
  await chrome.storage.local.set({ [GITHUB_CONTROL_APPLIED_KEY]: Object.fromEntries(bounded) });
}

async function clearAppliedGithubControl(chatId) {
  const current = await readAppliedGithubControls();
  if (!Object.hasOwn(current, chatId)) return false;
  delete current[chatId];
  await chrome.storage.local.set({ [GITHUB_CONTROL_APPLIED_KEY]: current });
  return true;
}

async function ensureGithubControlPollAlarm() {
  const alarms = await chrome.alarms.getAll();
  if (alarms.some((alarm) => alarm.name === GITHUB_CONTROL_ALARM_NAME)) return;
  await chrome.alarms.create(GITHUB_CONTROL_ALARM_NAME, { periodInMinutes: GITHUB_CONTROL_POLL_MINUTES });
}

async function githubScheduleAuthority(conversation, state = null) {
  if (!conversation || !stateModel.isBoundConversation(conversation)) return null;
  const basis = state || await getBridgeState();
  const runtime = await fetchRuntime(basis.settings, { fresh: true });
  if (runtime.source === "remote") {
    const control = githubControlModel.findConversationControl(runtime, conversation.id);
    if (control && githubControlModel.controlMatchesConversation(control, conversation)) {
      return {
        managed: true,
        source: "remote",
        controlGeneration: control.controlGeneration,
        bindingRevision: control.bindingRevision
      };
    }
  }

  // Once a matching GitHub desired state has been applied, a transient fetch failure,
  // malformed publication, or temporarily missing record must not silently hand schedule
  // ownership back to DOM/local pacing controls. Rebind creates a new revision and exits
  // this sticky ownership boundary explicitly.
  const applied = await readAppliedGithubControls();
  const cached = applied[conversation.id];
  if (!cached || cached.bindingRevision !== conversation.bindingRevision) return null;
  return {
    managed: true,
    source: "cached",
    controlGeneration: cached.generation,
    bindingRevision: cached.bindingRevision
  };
}

async function githubOwnershipSnapshot(state, runtime = null) {
  const applied = await readAppliedGithubControls();
  const ownership = {};
  for (const conversation of Object.values(state?.conversations || {})) {
    if (!stateModel.isBoundConversation(conversation)) continue;
    const control = runtime?.source === "remote"
      ? githubControlModel.findConversationControl(runtime, conversation.id)
      : null;
    if (control && githubControlModel.controlMatchesConversation(control, conversation)) {
      ownership[conversation.id] = {
        managed: true,
        source: "remote",
        controlGeneration: control.controlGeneration,
        bindingRevision: control.bindingRevision
      };
      continue;
    }
    const cached = applied[conversation.id];
    if (cached?.bindingRevision === conversation.bindingRevision) {
      ownership[conversation.id] = {
        managed: true,
        source: "cached",
        controlGeneration: cached.generation,
        bindingRevision: cached.bindingRevision
      };
    }
  }
  return ownership;
}

function repairedScheduleDeadline(control, runtime, nowMs = Date.now()) {
  if (!control.enabled) return null;
  const explicit = Date.parse(control.nextWakeAt || "");
  if (Number.isFinite(explicit) && explicit > nowMs + 1000) return explicit;
  const interval = control.intervalMinutes === null ? runtime.intervalMinutes : control.intervalMinutes;
  return nowMs + interval * 60_000;
}

async function reconcileGithubConversationControlsOnce() {
  const state = await getBridgeState();
  const runtime = await fetchRuntime(state.settings, { fresh: true });
  if (runtime.source !== "remote") {
    return { ok: false, reason: "runtime_unavailable", configured: 0, applied: [] };
  }

  const configured = runtime.conversationControls.length;
  const applied = await readAppliedGithubControls();
  const appliedNow = [];

  for (const conversation of Object.values(state.conversations)) {
    const control = githubControlModel.findConversationControl(runtime, conversation.id);
    if (!control || !githubControlModel.controlMatchesConversation(control, conversation)) continue;

    const appliedEntry = applied[conversation.id] || null;
    const sameBinding = appliedEntry?.bindingRevision === control.bindingRevision;
    const appliedGeneration = sameBinding ? Number(appliedEntry?.generation || 0) : 0;
    if (control.controlGeneration < appliedGeneration) continue;

    const mutation = await mutateState((currentState) => {
      const current = currentState.conversations[conversation.id];
      if (!current || !githubControlModel.controlMatchesConversation(control, current)) {
        return { state: currentState, value: { ok: false, reason: "binding_changed" } };
      }
      const fresh = control.controlGeneration > appliedGeneration;
      const generationDrift = !fresh && Number(appliedEntry?.localGeneration) !== current.generation;
      const drifted =
        generationDrift ||
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
    await writeAppliedGithubControl(
      chatId,
      control.controlGeneration,
      control.bindingRevision,
      localGeneration
    );
    appliedNow.push({
      chatId,
      controlGeneration: control.controlGeneration,
      enabled: control.enabled,
      repaired: !fresh
    });
  }

  return { ok: true, reason: "reconciled", configured, applied: appliedNow };
}

function reconcileGithubConversationControls() {
  const operation = githubControlQueue.then(() => reconcileGithubConversationControlsOnce());
  githubControlQueue = operation.catch(() => undefined);
  return operation;
}

async function initializeGithubControlPlane() {
  await ensureGithubControlPollAlarm();
  return reconcileGithubConversationControls();
}
