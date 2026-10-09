/* Browser-local legacy effect suspension: a deny latch, NEVER a transport permit.
 * This does not establish a globally authoritative mode fence or retire an
 * older/offline Bridge that has not received this code. New GitHub-first Send
 * stays disabled until independent admission and retirement proof exist.
 */
const LEGACY_DOM_EFFECT_SUSPENSION_KEY = "conversationFabricLegacyDomEffectSuspension";

async function requireLegacyConversationSpawnEffectAllowed() {
  if (!chrome?.storage?.local || typeof chrome.storage.local.get !== "function") {
    throw new Error("Legacy DOM effect admission storage unavailable");
  }
  let stored;
  try {
    stored = await chrome.storage.local.get(LEGACY_DOM_EFFECT_SUSPENSION_KEY);
  } catch (_error) {
    throw new Error("Legacy DOM effect admission storage read failed");
  }
  if (!stored || typeof stored !== "object" || Array.isArray(stored)) {
    throw new Error("Legacy DOM effect admission snapshot malformed");
  }
  // Any present value, including null/false, is a suspension. Only a
  // completely absent key preserves the existing legacy behavior.
  if (Object.hasOwn(stored, LEGACY_DOM_EFFECT_SUSPENSION_KEY)) {
    throw new Error("Legacy DOM browser effects suspended pending global transport admission");
  }
  return true;
}
