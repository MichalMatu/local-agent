const GITHUB_CONTROL_APPLIED_KEY = "bridgeGithubControlApplied";
const GITHUB_CONTROL_APPLIED_LIMIT = 128;
let githubControlQueue = Promise.resolve();

function serializeGithubControlOperation(operation) {
  const pending = githubControlQueue.then(operation);
  githubControlQueue = pending.catch(() => undefined);
  return pending;
}

function githubControlSignature(control) {
  return JSON.stringify([
    control.conversationId,
    control.controlGeneration,
    control.enabled,
    control.intervalMinutes,
    control.nextWakeAt,
    control.updatedAt
  ]);
}

function githubControlPreservedLocalSafety(conversation, fresh) {
  if (!conversation || conversation.enabled) return null;
  if (conversation.lastStatus === "conversation_exhausted") return "conversation_exhausted";
  if (!fresh && conversation.lastStatus === "assistant_retry_exhausted") {
    return "assistant_retry_exhausted";
  }
  return null;
}

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
      bindingRevision: Number.isSafeInteger(bindingRevision) && bindingRevision >= 0 ? bindingRevision : 0,
      localGeneration: Number.isSafeInteger(localGeneration) && localGeneration >= 0 ? localGeneration : -1,
      controlSignature: typeof value?.controlSignature === "string" ? value.controlSignature : "",
      at: Number(value?.at) || 0
    };
  }
  return result;
}

async function writeAppliedGithubControl(chatId, generation, bindingRevision, localGeneration, controlSignature = "") {
  const current = await readAppliedGithubControls();
  current[chatId] = {
    generation,
    bindingRevision: Math.max(0, Number(bindingRevision) || 0),
    localGeneration,
    controlSignature: String(controlSignature || ""),
    at: Date.now()
  };
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
  if (!conversation) return null;
  const basis = state || await getBridgeState();
  const [runtime, applied] = await Promise.all([
    fetchRuntime(basis.settings, { fresh: true }),
    readAppliedGithubControls()
  ]);
  const cached = applied[conversation.id] || null;

  if (runtime.source === "remote") {
    const control = githubControlModel.findConversationControl(runtime, conversation.id);
    if (control && githubControlModel.controlMatchesConversation(control, conversation)) {
      const signature = githubControlSignature(control);
      const remoteIsStale = cached && control.controlGeneration < cached.generation;
      const sameGenerationConflict =
        cached &&
        control.controlGeneration === cached.generation &&
        cached.controlSignature &&
        cached.controlSignature !== signature;
      if (!remoteIsStale && !sameGenerationConflict) {
        return {
          managed: true,
          source: "remote",
          controlGeneration: control.controlGeneration,
          bindingRevision: Number(conversation.bindingRevision) || 0
        };
      }
    }
  }

  // Once GitHub desired state has been applied to a chat, transient runtime failure,
  // stale rollback, or a same-generation rewrite must not silently hand scheduling
  // authority back to local/DOM pacing. Ownership is keyed by chat identity only;
  // repository binding metadata is deliberately not part of this boundary.
  if (!cached) return null;
  return {
    managed: true,
    source: "cached",
    controlGeneration: cached.generation,
    bindingRevision: Number(conversation.bindingRevision) || 0
  };
}

async function githubOwnershipSnapshot(state, runtime = null) {
  const applied = await readAppliedGithubControls();
  const ownership = {};
  for (const conversation of Object.values(state?.conversations || {})) {
    const cached = applied[conversation.id] || null;
    const control = runtime?.source === "remote"
      ? githubControlModel.findConversationControl(runtime, conversation.id)
      : null;
    if (control && githubControlModel.controlMatchesConversation(control, conversation)) {
      const signature = githubControlSignature(control);
      const remoteIsStale = cached && control.controlGeneration < cached.generation;
      const sameGenerationConflict =
        cached &&
        control.controlGeneration === cached.generation &&
        cached.controlSignature &&
        cached.controlSignature !== signature;
      if (!remoteIsStale && !sameGenerationConflict) {
        ownership[conversation.id] = {
          managed: true,
          source: "remote",
          controlGeneration: control.controlGeneration,
          bindingRevision: Number(conversation.bindingRevision) || 0
        };
        continue;
      }
    }
    if (cached) {
      ownership[conversation.id] = {
        managed: true,
        source: "cached",
        controlGeneration: cached.generation,
        bindingRevision: Number(conversation.bindingRevision) || 0
      };
    }
  }
  return ownership;
}

