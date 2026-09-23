# Superchat research log

This file records evidence, open questions and implementation-relevant observations. Keep observed facts separate from hypotheses.

## 2026-09-06 — Observed hard conversation exhaustion

Source: saved live ChatGPT page / captured DOM from a real conversation that reached its maximum length.

Observed stable signals:

```text
[data-message-author-role="assistant"]
  -> descendant .text-token-text-error
  -> normalized text contains:
     "You've reached the maximum length for this conversation"
  -> descendant button with normalized visible text exactly:
     "Start new chat"
```

The assistant message also exposes `data-message-id`.

Do not depend on:

- Tailwind utility class combinations;
- generated CSS hashes;
- SVG sprite ids;
- exact element depth;
- the complete error sentence remaining byte-for-byte identical.

Canonical contract: `docs/CHATGPT_DOM_CONTRACT.md`.

Implementation already present:

- `chat_bridge/dom_contract.js` encapsulates the structural/textual detector;
- `chat_bridge/exhaustion_guard.js` observes DOM mutations, periodically rescans, deduplicates and reports exhaustion;
- `chat_bridge/worker_transport.js` validates the sender conversation and marks it `conversation_exhausted`, disables it and clears its alarm.

## 2026-09-06 — Saved exhausted page

A full saved page/archive was captured by the operator after the conversation reached the hard limit.

Planned use:

- do not commit the complete raw page blindly;
- inspect it locally;
- remove account/conversation-specific/private data and unrelated application markup;
- extract the smallest DOM fragment that reproduces the exhaustion detector contract;
- commit that sanitized fragment as a regression fixture;
- add negative fixtures that intentionally omit or alter one required signal.

Open item: the raw archive still needs to be inspected and sanitized before committing any fixture derived from it.

## 2026-09-06 — Current bridge state model

Observed from `chat_bridge/bridge_state.js`:

- schema version is 3;
- top-level persistent state contains settings and `conversations`;
- conversation records already contain immutable repository/binding identity, scheduling generation, assistant baseline and delivery/control status;
- there is no durable goal, supervisor or operation-journal domain.

Conclusion:

Superchat should introduce separate `supervisor`, `goals` and `operations` state domains rather than turning conversation records into goal records.

## 2026-09-06 — Current conversation registration contract

Observed from `chat_bridge/worker_conversations.js`:

- `upsertConversation()` rejects a non-concrete ChatGPT URL with `Open a concrete ChatGPT conversation first.`;
- an existing conversation's catalog binding is preserved;
- binding changes use the explicit operator `rebindConversation()` path;
- ordinary conversation updates cannot mutate binding.

Conclusion:

Automatic replacement creation must use a new internal creation/registration transaction. Do not weaken the existing concrete-URL registration contract.

## 2026-09-06 — Current normal delivery contract

Observed from `chat_bridge/content.js` and `worker_delivery.js`:

- normal delivery is authorized only for an already-known concrete conversation URL;
- content delivery checks exact normalized current URL before writing to the composer;
- service worker validates generation and binding revision before authorization;
- uncertain delivery is deliberately not treated as proven success.

Conclusion:

A dedicated new-chat bootstrap path is safer than allowing normal feedback delivery to target `https://chatgpt.com/`.

## 2026-09-06 — Critical hard-exhaustion handoff constraint

A terminal maximum-length conversation cannot be relied on to answer one final handoff request.

Conclusion:

The minimum viable Superchat design requires durable checkpoints before hard exhaustion. Terminal rollover must be able to reconstruct work from:

1. the last durable structured goal checkpoint;
2. immutable repository and binding metadata;
3. exact current repository/Local Agent evidence re-verified by the replacement planner.

A final LLM summary is useful during proactive rotation but cannot be a correctness requirement.

## 2026-09-06 — Proposed architecture decision

Preferred separation:

```text
Superchat LLM
    -> deterministic Chat Supervisor
        -> Chat Bridge
            -> child planner chats
                -> deterministic Local Agent
```

Rationale:

- LLM chooses intent and next supervisory action;
- deterministic layer owns lifecycle, state transitions, retries, idempotency and recovery;
- child planners remain hard-bound to repositories;
- Local Agent remains the only deterministic executor of queued local tasks.

## Open research questions

### New-chat page contract

Need live evidence for:

- stable allowed URL shapes before a conversation id exists;
- composer selectors on a clean new-chat page;
- whether clicking `Start new chat` always lands on the same surface as opening `https://chatgpt.com/` directly;
- exact point when `/c/<id>` appears after first submission;
- whether history/navigation can change the URL before the first user message is visibly committed;
- whether a newly created conversation can be reliably associated with the tab after service-worker restart.

### Submission reconciliation

Need a deterministic strategy for this ambiguous case:

```text
bootstrap submit attempted
service worker dies / response lost
unknown whether first message was accepted
```

Research possible evidence:

- current tab URL became concrete `/c/<id>`;
- matching first user message exists in the DOM;
- composer became empty;
- known operation marker embedded in bootstrap text;
- browser history/tab identity.

Do not solve this by blindly submitting again.

### Checkpoint publication protocol

Need to choose between:

1. structured `[LAB:*]` checkpoint marker in assistant output;
2. dedicated content-side extraction of a structured fenced block;
3. bridge-owned request/response message for checkpoint publication;
4. durable repository-side checkpoint artifact.

Selection criteria:

- bounded size;
- parser simplicity;
- replay/stale-generation protection;
- ease of testing;
- no need for arbitrary repository writes from the supervisor layer.

### Superchat control syntax

Need to choose a strict `[LAS:*]` representation.

Options to test:

- key/value marker;
- one-line bounded JSON object;
- action marker plus separately bounded fields.

Requirements are more important than syntax: deterministic parser, bounded lengths, no inferred binding and replay protection.

### Supervisor identity

Need to decide whether the Superchat conversation is represented as:

- a dedicated supervisor record outside normal conversations;
- a normal conversation with a special role and `local-agent` non-executing catalog binding;
- a hybrid: normal concrete conversation identity plus separate privileged supervisor authorization record.

Preferred current direction: hybrid authorization, so normal conversation URL/baseline sender checks can be reused while privileged cross-chat actions remain separately gated.

### Checkpoint cadence

Need production evidence before setting predictive rotation thresholds.

Initial correctness should not depend on exact token estimation. Candidate checkpoint triggers:

- after a verified task result;
- after a commit is accepted as current evidence;
- after a material plan change/blocker;
- every bounded number of successful wakes;
- before explicit/proactive rotation.

### Fleet snapshot limits

Need to define bounds for:

- maximum active goals;
- historical chats retained per goal;
- checkpoint text/arrays;
- operation history retention;
- supervisor snapshot size.

The snapshot should contain current state/evidence pointers, not entire child transcripts.

## Research completion rule

When an open question is resolved by live evidence, tests or a production incident:

1. record the evidence/date here;
2. update the canonical contract/design document;
3. add or update regression coverage;
4. remove any implementation fallback that relied on an unverified assumption when practical.
