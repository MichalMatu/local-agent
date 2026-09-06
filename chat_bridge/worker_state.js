let stateQueue = Promise.resolve();

async function loadStoredState() {
  const raw = await chrome.storage.local.get(null);
  const migrated = stateModel.migrateLegacyStorage(raw);
  if (migrated.migrated) {
    await chrome.storage.local.set({ bridgeState: migrated.state });
  }
  return migrated.state;
}

async function getBridgeState() {
  await stateQueue;
  return loadStoredState();
}

function mutateState(mutator) {
  const operation = stateQueue.then(async () => {
    const current = await loadStoredState();
    const result = await mutator(stateModel.normalizeState(current));
    const nextState = stateModel.normalizeState(result?.state || result || current);
    await chrome.storage.local.set({ bridgeState: nextState });
    return {
      state: nextState,
      value: result?.value,
      conversation: result?.conversation
    };
  });
  stateQueue = operation.catch(() => undefined);
  return operation;
}
