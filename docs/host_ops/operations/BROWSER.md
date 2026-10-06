# Browser operations

`python -m local_agent.host_ops browser` exposes eleven deliberately separate boundaries:

- `browser inspect` reads local browser/process and loopback Chromium DevTools metadata without opening a DevTools WebSocket;
- `browser attach inspect` explicitly attaches read-only to one loopback Chromium CDP endpoint and returns sanitized browser/target inventory;
- `browser attach snapshot` reads bounded current-page metadata for one exact page target without page mutation or content extraction;
- `browser attach selectors` counts matches for bounded caller-supplied CSS selectors on one exact page target without returning matched nodes or page content;
- `browser attach readiness` correlates exact-target DOM selector presence with exact extension content-script fingerprints and current worker-target presence without page/extension mutation;
- `browser attach recover-content-script` may perform exactly one guarded reload only after a missing/stale content-script diagnosis, then requires a readiness re-check;
- `browser attach workers` reads bounded worker/service-worker lifecycle state for one explicit endpoint without worker or page mutation;
- `browser attach reload` performs exactly one guarded reload of one exact HTTP(S) page target after a sanitized expected-URL check;
- `browser session start|status|stop` controls one persistent Chromium process bound to an isolated host-ops-owned profile and loopback-only dynamic CDP endpoint;
- `browser interactive-start|interactive-status|interactive-stop` controls a no-CDP browser process for that same owned profile so the user can perform short manual steps without granting automated page actions;
- `browser probe` launches a disposable managed browser context, performs exactly one bounded HTTP(S) navigation and returns sanitized metadata.

`browser attach reload` is the underlying live-page mutation primitive, and `browser attach recover-content-script` may invoke it at most once after a qualifying diagnosis. No browser command exposes general page automation authority.

## Read-only browser inspection

Inspect local browser processes and any loopback DevTools endpoints discoverable from Chromium command-line flags:

```bash
python -m local_agent.host_ops browser inspect --json
```

Probe an explicit local DevTools endpoint as well:

```bash
python -m local_agent.host_ops browser inspect \
  --endpoint http://127.0.0.1:9222 \
  --timeout 3 \
  --json
```

`--endpoint` is repeatable.

Inspection JSON contains:

- `processes`: recognized browser root processes with PID, family and remote-debugging metadata;
- `endpoints`: bounded `/json/version` and `/json/list` evidence for each unique probed endpoint;
- `warnings`: non-fatal conditions such as a non-loopback debug address, dynamic port or pipe-only debugging.

An unreachable DevTools endpoint is structured evidence, not a whole-command failure. Process-listing failure, truncated process evidence or invalid explicit endpoint input fail the command.

Explicit DevTools endpoints must use `http` or `https`, include an explicit port and resolve syntactically to `localhost`, `127.0.0.1` or `::1`. Credentials, paths, queries and fragments are rejected. Discovered non-loopback debugging addresses are reported but never probed. The HTTP probe rejects redirects and bounds each retained response to 1 MiB.

`browser inspect` does not launch, terminate, navigate or attach through a DevTools WebSocket.

## Explicit Chromium CDP attach

Attach to one already-authorized loopback Chromium DevTools endpoint and inventory targets:

```bash
python -m local_agent.host_ops browser attach inspect \
  --endpoint http://127.0.0.1:9222 \
  --timeout 10 \
  --json
```

The endpoint follows the same strict loopback/base-URL validation as `browser inspect`: explicit `http`/`https`, explicit port, no credentials, path, query or fragment. The attach path is Chromium-only and requires the optional `host-ops[browser]` Playwright extra, but it does not require a Playwright-managed browser binary because it connects to an existing Chromium endpoint.

The inspect helper uses `connect_over_cdp(..., is_local=True, no_defaults=True)`, opens one browser-level CDP session, sends only `Target.getTargets`, sanitizes returned target URLs, detaches the CDP session and disconnects Playwright. It does not create contexts or pages, navigate/reload, attach a page-level CDP session, execute JavaScript, inspect DOM/content, read cookies/storage, capture screenshots or mutate extensions.

Attach-inspect JSON contains only the normalized endpoint, bounded browser version, context count and up to 512 target records with bounded id/type/title, sanitized URL and current `attached` flag. HTTP(S) target evidence drops userinfo, query and fragment; non-HTTP(S) target URLs are reduced to scheme-only evidence.

