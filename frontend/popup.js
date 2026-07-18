const CURRENT_USER_STORAGE_KEY = "current_user";
const CURRENT_USER_ID_STORAGE_KEY = "current_user_id";
const SELECTED_MODEL_STORAGE_KEY = "selected_model";
const TAB_STATE_PREFIX = "tabState:";
const TAB_STATE_TTL_MS = 30 * 60 * 1000;
const PARSE_RETRY_DELAY_MS = 250;
const PARSE_RETRY_TIMEOUT_MS = 3500;
const MESSAGING_PARSER_ID = "linkedin-messaging";
const PROFILE_PARSER_ID = "linkedin-profile";
const DEFAULT_SELF_NAME = "Quentin Glangetas";
const SELF_RATING_LABELS = ["very poor", "poor", "neutral", "good", "very good"];
const OTHER_RATING_LABELS = ["unhelpful", "confused", "neutral", "good", "very good"];
const PARSER_FILES = [
  "frontend/content/parsing/runtime.js",
  "frontend/content/parsing/helpers.js",
  "frontend/content/parsing/execute.js",
  "frontend/content/parsing/parsers/linkedin-profile.js",
  "frontend/content/parsing/parsers/linkedin-messaging.js"
];
const SUGGESTION_INJECTION_FILE = "frontend/content/injection/suggestion-injection.js";

const viewButtons = Array.from(document.querySelectorAll("[data-view-button]"));
const composerView = document.getElementById("composer-view");
const resultsView = document.getElementById("results-view");
const workbenchView = document.getElementById("workbench-view");
const settingsView = document.getElementById("settings-view");
const settingsBackendUrl = document.getElementById("settings-backend-url");
const settingsApiKey = document.getElementById("settings-api-key");
const settingsSaveButton = document.getElementById("settings-save-button");
const settingsTestButton = document.getElementById("settings-test-button");
const settingsStatus = document.getElementById("settings-status");
const currentUserBadges = Array.from(document.querySelectorAll("[data-current-user]"));
const sourceSiteBadges = Array.from(document.querySelectorAll("[data-source-site]"));
const loginOpenButton = document.getElementById("login-open-button");
const modelSelect = document.getElementById("model-select");
const refreshModelsButton = document.getElementById("refresh-models-button");
const contextInput = document.getElementById("context-input");
const generateButton = document.getElementById("generate-button");
const composerStatus = document.getElementById("composer-status");
const generationLoader = document.getElementById("generation-loader");
const generationError = document.getElementById("generation-error");
const generationErrorTitle = document.getElementById("generation-error-title");
const generationErrorDetail = document.getElementById("generation-error-detail");
const suggestionPanel = document.getElementById("suggestion-panel");
const suggestionOutput = document.getElementById("suggestion-output");
const evidenceDetails = document.getElementById("evidence-details");
const evidenceOutput = document.getElementById("evidence-output");
const resultsStatus = document.getElementById("results-status");
const generationTiming = document.getElementById("generation-timing");
const pickButton = document.getElementById("pick-button");
const copySuggestionButton = document.getElementById("copy-suggestion-button");
const backButton = document.getElementById("back-button");
const regenerateButton = document.getElementById("regenerate-button");
const ingestButton = document.getElementById("ingest-button");
const refreshParseButton = document.getElementById("refresh-parse-button");
const saveProfileButton = document.getElementById("save-profile-button");
const saveExampleButton = document.getElementById("save-example-button");
const previewToggleButton = document.getElementById("preview-toggle-button");
const workbenchStatus = document.getElementById("workbench-status");
const parsePanel = document.getElementById("parse-panel");
const messageList = document.getElementById("message-list");
const parseJson = document.getElementById("parse-json");
const parseJsonBlock = document.getElementById("parse-json-block");
const copyParseJsonButton = document.getElementById("copy-parse-json-button");
const previewPanel = document.getElementById("preview-panel");
const promptPreviewOutput = document.getElementById("prompt-preview-output");
const copyPromptButton = document.getElementById("copy-prompt-button");

const state = {
  windowId: Number.NaN,
  tabId: Number.NaN,
  tabUrl: "",
  view: "composer",
  currentUser: "",
  suggestion: "",
  originalSuggestion: "",
  generationId: null,
  evidence: null,
  ingest: null,
  generationMs: null,
  generationState: "idle",
  parseSequence: 0,
  generateSequence: 0,
  workbench: {
    parse: null,
    selections: [],
    previewVisible: false
  }
};

function normalizeErrorMessage(value, fallback = "Something went wrong.") {
  if (typeof value !== "string") {
    return fallback;
  }

  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized || fallback;
}

function errorText(error) {
  return normalizeErrorMessage(error instanceof Error ? error.message : String(error));
}