async function recoverGithubControlledConversations(state, runtime, applied) {
  const missing = (runtime.conversationControls || []).filter(
    (control) => !state.conversations?.[control.conversationId]
  );
  if (!missing.length) return { recovered: [], conflicts: [] };

  const wanted = new Set(missing.map((control) => control.conversationId));
  const tabs = await chrome.tabs.query({
    url: ["https://chatgpt.com/*", "https://chat.openai.com/*"]
  });
  const candidates = new Map();
  for (const tab of tabs) {
    if (!Number.isInteger(tab?.id)) continue;
    const url = normalizeConversationUrl(tab.url || "");
    if (!url) continue;
    const chatId = conversationId(url);
    if (!wanted.has(chatId)) continue;
    const matches = candidates.get(chatId) || [];
    matches.push({
      tabId: tab.id,
      url,
      label: String(tab.title || "GitHub-managed conversation")
    });
    candidates.set(chatId, matches);
  }

  const recovered = [];
  const conflicts = [];
  for (const control of missing) {
    const appliedEntry = applied[control.conversationId] || null;
    const appliedGeneration = Number(appliedEntry?.generation || 0);
    const controlSignature = githubControlSignature(control);
    if (control.controlGeneration < appliedGeneration) {
      conflicts.push({
        chatId: control.conversationId,
        controlGeneration: control.controlGeneration,
        reason: "stale_generation"
      });
      continue;
    }
    if (
      control.controlGeneration === appliedGeneration &&
      appliedEntry?.controlSignature &&
      appliedEntry.controlSignature !== controlSignature
    ) {
      conflicts.push({
        chatId: control.conversationId,
        controlGeneration: control.controlGeneration,
        reason: "same_generation_rewritten"
      });
      continue;
    }
    const matches = candidates.get(control.conversationId) || [];
    if (matches.length > 1) {
      conflicts.push({
        chatId: control.conversationId,
        controlGeneration: control.controlGeneration,
        reason: "conversation_recovery_ambiguous"
      });
      continue;
    }
    if (matches.length !== 1) continue;

    const candidate = matches[0];
    const mutation = await mutateState((currentState) => {
      if (currentState.conversations?.[control.conversationId]) {
        return { state: currentState, value: { recovered: false } };
      }
      const upserted = stateModel.upsertConversation(currentState, {
        url: candidate.url,
        label: candidate.label,
        enabled: control.enabled,
        preferredTabId: candidate.tabId,
        intervalOverrideMinutes: control.intervalMinutes,
        bootstrapPending: false,
        lastStatus: "github_control_recovered",
        lastRuntimeSource: runtime.source
      });
      const sameIdentity = upserted.conversation.id === control.conversationId;
      return {
        state: sameIdentity ? upserted.state : currentState,
        value: {
          recovered: sameIdentity,
          chatId: upserted.conversation.id,
          tabId: candidate.tabId
        }
      };
    });
    if (mutation.value?.recovered) {
      recovered.push({
        chatId: mutation.value.chatId,
        tabId: mutation.value.tabId,
        controlGeneration: control.controlGeneration
      });
    }
  }
  return { recovered, conflicts };
}