The whole attach operation runs in a bounded helper under `ProcessRunner`. Helper stdout/stderr are bounded, structured output is revalidated by the parent, and vendor errors are sanitized before becoming public evidence.

### Target-specific read-only page snapshot

After `browser attach inspect` returns an exact page target id, inspect only bounded current-page metadata:

```bash
python -m local_agent.host_ops browser attach snapshot \
  --endpoint http://127.0.0.1:9222 \
  --target-id PAGE_TARGET_ID \
  --timeout 10 \
  --json
```

The snapshot helper connects with the same `is_local=True` / `no_defaults=True` CDP boundary, maps the exact target id to a Playwright page, and opens a temporary page-level CDP session. It sends only `Target.getTargetInfo`, `Page.getFrameTree` and `DOM.getDocument` with `depth=0` and `pierce=false`. It does not call `Page.getNavigationHistory` or `Runtime.evaluate`.

Returned evidence is limited to the exact target identity/type, bounded title, sanitized target/main-frame URLs, bounded frame count, main-frame MIME type, and document-root name/child count. It does not return HTML, text, DOM children, attributes, navigation history, cookies/storage or page resources. URL query strings, fragments and credentials are removed before evidence leaves the helper.

Every unmatched temporary page CDP session is detached immediately; the matched session is detached in cleanup and Playwright disconnects without closing the existing browser.

### Target-specific CSS selector counts

Count matches for explicit CSS selectors on the same already-authorized exact page target:

```bash
python -m local_agent.host_ops browser attach selectors \
  --endpoint http://127.0.0.1:9222 \
  --target-id PAGE_TARGET_ID \
  --selector '#prompt-textarea' \
  --selector '#composer-submit-button' \
  --json
```

The command accepts 1 to 16 selectors, each at most 256 characters, and deduplicates exact repeats. It opens a temporary page-level CDP session, sends `DOM.getDocument` with `depth=0` / `pierce=false`, then `DOM.querySelectorAll` once per selector. It does not call `Runtime.evaluate` or Playwright locators.

Returned evidence contains only the exact target identity/type, bounded title, sanitized target URL and ordered `{selector, match_count}` records. Node ids remain inside the helper and are discarded after counting. The command does not return matched elements, text, HTML, attributes, form values, cookies/storage or selector-query vendor details. Each count is bounded and malformed selector/protocol evidence fails closed.

This primitive is intended for readiness/structure checks such as whether a composer, submit control or message container exists. Visibility, enabled/disabled state and element content are deliberately not inferred from a nonzero count.

### Target-specific extension readiness correlation

Correlate DOM readiness with known extension content-script builds on one exact page target:

```bash
python -m local_agent.host_ops browser attach readiness \
  --endpoint http://127.0.0.1:9222 \
  --target-id PAGE_TARGET_ID \
  --selector '#prompt-textarea' \
  --script-fingerprint content.js=SHA256 \
  --script-fingerprint exhaustion_guard.js=SHA256 \
  --timeout 10 \
  --json
```

The command accepts 1 to 16 selectors and 1 to 16 script fingerprints. A fingerprint is a safe script basename plus a caller-known 64-hex SHA-256 (`NAME=SHA256`). It is deliberately generic: `host-ops` does not embed Chat Bridge filenames, protocol versions or extension ids.

The helper maps only the exact page target, counts selectors through `DOM.getDocument(depth=0,pierce=false)` plus `DOM.querySelectorAll`, then briefly enables the CDP `Debugger` domain to receive existing `Debugger.scriptParsed` metadata. It never requests script source. For caller-requested basenames only, Chromium's `scriptParsed.hash` is compared with the supplied SHA-256. `Runtime.evaluate`, `Debugger.getScriptSource`, Playwright locators and page-world code execution are not used.

`chrome-extension://` origins are correlated only inside the helper. If one extension origin satisfies the requested fingerprints, `Target.getTargets` is checked for a currently running `service_worker` from that same origin. The extension id, raw extension URL, observed hash and script source are never returned. Multiple plausible extension origins fail closed into `content_script_state=ambiguous` rather than choosing one heuristically.

Returned evidence contains selector counts, per-requested-script status (`matched`, `stale` or `missing`), `dom_ready`, `content_script_state` (`ready`, `stale`, `missing` or `ambiguous`), `worker_state` (`running`, `inactive` or `unknown`) and a bounded diagnosis. Diagnosis precedence is `dom_not_ready`, `content_script_missing`, `content_script_stale`, `extension_ambiguous`, `worker_inactive`, then `ready`.