function normalizeName(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

function isSelfSender(sender) {
  return normalizeName(sender) === normalizeName(state.currentUser || DEFAULT_SELF_NAME);
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function formatDuration(ms) {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }
  if (ms < 60000) {
    return `${(ms / 1000).toFixed(1)}s`;
  }

  const minutes = Math.floor(ms / 60000);
  const seconds = Math.round((ms % 60000) / 1000);
  return seconds === 0 ? `${minutes}min` : `${minutes}min ${seconds}s`;
}

function setStatus(element, message, tone = "muted") {
  if (!element) {
    return;
  }

  element.textContent = message;
  element.classList.toggle("is-success", tone === "success");
  element.classList.toggle("is-error", tone === "error");
}

// --- views ---------------------------------------------------------------

function setView(view) {
  state.view = view;
  const showingComposer = view === "composer";
  const showingResults = view === "results";
  const showingWorkbench = view === "workbench";
  const showingSettings = view === "settings";

  composerView.hidden = !showingComposer;
  resultsView.hidden = !showingResults;
  workbenchView.hidden = !showingWorkbench;
  settingsView.hidden = !showingSettings;

  viewButtons.forEach((button) => {
    const target = button.dataset.viewButton;
    // the compose tab stays lit for the results view: results is compose's outcome
    const isSelected = target === view || (target === "composer" && showingResults);
    button.classList.toggle("is-selected", isSelected);
  });
}

function openView(view) {
  setView(view);
  scheduleTabStateSave();

  if (view === "workbench" && !state.workbench.parse) {
    refreshWorkbenchParse();
  }

  if (view === "settings") {
    loadSettingsFields();
  }
}

// --- settings ------------------------------------------------------------

async function loadSettingsFields() {
  const { baseUrl, apiKey } = await ConverseApi.getSettings();
  settingsBackendUrl.value = baseUrl;
  settingsApiKey.value = apiKey;
  setStatus(settingsStatus, "");
}

async function saveSettings() {
  await ConverseApi.saveSettings({
    backendUrl: settingsBackendUrl.value,
    apiKey: settingsApiKey.value
  });
  const { baseUrl } = await ConverseApi.getSettings();
  settingsBackendUrl.value = baseUrl;
  setStatus(settingsStatus, `saved — using ${baseUrl}`, "success");
}

async function testSettings() {
  settingsTestButton.disabled = true;
  setStatus(settingsStatus, "testing… (a cold backend takes a few seconds)");
  try {
    // /health proves reachability; a real endpoint proves the api key and the db.
    await ConverseApi.checkHealth();
    await ConverseApi.getModels();
    setStatus(settingsStatus, "ok — reachable and authorised", "success");
  } catch (error) {
    setStatus(settingsStatus, error.message, "error");
  } finally {
    settingsTestButton.disabled = false;
  }
}

function setResultsState(resultsState) {
  state.generationState = resultsState;
  generationLoader.hidden = resultsState !== "loading";
  generationError.hidden = resultsState !== "error";
  suggestionPanel.hidden = resultsState !== "suggestion";

  const busy = resultsState === "loading";
  generateButton.disabled = busy;
  regenerateButton.disabled = busy;
}

function formatIngestStatus(ingest) {
  if (!ingest) {
    return "";
  }

  const similarity = typeof ingest.similarity === "number" ? ` — similarity ${ingest.similarity.toFixed(3)}` : "";
  return `ingested (${ingest.feedback})${similarity}`;
}

function renderIngestState() {
  const hasText = Boolean(state.suggestion.trim());
  ingestButton.disabled = !hasText || !state.generationId || Boolean(state.ingest);
  ingestButton.textContent = state.ingest ? "ingested" : "ingest";
  setStatus(resultsStatus, formatIngestStatus(state.ingest), state.ingest ? "success" : "muted");
}

function renderSuggestion() {
  suggestionOutput.value = state.suggestion;
  generationTiming.hidden = typeof state.generationMs !== "number";
  generationTiming.textContent = generationTiming.hidden ? "" : formatDuration(state.generationMs);
  evidenceDetails.hidden = !state.evidence;
  evidenceOutput.textContent = state.evidence ?? "";
  pickButton.disabled = !state.suggestion.trim();
  copySuggestionButton.disabled = !state.suggestion.trim();
  renderIngestState();
  setResultsState("suggestion");
  window.requestAnimationFrame(() => {
    autosizeSuggestionOutput();
  });
}

function renderGenerationError(title, detail) {
  generationErrorTitle.textContent = title;
  generationErrorDetail.textContent = detail;
  setResultsState("error");
}

function autosizeSuggestionOutput() {
  suggestionOutput.style.height = "auto";
  const maxHeight = Math.round(window.innerHeight * 0.5);
  const targetHeight = Math.min(suggestionOutput.scrollHeight + 2, maxHeight);
  suggestionOutput.style.height = `${targetHeight}px`;
  suggestionOutput.style.overflowY = suggestionOutput.scrollHeight > maxHeight ? "auto" : "hidden";
}

// --- badges ---------------------------------------------------------------

function getSourceSiteLabel(url) {
  if (!url) {
    return "";
  }

  try {
    const parsed = new URL(url);
    if (parsed.protocol === "chrome:" || parsed.protocol === "chrome-extension:") {
      return "";
    }

    return parsed.hostname.replace(/^www\./, "");
  } catch (_error) {
    return "";
  }
}

function renderSourceBadge() {
  const label = getSourceSiteLabel(state.tabUrl);
  sourceSiteBadges.forEach((badge) => {
    badge.textContent = label;
    badge.hidden = !label;
  });
}

async function renderCurrentUserBadge() {
  const stored = await chrome.storage.local.get([CURRENT_USER_STORAGE_KEY, CURRENT_USER_ID_STORAGE_KEY]);
  const currentUser = String(stored[CURRENT_USER_STORAGE_KEY] ?? "").trim();
  const currentUserId = String(stored[CURRENT_USER_ID_STORAGE_KEY] ?? "").trim();
  state.currentUser = currentUser;

  const isLoggedIn = Boolean(currentUser && currentUserId);
  currentUserBadges.forEach((badge) => {
    badge.textContent = currentUser;
    badge.hidden = !isLoggedIn;
    badge.title = currentUserId ? `user id ${currentUserId}` : currentUser;
  });

  loginOpenButton.classList.toggle("is-authenticated", isLoggedIn);
  loginOpenButton.title = isLoggedIn ? `signed in as ${currentUser}` : "open login page";
}

// --- models ---------------------------------------------------------------

async function loadModels({ refresh = false } = {}) {
  let catalog;
  try {
    catalog = refresh ? await ConverseApi.refreshModels() : await ConverseApi.getModelsCached();
  } catch (error) {
    modelSelect.replaceChildren(new Option("backend offline — no models", "", true, true));
    setStatus(composerStatus, errorText(error), "error");
    return false;
  }

  const models = Array.isArray(catalog?.models) ? catalog.models : [];
  modelSelect.replaceChildren();
  models.forEach((model) => {
    modelSelect.append(new Option(`${model.id} · ${model.provider}`, model.id));
  });

  const { [SELECTED_MODEL_STORAGE_KEY]: storedModel } = await chrome.storage.local.get(SELECTED_MODEL_STORAGE_KEY);
  const modelIds = models.map((model) => model.id);
  modelSelect.value = modelIds.includes(storedModel) ? storedModel : catalog.default;
  setStatus(composerStatus, "");
  return true;
}

// --- per-tab state ---------------------------------------------------------

function tabStateKey(tabId) {
  return `${TAB_STATE_PREFIX}${tabId}`;
}

async function saveTabState() {
  if (!Number.isInteger(state.tabId) || !chrome.storage?.session) {
    return;
  }

  const snapshot = {
    savedAt: Date.now(),
    context: contextInput.value,
    view: state.view,
    suggestion: state.suggestion,
    originalSuggestion: state.originalSuggestion,
    generationId: state.generationId,
    evidence: state.evidence,
    ingest: state.ingest
  };

  const isEmpty = !snapshot.context.trim() && !snapshot.suggestion && snapshot.view === "composer";
  if (isEmpty) {
    await chrome.storage.session.remove(tabStateKey(state.tabId));
    return;
  }

  await chrome.storage.session.set({ [tabStateKey(state.tabId)]: snapshot });
}

let tabStateSaveTimer = null;

function scheduleTabStateSave() {
  if (tabStateSaveTimer) {
    window.clearTimeout(tabStateSaveTimer);
  }

  tabStateSaveTimer = window.setTimeout(() => {
    tabStateSaveTimer = null;
    saveTabState().catch(() => {});
  }, 250);
}

async function restoreTabState() {
  let snapshot = null;

  if (Number.isInteger(state.tabId) && chrome.storage?.session) {
    const key = tabStateKey(state.tabId);
    const stored = await chrome.storage.session.get(key);
    snapshot = stored[key] ?? null;

    if (snapshot && Date.now() - (snapshot.savedAt ?? 0) > TAB_STATE_TTL_MS) {
      await chrome.storage.session.remove(key);
      snapshot = null;
    }
  }

  contextInput.value = snapshot?.context ?? "";
  state.suggestion = snapshot?.suggestion ?? "";
  state.originalSuggestion = snapshot?.originalSuggestion ?? "";
  state.generationId = snapshot?.generationId ?? null;
  state.evidence = snapshot?.evidence ?? null;
  state.ingest = snapshot?.ingest ?? null;
  // not snapshotted: a restored suggestion has no honest timing to report
  state.generationMs = null;
  state.workbench.parse = null;
  state.workbench.selections = [];
  state.workbench.previewVisible = false;
  resetWorkbenchDisplay();

  const view = ["composer", "results", "workbench"].includes(snapshot?.view) ? snapshot.view : "composer";
  setView(view === "results" && !state.suggestion ? "composer" : view);

  if (state.view === "results") {
    renderSuggestion();
  } else {
    setResultsState("idle");
  }

  if (state.view === "workbench") {
    refreshWorkbenchParse();
  }
}

async function pruneExpiredTabStates() {
  if (!chrome.storage?.session) {
    return;
  }

  const everything = await chrome.storage.session.get(null);
  const now = Date.now();
  const expiredKeys = Object.entries(everything)
    .filter(([key, value]) => (
      key.startsWith(TAB_STATE_PREFIX) && now - (value?.savedAt ?? 0) > TAB_STATE_TTL_MS
    ))
    .map(([key]) => key);

  if (expiredKeys.length > 0) {
    await chrome.storage.session.remove(expiredKeys);
  }
}

// --- active-tab targeting ---------------------------------------------------

function isOwnExtensionPage(url) {
  return typeof url === "string" && url.startsWith(chrome.runtime.getURL(""));
}

async function findTargetTab() {
  const [activeTab] = await chrome.tabs.query({ active: true, windowId: state.windowId });
  if (activeTab && !isOwnExtensionPage(activeTab.url ?? "")) {
    return activeTab;
  }

  // In the side panel the active tab is never this page itself; this fallback only
  // triggers when popup.html runs as a regular tab (e2e harness) — target the most
  // recently used web tab instead.
  const activeTabs = await chrome.tabs.query({ active: true });
  const webTabs = activeTabs.filter((tab) => !isOwnExtensionPage(tab.url ?? ""));
  webTabs.sort((left, right) => (right.lastAccessed ?? 0) - (left.lastAccessed ?? 0));
  return webTabs[0] ?? null;
}

async function adoptActiveTab({ initial = false } = {}) {
  let tab = null;
  try {
    tab = await findTargetTab();
  } catch (_error) {
    return;
  }

  if (!tab || !Number.isInteger(tab.id)) {
    return;
  }

  if (!initial && tab.id === state.tabId) {
    state.tabUrl = tab.url ?? state.tabUrl;
    renderSourceBadge();
    return;
  }

  if (!initial) {
    await saveTabState().catch(() => {});
  }

  state.tabId = tab.id;
  state.tabUrl = tab.url ?? "";
  state.parseSequence += 1;
  state.generateSequence += 1;
  await restoreTabState();
  renderSourceBadge();
}

// --- parsing ----------------------------------------------------------------

function detectParserId(url) {
  let parsed;
  try {
    parsed = new URL(url);
  } catch (_error) {
    return null;
  }

  const isLinkedIn = /(^|\.)linkedin\.com$/i.test(parsed.hostname);
  const isLocalFixture = ["localhost", "127.0.0.1"].includes(parsed.hostname);
  if (!isLinkedIn && !isLocalFixture) {
    return null;
  }

  if (parsed.pathname.startsWith("/messaging")) {
    return MESSAGING_PARSER_ID;
  }

  if (/^\/in\/[^/]+\/?$/.test(parsed.pathname)) {
    return PROFILE_PARSER_ID;
  }

  return null;
}

function normalizeParseResult(parseResult) {
  if (!parseResult || typeof parseResult !== "object") {
    return {
      status: "failed_to_parse_with_appropriate_methodology",
      error: "No parse result is available."
    };
  }

  const normalized = { ...parseResult };
  if (typeof normalized.output === "string") {
    try {
      normalized.output = JSON.parse(normalized.output);
    } catch (_error) {
      normalized.output = normalized.output.trim();
    }
  }

  return normalized;
}

async function parseActiveTab() {
  if (!Number.isInteger(state.tabId)) {
    return {
      status: "failed_to_parse_with_appropriate_methodology",
      error: "No active tab to parse."
    };
  }

  const parserId = detectParserId(state.tabUrl);
  if (!parserId) {
    return {
      status: "failed_to_find_appropriate_parsing_methodology",
      url: state.tabUrl
    };
  }

  await chrome.scripting.executeScript({
    target: { tabId: state.tabId },
    files: PARSER_FILES
  });

  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: state.tabId },
    func: async (parserIdOverride, retryDelayMs, retryTimeoutMs) => {
      if (!globalThis.ConverseParsing?.parseCurrentPageWithRetry) {
        return {
          status: "failed_to_parse_with_appropriate_methodology",
          error: "Parser runtime is unavailable on the current page."
        };
      }

      return globalThis.ConverseParsing.parseCurrentPageWithRetry(parserIdOverride, retryDelayMs, retryTimeoutMs);
    },
    args: [parserId, PARSE_RETRY_DELAY_MS, PARSE_RETRY_TIMEOUT_MS]
  });

  return normalizeParseResult(result);
}

