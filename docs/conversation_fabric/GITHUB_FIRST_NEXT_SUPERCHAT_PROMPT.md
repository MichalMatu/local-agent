# Milestone 8 — new-chat continuation prompt (manual operator handoff)

This is the **manual new ChatGPT window** prompt for the current
GitHub-first Conversation Fabric development track. It is **not** an automatic
Superchat successor protocol and is **not** the separate supervised active
Chrome-extension reload acceptance test in NEXT_CHAT_PROMPT.md.

Copy the prompt below into a **new ChatGPT conversation only after the current
chat has finished its checkpoint and the user has explicitly chosen to move**.
Attach the new conversation to Chat Bridge through the currently supported
operator-managed flow. Never reuse a predecessor `[LA_CHAT=...]` identity or
scheduling generation.

## Continuation prompt

Continue development of `MichalMatu/local-agent`, GitHub-first Conversation
Fabric Milestone 8, from the **latest live GitHub state**, not from remembered
conversation text. The user has decided to **postpone automatic
Superchat-to-Superchat succession** until GitHub-first private workflow
transport and genuine cross-device recovery are proven. Continue with the
existing ordinary ChatGPT Superchat / legacy DOM Bridge mode in the meantime.

Read, in order:

1. `AGENTS.md`.
2. `docs/conversation_fabric/GITHUB_FIRST_CURRENT_HANDOFF.md`.
3. `docs/conversation_fabric/TARGET_PRODUCT_ARCHITECTURE.md`.
4. `docs/conversation_fabric/README.md` and `CURRENT_PLAN.md`.
5. Any exact current PR diff, matching tests and known durable result record.

Resolve `main`, the exact open PR heads, the private `fabric-data` ref and
the current `agent-control` daemon evidence **afresh**. All old handoff SHA
values are observations only. Specifically inspect the parent mode/exclusion
draft PR #209 and stacked synthetic-only private CAS draft PR #214. Existing
independent reasoning-child reviews
`m8-parent-fence-verification` and `m8-parent-fence-integration` were
delegated previously but their complete final replies have not been
verified in the current GitHub PR review record. **Do not duplicate pending
delegations, invent their results, or merge the drafts merely because CI is
green.**

Before continuing code work, also inspect any newer PRs that repair legacy
Conversation Fabric terminal delivery uncertainty. They must preserve
at-most-once no-replay behavior: a lost feedback ACK is **unconfirmed**, not
proof of successful delivery, and uncertain receipts must remain inspectable
during campaign-history cleanup. Resolve conflicts safely on the latest `main`. **The operator has disabled
GitHub Actions automatic execution due to exhausted credits:** do not wait
for hosted six-check CI or manually dispatch a workflow. Instead run the
exact-head Mac/sandbox checks in `LOCAL_VERIFICATION.md` and retain durable
command/exit-code evidence, marking unsupported gates unverified. Independent
security/integration review requirements remain in force.

For each executable Local Agent task, resolve the actual target repository
from `chat_bridge/runtime.json` on `chat-bridge-state`; verify
`execution_enabled`, exact `agent_binding`, matching
`.agent/binding.json` and live daemon record on `agent-control`, and the
exact work-branch source SHA. Do not direct tasks to disabled repositories.
Prefer GitHub PR changes when exact diffs and local test evidence can verify
them; use the canonical bound Local Agent for Mac commands and authorized
browser or device testing. Do not reactivate GitHub Actions.

Production limits remain strict:

- Keep GitHub-first private browser Send and real ACK disabled. The
  synthetic parent fence, CAS and read-only private snapshot are not
  browser execution permissions.
- Do not change global Bridge Master, accidentally alter conversation
  scheduling, expose private credentials, publish private child prompts,
  or write to the private `fabric-data` repository without exact approved
  authority.
- Never automatically retry ambiguous child bootstrap, machine command,
  parent feedback delivery, or unknown-effects browser operation.
- Do not automatically promote reasoning children to Superchats or close
  an operator chat. A future parent successor needs a separately designed,
  durable, confirmed authority-transfer protocol.
- The controlled Chrome-extension reload during live child work remains an
  operator-guided acceptance test, **not** a safe unsupervised background test.

Continue with useful bounded code, tests and documentation tasks. Update the
canonical handoff in the repository with verified source SHAs, statuses,
blocking reviews and next test gates before requesting another manual
ChatGPT window handoff. Distinguish real GitHub reads, synthetic fixture
proof, legacy browser live proof and unfinished production GitHub-first
execution.

## Acceptance boundary

This manual prompt transfers **reasoning instructions**, not browser
authority or control ownership. A new chat must explicitly bind to its own
managed Chat Bridge conversation and re-read durable GitHub evidence before
any authorized operation. The old chat must not be assumed closed, stopped,
retired or superseded by merely opening a new window.