`worker_inactive` means only that no live service-worker target for the correlated extension origin was present at that instant. Manifest V3 service workers are allowed to sleep, so this is not by itself proof of failure. Use `browser attach workers` when registration/version lifecycle evidence is needed. C3 performs no reinjection, reload, worker wake or other self-heal action.

The exact page target URL is re-read after collection; if the sanitized URL or target identity changes during the inspection, the command fails closed instead of correlating evidence across navigations.

### Bounded content-script recovery

Recover a missing or stale extension content script only when C3 evidence identifies that exact condition on one exact page target:

```bash
python -m local_agent.host_ops browser attach recover-content-script \
  --endpoint http://127.0.0.1:9222 \
  --target-id PAGE_TARGET_ID \
  --expect-url https://example.test/path \
  --selector '#prompt-textarea' \
  --script-fingerprint content.js=SHA256 \
  --timeout 30 \
  --json
```

The command first performs the same bounded readiness inspection using the caller-supplied selectors and fingerprints. `--expect-url` is mandatory and must be the sanitized HTTP(S) URL previously observed for the exact target. If the pre-check URL differs, recovery fails before mutation.

Only `content_script_missing` and `content_script_stale` are actionable. `ready` and `worker_inactive` return `action=none,outcome=not_needed`; `dom_not_ready` and `extension_ambiguous` return `action=none,outcome=not_applicable`. Manifest V3 worker inactivity is deliberately not repaired or used as a reason to reload.

For an actionable diagnosis, the capability invokes the existing guarded reload exactly once. It does not add another CDP mutation path. If the reload reports a different sanitized URL, recovery returns `target_changed` and does not inspect the new page. If the URL remains the expected URL, exactly one post-reload readiness check is required. The result is `recovered` only when that post-check reports both DOM readiness and `content_script_state=ready`; otherwise it is `not_recovered`.

Returned JSON contains only bounded nested `before`, optional `reload`, and optional `after` evidence plus `action` and `outcome`. Extension ids, observed hashes, raw extension URLs and script source remain private exactly as in `browser attach readiness`. There is no `Runtime.evaluate`, script injection/reinjection, worker start/stop/update, arbitrary navigation, retry loop or repeated reload authority.

The user timeout is a whole-operation budget shared by the pre-check, optional guarded reload and optional post-check. Each composed helper receives only the remaining budget, and recovery fails closed if less than one second remains before another bounded helper could start.

### Read-only worker and service-worker diagnostics

Inspect worker-like Chromium targets plus service-worker registration/version lifecycle state for one already-authorized endpoint:

```bash
python -m local_agent.host_ops browser attach workers \
  --endpoint http://127.0.0.1:9222 \
  --timeout 10 \
  --json
```

The helper opens only a browser-level CDP session. It subscribes to `ServiceWorker.workerRegistrationUpdated`, `ServiceWorker.workerVersionUpdated` and `ServiceWorker.workerErrorReported`, enables the ServiceWorker diagnostics domain, reads `Target.getTargets`, then disables the diagnostics domain, detaches and disconnects. It never calls worker start/stop/update/unregister/skip-waiting or dispatch APIs, never attaches to a worker target, and does not use `Runtime.evaluate`.

Returned evidence is deliberately bounded: worker-like targets (`service_worker`, `worker`, `shared_worker`, `background_page`) include only target id/type, sanitized URL and attached state; registrations include only sanitized scope URL plus deleted state; service-worker versions include optional target id, optional sanitized scope URL, sanitized script URL, running/lifecycle status, controlled-client count, and correlation to target-attached/registration-deleted state. Registration ids, version ids and controlled-client ids stay inside the helper. Worker error events contribute only to `error_count`; error text, source URL and line/column details are not returned.

HTTP(S) URLs lose credentials, query and fragment. Non-HTTP(S) worker URLs are reduced to scheme-only evidence, so a `chrome-extension://...` worker is exposed only as `chrome-extension:`. A stopped registered service worker can therefore remain visible through version evidence even when there is no active `service_worker` target. This lets callers distinguish missing registration from a registered-but-stopped worker without waking or mutating it.

### Target-specific guarded reload

Reload one exact page target only after proving that its current sanitized HTTP(S) URL is the one the caller previously observed:

```bash
python -m local_agent.host_ops browser attach reload \
  --endpoint http://127.0.0.1:9222 \
  --target-id PAGE_TARGET_ID \
  --expect-url https://example.test/path \
  --timeout 15 \
  --json
```

`--expect-url` is mandatory. It must already be in the same sanitized HTTP(S) form returned by `browser attach inspect` or `browser attach snapshot`: no credentials, query or fragment. The helper maps the exact target id to one attached Playwright page, re-reads `Target.getTargetInfo`, requires target type `page`, sanitizes the live target URL and compares it exactly to `--expect-url`. A mismatch fails closed before any reload call.

If the guard passes, the helper sends `Page.reload` exactly once through the page-level CDP session and waits for the page `load` state within the bounded helper deadline. It then re-reads the same target identity and returns only normalized endpoint, exact target id/type, expected URL, and bounded before/after sanitized URL plus title evidence. C1 deliberately does not infer an HTTP response status because doing so would require a wider network-observation contract.

The reload primitive has no click, fill, press, drag, form submission, locator, arbitrary JavaScript or `Runtime.evaluate` path. It does not expose a reload loop, navigation to another URL, cookies/storage, DOM/page content, headers or response bodies. Raw target URLs and query/fragment values never become structured result fields, and the parent process revalidates the complete helper JSON shape and exact target/guard identity before returning evidence.

Unmatched temporary page CDP sessions are detached immediately. The matched session is detached in cleanup and Playwright disconnects from the existing browser; it does not close the operator's page or browser.

## Persistent isolated CDP session

Start one dedicated Chromium-family browser process with a separate persistent profile:

```bash
python -m local_agent.host_ops browser session start \
  --profile-dir /Users/example/.local/share/hostops/chat-bridge \
  --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
  --extension-dir /Users/example/local-agent/chat_bridge \
  --url https://chatgpt.com/ \
  --json
```

`--profile-dir` is mandatory, absolute and whitespace-free. On first start, `host-ops` accepts only a missing or empty directory and writes a small ownership marker. A non-empty directory without that marker is rejected, so this command cannot adopt or expose an existing normal Chrome profile accidentally. The profile remains on disk across stop/start cycles so operator logins and site state can persist inside this isolated browser only.

Chrome is launched with `--remote-debugging-address=127.0.0.1` and `--remote-debugging-port=0`. Chrome chooses a free port and records it in the profile's `DevToolsActivePort`; returned evidence exposes only the resulting loopback endpoint, root browser pid, browser version and state. No fixed debug port is reserved.

An optional start URL must be sanitized HTTP(S): no credentials, query or fragment. This keeps secrets out of the browser process command line. Unpacked extension directories are explicit, absolute, existing paths; when supplied, the session uses both `--load-extension` and `--disable-extensions-except` for that exact bounded set.

Check the exact profile:

```bash
python -m local_agent.host_ops browser session status \
  --profile-dir /Users/example/.local/share/hostops/chat-bridge \
  --json
```

Status is `running`, `stopped` or `unhealthy`. Process identity is fail-closed: the root browser must use the exact profile plus dynamic-port CDP on `127.0.0.1`, otherwise the profile is treated as being used outside the managed-session contract.

Stop only that exact managed process:

```bash
python -m local_agent.host_ops browser session stop \
  --profile-dir /Users/example/.local/share/hostops/chat-bridge \
  --json
```

Stop sends one `SIGTERM` to the exact matched root pid and waits boundedly for exit. It does not use `pkill`, process-name matching or `SIGKILL`, and refuses to signal a browser whose profile/debugging identity does not match the managed contract.

The managed-session path never enables remote debugging on the default Chrome profile. Modern Chrome also requires remote debugging switches to use a non-default user-data directory, so the isolated profile is both a security and compatibility boundary. Browser process creation goes through the shared `host_ops.core.execution.DetachedProcessSpawner`; browser capabilities do not own raw subprocess creation.

## Interactive manual session

The same host-ops-owned profile can be launched temporarily without CDP and without extension flags:

```bash
python -m local_agent.host_ops browser interactive-start   --profile-dir /Users/example/.local/share/hostops/chat-bridge   --browser-executable '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'   --url https://chatgpt.com/   --json
```