function summarizeParseFailure(parseResult) {
  if (parseResult?.status === "failed_to_find_appropriate_parsing_methodology") {
    const label = getSourceSiteLabel(parseResult?.url || state.tabUrl);
    return label
      ? `No parser is configured for ${label} pages.`
      : "No parser is configured for this page.";
  }

  return normalizeErrorMessage(parseResult?.error, "The page structure did not match what the parser expected.");
}

// --- generation payload -------------------------------------------------------

function normalizeMessageTime(value) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (!text) {
    return null;
  }

  const compactMatch = text.match(/^(?:sun|mon|tue|wed|thu|fri|sat)(\d{1,2})([a-z]{3})(\d{2}|\d{4})\s+(\d{1,2})(?::(\d{2}))?\s*([ap])m$/i);
  if (compactMatch) {
    const monthIndex = {
      jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5,
      jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11
    }[compactMatch[2].toLowerCase()];

    if (monthIndex !== undefined) {
      const year = Number(compactMatch[3]);
      const fullYear = year < 100 ? 2000 + year : year;
      const meridiem = compactMatch[6].toLowerCase();
      let hour = Number(compactMatch[4]);
      const minute = Number(compactMatch[5] ?? 0);

      if (hour === 12) {
        hour = meridiem === "a" ? 0 : 12;
      } else if (meridiem === "p") {
        hour += 12;
      }

      return new Date(Date.UTC(fullYear, monthIndex, Number(compactMatch[1]), hour, minute, 0, 0)).toISOString();
    }
  }

  const parsed = new Date(text);
  return Number.isNaN(parsed.getTime()) ? text : parsed.toISOString();
}

