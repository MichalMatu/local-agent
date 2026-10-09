# Private global parent fence: default-disabled reader

Status: **read-only synthetic preview**, not a browser Send/ACK authority.

The unimported chat_bridge/github_fabric_private_parent_fence_reader.js
module reads the future global parents/ namespace from the private
MichalMatu/local-agent-fabric-private repository and fixed fabric-data branch.
It does not depend on the project/workflow folder. Its global parent
identifier follows github_fabric_parent_fence_preview.py:

- The prefix parent- plus the first 32 hex characters of SHA-256 over the
  canonical compact JSON array ["fabric-global-parent-mode-v1", parent_url].
- The exact immutable parent record has fence_epoch=1,
  phase=unattested_no_browser_authority, browser_send_authorized=false
  and ack_state=not_attested.
- The two recognized preview labels are legacy_dom and github_first.
  An existing opposite-mode record is a hard conflict, not a takeover.
- The record is immutable preview evidence, **not proof that an old/offline
  legacy extension has stopped sending**.

## Reader contract

1. The caller explicitly passes enabled=true, a separately provisioned
   *read-only* token, one canonical parent URL and one expected mode.
   No runtime flag, credential storage, token forwarding or active browser
   integration is supplied.
2. The reader resolves the fixed branch once. It then reads the Git commit,
   recursive tree, global index and every indexed record at the **same
   immutable head SHA**. Contents blob SHA must match the tree entry.
3. The tree cannot be truncated. Only recognized parents/index.json and
   parents/parent-*.json files are accepted, with 100644 blob modes.
   Missing indexes, orphan paths, dangling paths and mismatched records fail
   closed. An empty index or absent namespace returns unregistered.
4. All responses are byte-bounded; network requests are GET-only to the
   fixed private repository, with redirects forbidden, cookies omitted and
   credentials never included in a URL or error message.
5. Success returns unattested_preview or unregistered with
   browser_effects_permitted=false. **No response can authorize browser
   tab creation, composer population, Send, ACK, child execution or mode
   handoff.** No token is saved or sent to a content script.

The command below uses injected fake GitHub responses, including opposite
transport races, forged Send/ACK, truncation, path/identity tampering,
inaccessible sources and transport errors.

    node chat_bridge/github_fabric_private_parent_fence_reader.test.js

Normal repository Bridge verification discovers the test.

The module is intentionally **not imported** in service_worker.js, manifest.json
or content scripts. Shipping it as executable production code would create a
false sense of authority until the old DOM path also enforces an authoritative
shared epoch *before* tabs/composer/Send. Source-pinned preview observations
are insufficient: that cross-driver admission design, genuine browser ACK,
fenced retirement and stopped/offline old-extension migration gates remain
required. Do not enable real GitHub-first private child dispatch from this
module.

An additional CI admission regression, `chat_bridge/github_fabric_private_activation_guard.test.js`, fails if the private reader is accidentally imported into production service worker or ChatGPT content scripts, or if the public GitHub-first intake begins creating tabs or submitting prompts. Deliberate future production migration must update this contract only with an independently reviewed browser authority design and acceptance evidence.