Interactive mode is for short user-driven work such as authentication that may reject an automation-enabled browser. It refuses arbitrary/unowned profiles and refuses a process that exposes CDP, so it does not silently widen automated browser authority. Status/stop are bound to the same exact profile/process identity. See [Interactive browser sessions](BROWSER_INTERACTIVE_SESSION.md) for the concise operating contract.

## Managed one-navigation probe

Install the optional Playwright adapter separately from the dependency-free core:

```bash
.venv/bin/python -m pip install -e '.[browser]'
.venv/bin/python -m playwright install chromium
```

Development environments that need both repository tooling and the adapter may install `'.[dev,browser]'` instead.

Run one disposable headless navigation:

```bash
python -m local_agent.host_ops browser probe https://example.com/ --json
python -m local_agent.host_ops browser probe https://example.com/ --engine firefox --timeout 20 --json
```

Supported engines are `chromium`, `firefox` and `webkit`. Browser binaries remain an explicit Playwright installation step; `host-ops` never silently downloads them.

The probe creates a new non-persistent browser context with downloads disabled, performs one `domcontentloaded` navigation and closes the context/browser. It does not reuse or inspect the operator's normal Chrome/Chromium/Firefox/Safari profile, cookies or storage.

Managed-probe JSON contains only:

- selected engine;
- requested URL with credentials/query/fragment removed from returned evidence;
- final URL with credentials/query/fragment removed from returned evidence;
- bounded page title;
- main navigation HTTP status when available;
- counts of console errors, page errors and failed requests.

Console text, failed-request URLs, request/response bodies, headers, cookies and storage are not returned. Playwright/vendor errors are sanitized before they can become structured CLI evidence.

## Process and timeout boundary

Playwright-backed managed probing, CDP target inventory, target-specific page snapshots, selector counts, extension readiness, worker diagnostics and guarded reload run only inside internal helper processes started through `host_ops.core.execution.ProcessRunner`. Bounded content-script recovery is parent-side orchestration of the existing readiness and reload capabilities; it introduces no additional Playwright/CDP helper or mutation command. The parent passes navigation URLs and CDP endpoint/target/readiness inputs through the helper environment rather than repeating them in helper argv, bounds retained helper stdout/stderr and validates helper JSON before returning it.

The user timeout is the whole helper-process deadline, not merely a Playwright/CDP operation timeout. The helper reserves part of that deadline for browser/context cleanup. Outside Local Agent, `ProcessRunner` owns the helper process group; under Local Agent, the existing outer Local Agent process lifecycle remains the process-group owner.

## Current mutation boundary

`browser attach reload` remains the only direct automated mutation primitive against an already-attached Chromium page. `browser attach recover-content-script` can invoke it at most once after a qualifying diagnosis and before a required readiness re-check. The other attach operations remain read-only. Persistent managed sessions control an isolated browser process/profile but expose no page-action API; interactive mode deliberately hands that owned browser to the user in no-CDP mode. `browser probe` mutates only its disposable context through one explicit navigation.

There is no public operation for:

- page-content/text extraction, matched-node export, DOM traversal beyond root metadata or selector match counts, or element attribute/value inspection;
- reload loops, repeated self-heal actions, worker wake/restart recovery or multi-page automation/orchestration;
- navigation of an attached page to a caller-supplied URL;
- click, fill, press or drag actions;
- arbitrary JavaScript evaluation;
- script-source extraction;
- screenshots or page-content extraction;
- downloads/uploads;
- cookies, local storage or session storage;
- extension mutation.

Those capabilities require separate contracts and evidence. Managed disposable contexts remain the default direction for broader browser mutation. Any further live-session diagnostics or actions must remain explicit, target-specific, separately authorized and preserve before/after evidence.

## Browser support

Process discovery recognizes common Chrome, Chromium, Edge, Brave, Firefox and Safari root processes on supported POSIX hosts.

HTTP DevTools inspection currently applies only to Chromium-family processes exposing `--remote-debugging-port`. Pipe debugging is detected and reported but not attached. Explicit `browser attach inspect`, `browser attach snapshot`, `browser attach selectors`, `browser attach readiness`, `browser attach recover-content-script`, `browser attach workers` and `browser attach reload` are Chromium-only and require an already-authorized loopback HTTP(S) CDP endpoint. Reload additionally requires an exact `page` target with an HTTP(S) URL and a matching previously observed sanitized expected URL.

Managed probing uses the optional Playwright engines listed above and is independent of whether the operator already has a browser open.