function getMessagingOutput(parseResult) {
  if (parseResult?.status !== "success" || parseResult?.parserId !== MESSAGING_PARSER_ID) {
    return null;
  }

  const output = isPlainObject(parseResult.output) ? parseResult.output : null;
  return Array.isArray(output?.messages) ? output : null;
}

function buildGenerationPayload(output) {
  const recipientName = String(output.name ?? "").trim();
  if (!recipientName) {
    throw new Error("The conversation participant name could not be read from the page.");
  }

  return {
    recipientName,
    senderName: state.currentUser || undefined,
    model: modelSelect.value || undefined,
    additionalContext: contextInput.value.trim() || undefined,
    source: "linkedin",
    sourceUrl: state.tabUrl || undefined,
    messages: output.messages.map((message, index) => ({
      senderName: String(message.sender ?? "").trim(),
      body: String(message.message ?? "").trim(),
      sentTime: normalizeMessageTime(message.datetime),
      messageOrder: index
    }))
  };
}

// --- generation ---------------------------------------------------------------

async function runGeneration() {
  const sequence = ++state.generateSequence;
  state.generationMs = null;
  setView("results");
  setResultsState("loading");

  let parseResult;
  try {
    parseResult = await parseActiveTab();
  } catch (error) {
    if (sequence !== state.generateSequence) {
      return;
    }

    renderGenerationError("failed to parse the page", errorText(error));
    return;
  }

  if (sequence !== state.generateSequence) {
    return;
  }

  const output = getMessagingOutput(parseResult);
  if (!output) {
    renderGenerationError("failed to read the conversation", summarizeParseFailure(parseResult));
    return;
  }

  let payload;
  try {
    payload = buildGenerationPayload(output);
  } catch (error) {
    renderGenerationError("failed to read the conversation", errorText(error));
    return;
  }

  let generation;
  // Times the backend round trip only: page parsing is local, so a cold start
  // (container + Neon resume) shows up here and nowhere else.
  const startedAt = performance.now();
  try {
    generation = await ConverseApi.generateFollowup(payload);
  } catch (error) {
    if (sequence !== state.generateSequence) {
      return;
    }

    renderGenerationError("generation failed", errorText(error));
    return;
  }
  const elapsedMs = performance.now() - startedAt;

  if (sequence !== state.generateSequence) {
    return;
  }

  state.generationMs = elapsedMs;
  state.suggestion = String(generation?.suggestion ?? "").trim();
  state.originalSuggestion = state.suggestion;
  state.generationId = generation?.generationId ?? null;
  state.evidence = generation?.evidence ?? null;
  state.ingest = null;
  renderSuggestion();
  scheduleTabStateSave();
}

