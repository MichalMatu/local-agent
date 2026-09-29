# Local Agent 4.19.8

## Summary

Harden Chat Bridge against the current ChatGPT renderer and assistant-stream failure modes observed on the canonical Chrome-for-Testing conversation. The candidate keeps normal content protocol v13, advances Chat Bridge to 0.5.18 and advances the independent assistant guard protocol to v8.

## Problems fixed

1. **Assistant-only grouped turns** — a logical `data-turn-key` may contain an assistant response and action controls without either a user bubble or an explicit assistant-role marker, so assistant LAB controls could be skipped.
2. **`Resume stream unavailable`** — ChatGPT can terminate an already-accepted Bridge wake with a Retry card whose text differs from the previously supported `Message delivery timed out. Please try again.` shape. The old guard ignored it.
3. **Operator recovery interruption** — the bounded external content-script recovery and managed CfT stop helpers previously had no preflight preventing a reload/stop while ChatGPT still exposed an active generation Stop control.

## Fix

- Admit assistant-only grouped turns when bounded sanitization leaves non-empty assistant text or a structured assistant error, while stripping recognized user bubbles and grouped action controls and preserving fail-closed user-only handling.
- Recognize `Resume stream unavailable` as a second typed recoverable assistant error. It reuses ChatGPT's native Retry control, the exact preferred-tab requirement, immutable Bridge ownership check, binding/generation revalidation and the existing durable three-attempt retry budget. Unknown Retry-looking errors remain rejected.
- Advance the assistant guard protocol from v7 to v8 so reachable already-open tabs replace the guard-captured `dom_contract.js` / `exhaustion_guard.js` contract. Content protocol remains v13 because ordinary wake submission/control semantics are unchanged.
- Advance Chat Bridge from 0.5.17 to 0.5.18.
- Before external `recover-content-script`, count the exact target's `stop-button` / `composer-stop-button` controls and refuse recovery while generation is active.
- Before managed Chat Bridge browser `stop`, inspect only the owned profile's loopback endpoint and refuse to stop if any approved ChatGPT page target exposes a generation Stop control. Both helpers keep an explicit `--force` emergency override rather than interrupting by default.

## Evidence

- Live CfT evidence captured the assistant-only renderer and the `Resume stream unavailable` Retry card on the canonical diagnostic conversation.
- Focused Bridge verification passed for the new DOM/worker recovery contract.
- Recovery-helper tests passed 11/11 and managed-session helper tests passed 13/13 with active-stream fail-closed and explicit-force cases.
- PR #112 completed all five GitHub Actions gates successfully, including real-extension `bridge-browser` and macOS smoke.