async function reconcileGithubConversationControlsOnce() {
  let state = await getBridgeState();
  const runtime = await fetchRuntime(state.settings, { fresh: true });
  if (runtime.source !== "remote") {
    return { ok: false, reason: "runtime_unavailable", configured: 0, applied: [], conflicts: [] };
  }

  const configured = runtime.conversationControls.length;
  const applied = await readAppliedGithubControls();
  const recovery = await recoverGithubControlledConversations(state, runtime, applied);
  if (recovery.recovered.length) state = await getBridgeState();

  const appliedNow = [];
  const conflicts = [...recovery.conflicts];

  for (const conversation of Object.values(state.conversations)) {
    const control = githubControlModel.findConversationControl(runtime, conversation.id);
    if (!control || !githubControlModel.controlMatchesConversation(control, conversation)) continue;

    const appliedEntry = applied[conversation.id] || null;
    const appliedGeneration = Number(appliedEntry?.generation || 0);
    if (control.controlGeneration < appliedGeneration) continue;

    const controlSignature = githubControlSignature(control);
    if (
      control.controlGeneration === appliedGeneration &&
      appliedEntry?.controlSignature &&
      appliedEntry.controlSignature !== controlSignature
    ) {
      conflicts.push({
        chatId: conversation.id,
        controlGeneration: control.controlGeneration,
        reason: "same_generation_rewritten"
      });
      continue;
    }

    const desiredDeadline = control.enabled
      ? githubControlModel.scheduleDeadline(control, runtime.intervalMinutes)
      : null;

    const mutation = await mutateState((currentState) => {
      const current = currentState.conversations[conversation.id];
      if (!current) {
        return { state: currentState, value: { ok: false, reason: "conversation_removed" } };
      }
      const fresh = control.controlGeneration > appliedGeneration;
      const preservedLocalSafety = githubControlPreservedLocalSafety(current, fresh);
      if (preservedLocalSafety) {
        return {
          state: currentState,
          value: {
            ok: true,
            changed: false,
            localGeneration: current.generation,
            preservedLocalSafety
          }
        };
      }
      const generationDrift = !fresh && Number(appliedEntry?.localGeneration) !== current.generation;
      const drifted =
        generationDrift ||
        current.enabled !== control.enabled ||
        current.intervalOverrideMinutes !== control.intervalMinutes;
      if (!fresh && !drifted) {
        return { state: currentState, value: { ok: true, changed: false, localGeneration: current.generation } };
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

    if (!mutation.value?.ok) continue;
    const bindingRevision = Number(conversation.bindingRevision) || 0;
    if (!mutation.value.changed) {
      if (mutation.value.preservedLocalSafety) {
        await clearConversationAlarm(conversation.id, mutation.value.localGeneration);
      } else if (control.enabled && state.settings.masterEnabled &&
                 appliedEntry?.controlSignature === controlSignature) {
        // An unchanged GitHub generation normally leaves its alarm alone. If
        // Chrome loses that alarm, restore only a still-future local deadline:
        // replaying an expired one-shot wake would risk a duplicate Send.
        const latest = (await getBridgeState()).conversations[conversation.id];
        const storedDeadline = Date.parse(latest?.nextRunAt || "");
        if (latest?.enabled &&
            latest.generation === mutation.value.localGeneration &&
            stateModel.isTransportReady(latest) &&
            Number.isFinite(storedDeadline) && storedDeadline > Date.now() + 1000) {
          const alarms = await chrome.alarms.getAll();
          if (!alarms.some((alarm) => alarm.name === alarmName(conversation.id))) {
            await scheduleAt(conversation.id, storedDeadline, latest.generation);
          }
        }
      }
      if (mutation.value.preservedLocalSafety || !appliedEntry?.controlSignature) {
        await writeAppliedGithubControl(
          conversation.id,
          control.controlGeneration,
          bindingRevision,
          mutation.value.localGeneration,
          controlSignature
        );
      }
      continue;
    }

    const { chatId, localGeneration, fresh } = mutation.value;
    if (control.enabled) {
      await scheduleAt(chatId, desiredDeadline, localGeneration);
    } else {
      await clearConversationAlarm(chatId, localGeneration);
    }
    await writeAppliedGithubControl(
      chatId,
      control.controlGeneration,
      bindingRevision,
      localGeneration,
      controlSignature
    );
    appliedNow.push({
      chatId,
      controlGeneration: control.controlGeneration,
      enabled: control.enabled,
      repaired: !fresh
    });
  }

  return {
    ok: true,
    reason: "reconciled",
    configured,
    recovered: recovery.recovered,
    applied: appliedNow,
    conflicts
  };
}

function reconcileGithubConversationControls() {
  return serializeGithubControlOperation(() => reconcileGithubConversationControlsOnce());
}

async function initializeGithubControlPlane() {
  await ensureGithubControlPollAlarm();
  return reconcileGithubConversationControls();
}