async function injectSuggestionIntoActiveTab(text) {
  await chrome.scripting.executeScript({
    target: { tabId: state.tabId },
    files: [SUGGESTION_INJECTION_FILE]
  });

  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: state.tabId },
    func: (suggestionText) => {
      if (!globalThis.ConverseSuggestionInjection?.injectSuggestion) {
        return {
          ok: false,
          error: "Suggestion injector is unavailable on the current page."
        };
      }

      return globalThis.ConverseSuggestionInjection.injectSuggestion(suggestionText);
    },
    args: [text]
  });

  if (!result?.ok) {
    throw new Error(result?.error || "Unable to inject the suggestion into the page.");
  }
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const temporaryInput = document.createElement("textarea");
  temporaryInput.value = text;
  document.body.append(temporaryInput);
  temporaryInput.select();
  document.execCommand("copy");
  temporaryInput.remove();
}

function flashButtonLabel(button, label, revertLabel) {
  button.textContent = label;
  window.setTimeout(() => {
    button.textContent = revertLabel;
  }, 1200);
}

// --- workbench ------------------------------------------------------------------

function resetWorkbenchDisplay() {
  messageList.replaceChildren();
  parseJsonBlock.hidden = true;
  parseJson.textContent = "";
  previewPanel.hidden = true;
  promptPreviewOutput.textContent = "";
  previewToggleButton.classList.remove("is-selected");
  saveProfileButton.disabled = true;
  saveExampleButton.disabled = true;
  previewToggleButton.disabled = true;
  setStatus(workbenchStatus, "ready");
}

function getDefaultCategory(message, index) {
  return index === 0 && isSelfSender(message?.sender) ? "intro" : "message";
}

function isMessageIncluded(selection) {
  return selection?.included !== false;
}

function getIncludedCount() {
  const output = getMessagingOutput(state.workbench.parse);
  if (!output) {
    return 0;
  }

  return output.messages.filter((_message, index) => isMessageIncluded(state.workbench.selections[index])).length;
}

function updateWorkbenchActions() {
  const parse = state.workbench.parse;
  const isMessaging = Boolean(getMessagingOutput(parse));
  const isProfile = parse?.status === "success" && parse?.parserId === PROFILE_PARSER_ID;

  saveProfileButton.disabled = !isProfile;
  saveExampleButton.disabled = !isMessaging || getIncludedCount() === 0;
  previewToggleButton.disabled = !isMessaging;
}

