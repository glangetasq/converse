/* End-to-end harness: extension + mini-LinkedIn + backend(3001) + fake provider(8990). */

const { chromium } = require("playwright");
const { spawn } = require("child_process");
const path = require("path");

const REPO = path.resolve(__dirname, "../..");
const SHOTS = path.join(__dirname, "shots");
const FAKE_PROVIDER = path.join(__dirname, "fake_provider.py");
const FIXTURE = "http://localhost:8899";
const BACKEND = "http://localhost:3001";
const HAIKU = "claude-haiku-4-5-20251001";

const children = [];
let failures = 0;

function run(cmd, args, opts = {}) {
  const child = spawn(cmd, args, { stdio: ["ignore", "inherit", "inherit"], ...opts });
  children.push(child);
  return child;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForHttp(url, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      await fetch(url);
      return;
    } catch (_e) {
      await sleep(300);
    }
  }
  throw new Error(`Timed out waiting for ${url}`);
}

function check(name, condition, detail = "") {
  const status = condition ? "PASS" : "FAIL";
  if (!condition) failures += 1;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ""}`);
}

async function waitFor(fn, timeoutMs = 8000, interval = 150) {
  const deadline = Date.now() + timeoutMs;
  let last;
  while (Date.now() < deadline) {
    last = await fn();
    if (last) return last;
    await sleep(interval);
  }
  return last;
}

(async () => {
  run("python3", [path.join(REPO, "dev/mini-linkedin/serve.py")]);
  run("python3", [FAKE_PROVIDER, "8990"]);
  run(path.join(REPO, "backend/.venv/bin/python"), ["-m", "uvicorn", "app.main:app", "--port", "3001"], {
    cwd: path.join(REPO, "backend"),
    env: {
      ...process.env,
      PORT: "3001",
      OPENAI_API_KEY: "test-key",
      ANTHROPIC_API_KEY: "test-key",
      OPENAI_API_BASE_URL: "http://127.0.0.1:8990",
      CLAUDE_API_BASE_URL: "http://127.0.0.1:8990"
    }
  });

  await waitForHttp(`${FIXTURE}/`);
  await waitForHttp(`${BACKEND}/health`);
  console.log("[setup] fixture + backend up");

  const context = await chromium.launchPersistentContext("", {
    channel: "chromium",
    headless: true,
    viewport: { width: 420, height: 800 },
    args: [`--disable-extensions-except=${REPO}`, `--load-extension=${REPO}`]
  });

  let [sw] = context.serviceWorkers();
  if (!sw) sw = await context.waitForEvent("serviceworker", { timeout: 10000 });
  const extId = new URL(sw.url()).host;
  console.log(`[setup] extension ${extId}`);

  // --- login (also pins backend_url override for all extension pages) ---
  const loginPage = await context.newPage();
  await loginPage.goto(`chrome-extension://${extId}/frontend/login.html`);
  await loginPage.evaluate((url) => chrome.storage.local.set({ backend_url: url }), BACKEND);
  await loginPage.reload();
  await loginPage.click("#login-submit-button");
  const loginStatus = await waitFor(async () => {
    const text = await loginPage.textContent("#login-status-output");
    return text.includes("signed in as") ? text : null;
  });
  check("login: signed in", Boolean(loginStatus), loginStatus ?? "no status");

  // --- fixture messaging tab + popup-as-tab ---
  const messagingPage = await context.newPage();
  await messagingPage.goto(`${FIXTURE}/messaging/thread/abc/`);

  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${extId}/frontend/popup.html`);
  await messagingPage.bringToFront();
  await sleep(700);

  const modelValue = await waitFor(async () => {
    const value = await popup.inputValue("#model-select");
    return value || null;
  });
  check("composer: default model is haiku", modelValue === HAIKU, String(modelValue));

  const optionCount = await popup.locator("#model-select option").count();
  check("composer: model menu populated from backend", optionCount >= 9, `${optionCount} options`);

  const badge = await popup.textContent(".badge-site");
  check("composer: site badge follows active tab", badge === "localhost", String(badge));

  // --- generate (haiku → fake claude) ---
  await popup.fill("#context-input", "Mention the Berlin conference.");
  await popup.click("#generate-button");
  const suggestion = await waitFor(async () => {
    const value = await popup.inputValue("#suggestion-output");
    return value.trim() ? value : null;
  }, 15000);
  check(
    "generate: suggestion via claude path with context",
    Boolean(suggestion && suggestion.includes(`FAKE_SUGGESTION[${HAIKU}|with-context]`)),
    (suggestion ?? "").slice(0, 90)
  );
  // the dev corpus holds self-profile facts for the sender, so RAG returns evidence
  const evidenceVisible = await popup.locator("#evidence-details").isVisible();
  const evidenceText = evidenceVisible ? await popup.textContent("#evidence-output") : "";
  check("generate: RAG evidence block shows sender facts", evidenceVisible && evidenceText.includes("About"), evidenceText.slice(0, 60));

  // --- ingest: edit the draft, then save it with provenance ---
  await popup.fill("#suggestion-output", `${suggestion} See you Thursday!`);
  await popup.click("#ingest-button");
  const ingestStatus = await waitFor(async () => {
    const text = await popup.textContent("#results-status");
    return text.includes("ingested") || text.includes("failed") ? text : null;
  }, 10000);
  check(
    "ingest: edited draft saved with similarity",
    Boolean(ingestStatus?.includes("ingested (edited)") && /similarity -?[01]\.\d{3}/.test(ingestStatus)),
    String(ingestStatus)
  );
  const ingestDisabled = await popup.locator("#ingest-button").isDisabled();
  check("ingest: button locks after success", ingestDisabled);
  await popup.screenshot({ path: path.join(SHOTS, "results.png") });

  // --- workbench: parse + rate + preview ---
  await popup.click("#workbench-tab-button");
  const itemCount = await waitFor(async () => {
    const count = await popup.locator(".message-item").count();
    return count === 6 ? count : null;
  });
  check("workbench: 6 parsed messages", itemCount === 6, String(itemCount));

  const listHeader = await popup.textContent(".message-list-header");
  check("workbench: participant header", listHeader?.includes("Maya Lindqvist — 6 messages"), String(listHeader));

  const selfCount = await popup.locator(".message-item.is-self").count();
  check("workbench: self messages flagged", selfCount === 3, `${selfCount} self`);

  // rate first message 5 stars, ignore the last one
  await popup.locator(".message-item").first().locator(".star-button").nth(4).click();
  await popup.locator(".message-item").last().locator(".include-toggle").click();

  await popup.click("#preview-toggle-button");
  const previewText = await waitFor(async () => {
    const text = await popup.textContent("#prompt-preview-output");
    return text.trim() ? text : null;
  }, 10000);
  check(
    "workbench: prompt preview contains thread + context",
    Boolean(
      previewText
      && previewText.includes("Maya Lindqvist")
      && previewText.includes("Additional context from the sender")
      && previewText.includes("Mention the Berlin conference.")
    )
  );
  const previewStatus = await popup.textContent("#workbench-status");
  check("workbench: preview status v1, RAG ok", previewStatus?.includes("v1") && !previewStatus?.includes("RAG unavailable"), String(previewStatus));

  await popup.click("#save-example-button");
  const saveStatus = await waitFor(async () => {
    const text = await popup.textContent("#workbench-status");
    return text.includes("saved") || text.includes("failed") ? text : null;
  }, 10000);
  check("workbench: eval example saved (5 messages)", Boolean(saveStatus?.includes("saved 5 rated messages")), String(saveStatus));
  await popup.screenshot({ path: path.join(SHOTS, "workbench.png") });

  // --- per-tab state: switch to profile tab, inputs reset ---
  const profilePage = await context.newPage();
  await profilePage.goto(`${FIXTURE}/in/maya-lindqvist`);
  await profilePage.bringToFront();
  const resetContext = await waitFor(async () => {
    const value = await popup.inputValue("#context-input");
    return value === "" ? "" : null;
  }, 8000, 300);
  check("tabs: new tab resets context input", resetContext === "");

  const composerVisible = await popup.locator("#composer-view").isVisible();
  check("tabs: new tab lands on composer view", composerVisible);

  await popup.fill("#context-input", "profile tab note");

  // workbench on profile tab: raw JSON + save profile
  await popup.click("#workbench-tab-button");
  const profileJson = await waitFor(async () => {
    const visible = await popup.locator("#parse-json").isVisible();
    if (!visible) return null;
    const text = await popup.textContent("#parse-json");
    return text.includes("Maya") ? text : null;
  }, 10000);
  check("workbench: profile parses to raw JSON", Boolean(profileJson?.includes('"first_name": "Maya"')));

  await popup.click("#save-profile-button");
  const profileSaveStatus = await waitFor(async () => {
    const text = await popup.textContent("#workbench-status");
    return text.includes("saved") || text.includes("duplicate") || text.includes("failed") ? text : null;
  }, 10000);
  check("workbench: profile saved", Boolean(profileSaveStatus?.match(/saved profile|duplicate/)), String(profileSaveStatus));

  // --- switch back: context + results restored ---
  await messagingPage.bringToFront();
  const restored = await waitFor(async () => {
    const value = await popup.inputValue("#context-input");
    return value === "Mention the Berlin conference." ? value : null;
  }, 8000, 300);
  check("tabs: switching back restores context", Boolean(restored));

  // the last view used on the messaging tab was the workbench — it should come back
  const workbenchRestored = await waitFor(() => popup.locator("#workbench-view").isVisible(), 8000, 300);
  check("tabs: last view (workbench) restored on switch-back", Boolean(workbenchRestored));

  // --- model switch exercises the openai path ---
  await popup.click("#compose-tab-button");
  await popup.selectOption("#model-select", "gpt-5.4-nano");
  await popup.click("#generate-button");
  const nanoSuggestion = await waitFor(async () => {
    const value = await popup.inputValue("#suggestion-output");
    return value.includes("gpt-5.4-nano") ? value : null;
  }, 15000);
  check(
    "generate: openai path with selected model",
    Boolean(nanoSuggestion?.includes("FAKE_SUGGESTION[gpt-5.4-nano|with-context]")),
    (nanoSuggestion ?? "").slice(0, 80)
  );

  // --- pick injects into the fixture compose box ---
  await popup.click("#pick-button");
  await sleep(600);
  const composeText = await messagingPage.textContent(".msg-form__contenteditable");
  check("pick: suggestion injected into page compose box", Boolean(composeText?.includes("FAKE_SUGGESTION")), (composeText ?? "").slice(0, 60));

  // --- screenshots for theme review ---
  const popup2 = await context.newPage();
  await popup2.goto(`chrome-extension://${extId}/frontend/popup.html`);
  await messagingPage.bringToFront();
  await sleep(800);
  await popup2.screenshot({ path: path.join(SHOTS, "composer.png") });
  await loginPage.bringToFront();
  await loginPage.screenshot({ path: path.join(SHOTS, "login.png") });

  await context.close();
  console.log(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);
  process.exitCode = failures === 0 ? 0 : 1;
})()
  .catch((error) => {
    console.error("HARNESS ERROR:", error);
    process.exitCode = 2;
  })
  .finally(() => {
    children.forEach((child) => {
      try {
        child.kill("SIGTERM");
      } catch (_e) {}
    });
  });
