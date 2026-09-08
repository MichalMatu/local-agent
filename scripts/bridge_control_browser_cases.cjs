"use strict";

const assert = require("node:assert/strict");

module.exports = async function verifyDecoratedControls({ page, request, readChat, add, worker }) {
  const id = await add("decorated-controls");
  await request({ type: "bridge:save-global-settings", settings: { masterEnabled: false } });
  await request({ type: "bridge:update-conversation", conversationId: id,
    patch: { enabled: true, intervalOverrideMinutes: 17 } });
  const original = await readChat(id);
  let identity = 0;
  const append = (html, role = "assistant") => page.evaluate(({ html, role, identity }) => {
    const answer = document.createElement("div");
    answer.dataset.messageAuthorRole = role;
    answer.dataset.messageId = `decorated-answer-${identity}`;
    answer.innerHTML = html;
    document.body.append(answer);
  }, { html, role, identity: ++identity });

  async function accept(html, marker, enabled, interval, scheduled) {
    const before = await readChat(id);
    const started = Date.now();
    await append(html);
    const matches = (chat) => chat.generation === before.generation + 1 && chat.lastControlAction === marker &&
      chat.enabled === enabled && chat.intervalOverrideMinutes === interval &&
      Boolean(chat.nextRunAt) === scheduled && (!scheduled || chat.nextRunAt !== before.nextRunAt);
    const deadline = Date.now() + 5000;
    let after = await readChat(id);
    while (!matches(after) && Date.now() < deadline) {
      await page.waitForTimeout(50);
      after = await readChat(id);
    }
    assert.ok(matches(after), `${html}: ${JSON.stringify(after)}`);
    for (const key of ["agentBinding", "repositoryId", "repository", "bindingRevision", "assistantBaseline"]) {
      assert.equal(after[key], original[key], `${html} changed ${key}`);
    }
    assert.equal((await request({ type: "bridge:get-state" })).state.settings.masterEnabled, false);
    assert.equal(await worker.evaluate((id) => chrome.alarms.get(`local-agent-chat:${id}`), id), undefined);
    if (marker === "[LAB:NEXT=10m]") {
      assert.ok(Date.parse(after.nextRunAt) >= started + 600_000,
        JSON.stringify({ started, nextRunAt: after.nextRunAt, lastControlAt: after.lastControlAt }));
      assert.ok(Date.parse(after.nextRunAt) <= Date.now() + 600_000);
    }
    return after;
  }

  await accept("<p>Acknowledged.[LAB:PAUSE]</p>", "[LAB:PAUSE]", false, 17, false);
  await accept('<p>Acknowledged. "[LAB:RESUME]"</p>', "[LAB:RESUME]", true, 17, true);
  await accept("<p>Check later. [LAB:NEXT=10m] -</p>", "[LAB:NEXT=10m]", true, 17, true);
  await accept("<p>Interval:<strong>[LAB:INTERVAL=5]</strong>.</p>", "[LAB:INTERVAL=5]", true, 5, true);
  await accept("<pre><code>[LAB:PAUSE]</code></pre>", "[LAB:PAUSE]", false, 5, false);
  await accept("<p><code>[LAB:RESUME]</code></p>", "[LAB:RESUME]", true, 5, true);
  await accept("<blockquote>[LAB:STOP]</blockquote>", "[LAB:STOP]", false, null, false);
  await accept("<p>Done.[LOCAL_AGENT_BRIDGE:RESUME]</p>", "[LOCAL_AGENT_BRIDGE:RESUME]", true, null, true);
  await accept("<p>[LAB:PAUSE]</p><p>—</p>", "[LAB:PAUSE]", false, null, false);
  await accept("<p>[LAB:PAUSE] [LAB:RESUME]!</p>", "[LAB:RESUME]", true, null, true);

  const duplicateBaseline = await readChat(id);
  await page.evaluate(() => {
    const answers = document.querySelectorAll('[data-message-author-role="assistant"]');
    answers[answers.length - 1].append(document.createElement("span"));
  });
  await page.waitForTimeout(1000);
  assert.deepEqual(await readChat(id), duplicateBaseline);
  const resumed = await accept("<p>[LAB:PAUSE] [LAB:RESUME]!</p>", "[LAB:RESUME]", true, null, true);
  assert.ok(Date.parse(resumed.nextRunAt) > Date.parse(duplicateBaseline.nextRunAt));
  console.log("PASS: decorated and rendered Markdown controls reach the worker with unchanged binding, Master and timing semantics");

  for (const html of [
    "<p>[LAB:PAUSE] Continue.</p>", "<p>[LAB:PAUSE]</p><p>—</p><p>Continue.</p>",
    "<p>[LAB:PAUSE] [LAB:NEXT=29s]</p>", "<p>[LAB:PAUSE] [LAB:</p>",
    "<p>[LAB:NEXT=86401s].</p>", "<p>[LAB:INTERVAL=90s] —</p>",
    "<p>[lab:pause]</p>", "<p>[LAB:PAUSE]🙂</p>"
  ]) {
    const before = await readChat(id);
    await append(html);
    await page.waitForTimeout(1000);
    assert.deepEqual(await readChat(id), before, html);
  }
  const beforeUser = await readChat(id);
  await append("<p>Acknowledged.[LAB:PAUSE]</p>", "user");
  await page.waitForTimeout(1000);
  assert.deepEqual(await readChat(id), beforeUser, "user text must not become an assistant control");
  await accept("<p>Acknowledged.[LAB:PAUSE].</p>", "[LAB:PAUSE]", false, null, false);
  assert.equal(await page.evaluate(() => window.submits), 0);
  console.log("PASS: trailing prose, invalid final candidates, invalid ranges and user messages leave conversation state unchanged");

  await add("help-feedback-submit");
  const beforeHelpUsers = await page.locator('[data-message-author-role="user"]').count();
  await page.evaluate(() => {
    const answer = document.createElement("div");
    answer.dataset.messageAuthorRole = "assistant";
    answer.dataset.messageId = "help-feedback-answer";
    answer.textContent = "[LAB:HELP]";
    document.body.append(answer);
  });
  await page.waitForFunction(() => {
    const composer = document.querySelector("#prompt-textarea");
    const text = composer?.innerText || composer?.textContent || "";
    return text.includes("[LA_BRIDGE_FEEDBACK]") && text.includes("command=HELP");
  }, null, { timeout: 5000 });
  const preSubmit = await page.evaluate(() => ({
    composer: document.querySelector("#prompt-textarea")?.innerText || document.querySelector("#prompt-textarea")?.textContent || "",
    submits: window.submits,
    buttonDisabled: document.querySelector("#composer-submit-button")?.disabled,
    buttonConnected: document.querySelector("#composer-submit-button")?.isConnected,
    buttonType: document.querySelector("#composer-submit-button")?.type
  }));
  assert.match(preSubmit.composer, /\[LA_BRIDGE_FEEDBACK\]/);
  assert.match(preSubmit.composer, /command=HELP/);
  assert.equal(preSubmit.buttonDisabled, false);
  assert.equal(preSubmit.buttonConnected, true);
  assert.equal(preSubmit.buttonType, "submit");
  console.log("PASS: LAB HELP feedback reaches an enabled live Send control");
  await page.waitForFunction((beforeCount) => {
    const messages = document.querySelectorAll('[data-message-author-role="user"]');
    if (messages.length <= beforeCount) return false;
    const latest = messages[messages.length - 1];
    const text = latest.innerText || latest.textContent || "";
    return text.includes("[LA_BRIDGE_FEEDBACK]") && text.includes("command=HELP");
  }, beforeHelpUsers, { timeout: 7000 });
  assert.equal(await page.evaluate(() => window.submits), 1);
  assert.equal(await page.locator("#prompt-textarea").textContent(), "");
  console.log("PASS: LAB HELP feedback is submitted automatically through the live Send path");

  const operatorBaselineId = await add("operator-replay-baseline");
  const operatorBaselineUrl = page.url();
  await page.evaluate(() => {
    try { globalThis.__localAgentChatBridgeState?.dispose?.(); } catch (_error) {}
    globalThis.__localAgentChatBridgeState = null;
  });
  await append("<p>[LAB:OP:REMOVE]</p>", "user");
  const operatorTabId = await worker.evaluate(async (url) => {
    const tabs = await chrome.tabs.query({ url: ["https://chatgpt.com/*", "https://chat.openai.com/*"] });
    return tabs.find((tab) => tab.url === url)?.id || null;
  }, operatorBaselineUrl);
  assert.ok(operatorTabId, "fixture tab id must be discoverable");
  const ensured = await request({
    type: "bridge:ensure-tab-content",
    tabId: operatorTabId,
    expectedUrl: operatorBaselineUrl
  });
  assert.equal(ensured.ok, true, ensured.reason);
  await page.waitForTimeout(1200);
  assert.ok(await readChat(operatorBaselineId), "historical OP marker must be baselined, not replayed after reinjection");
  await append("<p>[LAB:OP:REMOVE]</p>", "user");
  const operatorDeadline = Date.now() + 5000;
  while (await readChat(operatorBaselineId) && Date.now() < operatorDeadline) {
    await page.waitForTimeout(50);
  }
  assert.equal(await readChat(operatorBaselineId), undefined, "new user-authored OP marker must execute after baseline");
  console.log("PASS: operator LAB controls baseline historical user messages across content reinjection");

  const retainedId = await add("retained-unconfirmed-browser-case");
  await page.evaluate(() => { window.dropDelivery = true; });
  const firstUnconfirmed = await request({ type: "bridge:run-now", conversationId: retainedId });
  assert.equal(firstUnconfirmed.reason, "delivery_unconfirmed");
  const retainedPrompt = await page.locator("#prompt-textarea").textContent();
  assert.match(retainedPrompt, /\[LA_REPO=tracker\]/);
  assert.equal(await page.evaluate(() => window.submits), 1);
  await page.locator("#prompt-textarea").fill(`${retainedPrompt} operator-edit`);
  const blockedRetry = await request({ type: "bridge:run-now", conversationId: retainedId });
  assert.equal(blockedRetry.reason, "composer_not_empty");
  assert.equal(await page.evaluate(() => window.submits), 1);
  assert.match(await page.locator("#prompt-textarea").textContent(), /operator-edit$/);
  await page.evaluate(() => { window.dropDelivery = false; });
  console.log("PASS: unconfirmed Bridge prompt stays visible and any operator edit blocks automatic reuse");
};