function createRatingControl(message, index, selection) {
  const labels = isSelfSender(message.sender) ? SELF_RATING_LABELS : OTHER_RATING_LABELS;

  const control = document.createElement("div");
  control.className = "message-control";

  const caption = document.createElement("span");
  caption.className = "control-caption";

  const stars = document.createElement("div");
  stars.className = "star-row";
  stars.setAttribute("role", "group");
  stars.setAttribute("aria-label", `rating for message ${index + 1}`);

  const starButtons = [];
  for (let rating = 1; rating <= 5; rating += 1) {
    const star = document.createElement("button");
    star.type = "button";
    star.className = "star-button";
    star.textContent = "★";
    star.title = labels[rating - 1];
    star.addEventListener("click", () => {
      selection.rating = rating;
      render();
    });
    starButtons.push(star);
    stars.append(star);
  }

  function render() {
    caption.textContent = labels[selection.rating - 1] ?? "neutral";
    starButtons.forEach((star, starIndex) => {
      star.classList.toggle("is-selected", starIndex < selection.rating);
    });
  }

  render();
  control.append(stars, caption);
  return control;
}

function createCategoryControl(index, selection) {
  const control = document.createElement("div");
  control.className = "message-control category-row";
  control.setAttribute("role", "group");
  control.setAttribute("aria-label", `category for message ${index + 1}`);

  const buttons = ["intro", "message"].map((category) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip-button";
    button.textContent = category;
    button.addEventListener("click", () => {
      selection.category = category;
      render();
    });
    control.append(button);
    return button;
  });

  function render() {
    buttons.forEach((button) => {
      button.classList.toggle("is-selected", button.textContent === selection.category);
    });
  }

  render();
  return control;
}

function createIncludeControl(row, index, selection) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "chip-button include-toggle";

  function render() {
    const included = isMessageIncluded(selection);
    button.textContent = included ? "included" : "ignored";
    button.classList.toggle("is-selected", included);
    row.classList.toggle("is-ignored", !included);
    button.setAttribute("aria-pressed", String(included));
    button.setAttribute("aria-label", `message ${index + 1} ${included ? "will" : "will not"} be saved`);
  }

  button.addEventListener("click", () => {
    selection.included = !isMessageIncluded(selection);
    render();
    updateWorkbenchActions();
  });

  render();
  return button;
}

function renderMessageItem(message, index) {
  const record = isPlainObject(message) ? message : { message: String(message ?? "") };
  const selection = {
    included: true,
    category: getDefaultCategory(record, index),
    rating: 3
  };
  state.workbench.selections[index] = selection;

  const row = document.createElement("article");
  row.className = "message-item";
  row.classList.toggle("is-self", isSelfSender(record.sender));

  const meta = document.createElement("div");
  meta.className = "message-meta";
  const sender = document.createElement("span");
  sender.className = "message-sender";
  sender.textContent = record.sender ?? "unknown sender";
  meta.append(sender);

  if (record.datetime) {
    const time = document.createElement("span");
    time.className = "message-time";
    time.textContent = record.datetime;
    meta.append(time);
  }

  const body = document.createElement("pre");
  body.className = "message-body";
  body.textContent = String(record.message ?? "").trim() || "(empty)";

  const controls = document.createElement("div");
  controls.className = "message-controls";
  controls.append(
    createIncludeControl(row, index, selection),
    createCategoryControl(index, selection),
    createRatingControl(record, index, selection)
  );

  row.append(meta, body, controls);
  return row;
}

function renderWorkbenchParse() {
  const parse = state.workbench.parse;
  messageList.replaceChildren();
  parseJsonBlock.hidden = true;
  parseJson.textContent = "";
  state.workbench.selections = [];

  if (!parse) {
    updateWorkbenchActions();
    return;
  }

  const output = getMessagingOutput(parse);
  if (output) {
    const header = document.createElement("p");
    header.className = "message-list-header";
    header.textContent = `${output.name ?? "unknown"} — ${output.messages.length} messages`;
    messageList.append(header);
    output.messages.forEach((message, index) => {
      messageList.append(renderMessageItem(message, index));
    });
    setStatus(workbenchStatus, "parsed conversation", "success");
  } else if (parse.status === "success") {
    parseJsonBlock.hidden = false;
    parseJson.textContent = JSON.stringify(parse, null, 2);
    setStatus(workbenchStatus, `parsed ${parse.parserId ?? "page"}`, "success");
  } else {
    parseJsonBlock.hidden = false;
    parseJson.textContent = JSON.stringify(parse, null, 2);
    setStatus(workbenchStatus, summarizeParseFailure(parse), "error");
  }

  updateWorkbenchActions();
}

async function refreshWorkbenchParse() {
  const sequence = ++state.parseSequence;
  setStatus(workbenchStatus, "parsing the active tab…");
  hidePromptPreview();

  let parseResult;
  try {
    parseResult = await parseActiveTab();
  } catch (error) {
    parseResult = {
      status: "failed_to_parse_with_appropriate_methodology",
      error: errorText(error)
    };
  }

  if (sequence !== state.parseSequence) {
    return;
  }

  state.workbench.parse = parseResult;
  renderWorkbenchParse();
}

function buildEvalExamplePayload() {
  const output = getMessagingOutput(state.workbench.parse);
  if (!output) {
    throw new Error("No parsed conversation is available to save.");
  }

  if (!state.currentUser) {
    throw new Error("Sign in before saving an eval example.");
  }

  const messages = output.messages.flatMap((message, index) => {
    const selection = state.workbench.selections[index] ?? {};
    if (!isMessageIncluded(selection)) {
      return [];
    }

    return [{
      message_order: index,
      sender_name: String(message.sender ?? "").trim(),
      sentTime: normalizeMessageTime(message.datetime),
      body: String(message.message ?? "").trim(),
      category: selection.category ?? getDefaultCategory(message, index),
      rating: Number(selection.rating ?? 3)
    }];
  });

  if (messages.length === 0) {
    throw new Error("Include at least one message before saving.");
  }

  const recipientName = inferRecipientName(output);

  return {
    saved_at: new Date().toISOString(),
    user_name: state.currentUser,
    recipient_name: recipientName,
    source: "linkedin",
    messages
  };
}

function inferRecipientName(output) {
  const userNameKey = normalizeName(state.currentUser);
  const senderCounts = new Map();

  output.messages.forEach((message, index) => {
    const senderName = String(message?.sender ?? "").trim();
    const senderKey = normalizeName(senderName);
    if (!senderName || !senderKey || senderKey === userNameKey) {
      return;
    }

    const entry = senderCounts.get(senderKey) ?? { count: 0, firstIndex: index, name: senderName };
    entry.count += 1;
    senderCounts.set(senderKey, entry);
  });

  const [bestSender] = Array.from(senderCounts.values()).sort((left, right) => (
    right.count !== left.count ? right.count - left.count : left.firstIndex - right.firstIndex
  ));

  if (bestSender) {
    return bestSender.name;
  }

  const participantName = String(output.name ?? "").trim();
  if (participantName && normalizeName(participantName) !== userNameKey) {
    return participantName;
  }

  throw new Error("Unable to infer the recipient name from this conversation.");
}

async function saveEvalExample() {
  let payload;
  try {
    payload = buildEvalExamplePayload();
  } catch (error) {
    setStatus(workbenchStatus, errorText(error), "error");
    return;
  }

  saveExampleButton.disabled = true;
  setStatus(workbenchStatus, "saving eval example…");

  try {
    await ConverseApi.saveEvalExample(payload);
    setStatus(workbenchStatus, `saved ${payload.messages.length} rated messages as an eval example`, "success");
  } catch (error) {
    setStatus(workbenchStatus, `save failed — ${errorText(error)}`, "error");
  } finally {
    updateWorkbenchActions();
  }
}

async function saveParsedProfile() {
  const parse = state.workbench.parse;
  if (parse?.status !== "success" || parse?.parserId !== PROFILE_PARSER_ID) {
    setStatus(workbenchStatus, "open a LinkedIn profile and re-parse first", "error");
    return;
  }

  const output = parse.output ?? parse;
  const label = [output?.first_name, output?.last_name].filter(Boolean).join(" ").trim() || parse.parserId;

  saveProfileButton.disabled = true;
  setStatus(workbenchStatus, "saving profile…");

  try {
    const response = await ConverseApi.saveParsedProfile({
      result: output,
      parserId: parse.parserId,
      label,
      sourceUrl: parse.url ?? state.tabUrl ?? null
    });
    const message = response?.status === "duplicate" ? "already saved (duplicate)" : `saved profile ${label}`;
    setStatus(workbenchStatus, message, "success");
  } catch (error) {
    setStatus(workbenchStatus, `save failed — ${errorText(error)}`, "error");
  } finally {
    updateWorkbenchActions();
  }
}

function hidePromptPreview() {
  state.workbench.previewVisible = false;
  previewPanel.hidden = true;
  previewToggleButton.classList.remove("is-selected");
}

async function togglePromptPreview() {
  if (state.workbench.previewVisible) {
    hidePromptPreview();
    return;
  }

  const output = getMessagingOutput(state.workbench.parse);
  if (!output) {
    setStatus(workbenchStatus, "parse a conversation first", "error");
    return;
  }

  let payload;
  try {
    payload = buildGenerationPayload(output);
  } catch (error) {
    setStatus(workbenchStatus, errorText(error), "error");
    return;
  }

  previewToggleButton.disabled = true;
  setStatus(workbenchStatus, "building prompt preview…");

  try {
    const preview = await ConverseApi.previewPrompt(payload);
    promptPreviewOutput.textContent = preview?.prompt ?? "";
    state.workbench.previewVisible = true;
    previewPanel.hidden = false;
    previewToggleButton.classList.add("is-selected");
    const ragNote = preview?.ragError ? ` (RAG unavailable: ${normalizeErrorMessage(preview.ragError)})` : "";
    setStatus(workbenchStatus, `prompt preview ready — ${preview?.promptVersion ?? "?"}${ragNote}`, preview?.ragError ? "error" : "success");
  } catch (error) {
    setStatus(workbenchStatus, `preview failed — ${errorText(error)}`, "error");
  } finally {
    previewToggleButton.disabled = false;
    updateWorkbenchActions();
  }
}

// --- login page -------------------------------------------------------------

async function openLoginPageTab() {
  const url = chrome.runtime.getURL("frontend/login.html");
  const tabs = await chrome.tabs.query({});
  const existingTab = tabs.find((tab) => typeof tab.url === "string" && tab.url.startsWith(url));
  const tab = Number.isInteger(existingTab?.id)
    ? await chrome.tabs.update(existingTab.id, { active: true, url })
    : await chrome.tabs.create({ active: true, url });

  if (typeof tab?.windowId === "number") {
    await chrome.windows.update(tab.windowId, { focused: true });
  }
}

// --- events -------------------------------------------------------------------

viewButtons.forEach((button) => {
  button.addEventListener("click", () => {
    openView(button.dataset.viewButton);
  });
});

settingsSaveButton.addEventListener("click", () => {
  saveSettings().catch((error) => setStatus(settingsStatus, error.message, "error"));
});

settingsTestButton.addEventListener("click", () => {
  testSettings();
});

loginOpenButton.addEventListener("click", () => {
  openLoginPageTab().catch((error) => {
    setStatus(composerStatus, errorText(error), "error");
  });
});

modelSelect.addEventListener("change", () => {
  chrome.storage.local.set({ [SELECTED_MODEL_STORAGE_KEY]: modelSelect.value }).catch(() => {});
});

contextInput.addEventListener("input", () => {
  scheduleTabStateSave();
});

generateButton.addEventListener("click", () => {
  runGeneration();
});

regenerateButton.addEventListener("click", () => {
  runGeneration();
});

backButton.addEventListener("click", () => {
  setView("composer");
  scheduleTabStateSave();
  contextInput.focus();
});

suggestionOutput.addEventListener("input", () => {
  state.suggestion = suggestionOutput.value;
  if (state.ingest) {
    // an edit after ingest starts a new draft round — allow re-ingesting
    state.ingest = null;
  }
  renderIngestState();
  pickButton.disabled = !state.suggestion.trim();
  copySuggestionButton.disabled = !state.suggestion.trim();
  autosizeSuggestionOutput();
  scheduleTabStateSave();
});

ingestButton.addEventListener("click", async () => {
  const finalDraft = suggestionOutput.value.trim();
  if (!finalDraft || !state.generationId) {
    return;
  }

  ingestButton.disabled = true;
  setStatus(resultsStatus, "ingesting…");

  try {
    const response = await ConverseApi.ingestFollowup(state.generationId, { finalDraft });
    state.ingest = {
      feedback: response?.userFeedback ?? "saved",
      similarity: typeof response?.originalFinalSimilarity === "number" ? response.originalFinalSimilarity : null,
      at: response?.ingestedAt ?? null
    };
    renderIngestState();
    scheduleTabStateSave();
  } catch (error) {
    setStatus(resultsStatus, `ingest failed — ${errorText(error)}`, "error");
    ingestButton.disabled = false;
  }
});

pickButton.addEventListener("click", async () => {
  if (!state.suggestion.trim()) {
    return;
  }

  try {
    await injectSuggestionIntoActiveTab(state.suggestion);
    flashButtonLabel(pickButton, "picked", "pick");
    window.close();
  } catch (error) {
    flashButtonLabel(pickButton, "failed", "pick");
    renderGenerationError("failed to insert the suggestion", errorText(error));
  }
});

copySuggestionButton.addEventListener("click", async () => {
  await copyText(suggestionOutput.value);
  flashButtonLabel(copySuggestionButton, "copied", "copy");
});

copyPromptButton.addEventListener("click", async () => {
  await copyText(promptPreviewOutput.textContent);
  flashButtonLabel(copyPromptButton, "copied", "copy");
});

copyParseJsonButton.addEventListener("click", async () => {
  await copyText(parseJson.textContent);
  flashButtonLabel(copyParseJsonButton, "copied", "copy");
});

refreshParseButton.addEventListener("click", () => {
  refreshWorkbenchParse();
});

refreshModelsButton.addEventListener("click", async () => {
  refreshModelsButton.disabled = true;
  const restore = refreshModelsButton.textContent;
  refreshModelsButton.textContent = "…";
  const ok = await loadModels({ refresh: true });
  refreshModelsButton.disabled = false;
  flashButtonLabel(refreshModelsButton, ok ? "refreshed" : "failed", restore);
});

saveExampleButton.addEventListener("click", () => {
  saveEvalExample();
});

saveProfileButton.addEventListener("click", () => {
  saveParsedProfile();
});

previewToggleButton.addEventListener("click", () => {
  togglePromptPreview();
});

chrome.tabs.onActivated.addListener(({ windowId }) => {
  if (windowId === state.windowId) {
    adoptActiveTab();
  }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (tabId !== state.tabId || !changeInfo.url) {
    return;
  }

  state.tabUrl = changeInfo.url;
  renderSourceBadge();
  updateWorkbenchActions();
});

chrome.storage.onChanged.addListener((changes, areaName) => {
  if (areaName === "local" && (changes[CURRENT_USER_STORAGE_KEY] || changes[CURRENT_USER_ID_STORAGE_KEY])) {
    renderCurrentUserBadge();
  }
});

window.addEventListener("pagehide", () => {
  saveTabState().catch(() => {});
});

window.addEventListener("load", async () => {
  const currentWindow = await chrome.windows.getCurrent();
  state.windowId = currentWindow.id;

  await pruneExpiredTabStates().catch(() => {});
  await renderCurrentUserBadge();
  await loadModels();
  await adoptActiveTab({ initial: true });
});
