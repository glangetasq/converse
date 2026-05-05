const DEFAULT_TONES = ["informal", "conversational"];
const WINDOW_WIDTH = 760;
const WINDOW_MIN_HEIGHT = 280;
const WINDOW_MARGIN = 80;
const RESUME_STORAGE_KEY = "savedResume";
const PARSE_RETRY_DELAY_MS = 250;
const PARSE_RETRY_TIMEOUT_MS = 3500;
const PARSER_FILES = [
  "content/parsing/runtime.js",
  "content/parsing/helpers.js",
  "content/parsing/parsers/linkedin-profile.js",
  "content/parsing/parsers/linkedin-messaging.js",
  "content/parsing/parsers/job-posting.js"
];

const composerView = document.getElementById("composer-view");
const resultsView = document.getElementById("results-view");
const generateButton = document.getElementById("generate-button");
const closeButton = document.getElementById("close-button");
const resultsCloseButton = document.getElementById("results-close-button");
const retryButton = document.getElementById("retry-button");
const regenerateButton = document.getElementById("regenerate-button");
const llmModalBackdrop = document.getElementById("llm-modal-backdrop");
const llmModal = document.getElementById("llm-modal");
const llmModalCloseButton = document.getElementById("llm-modal-close-button");
const llmModalOpenButtons = Array.from(document.querySelectorAll(".llm-modal-open-button"));
const uploadsModalBackdrop = document.getElementById("uploads-modal-backdrop");
const uploadsModal = document.getElementById("uploads-modal");
const uploadsModalCloseButton = document.getElementById("uploads-modal-close-button");
const uploadsModalOpenButtons = Array.from(document.querySelectorAll(".uploads-modal-open-button"));
const modeSelects = Array.from(document.querySelectorAll("[data-mode-select]"));
const debugModalBackdrop = document.getElementById("debug-modal-backdrop");
const debugModal = document.getElementById("debug-modal");
const debugModalCloseButton = document.getElementById("debug-modal-close-button");
const debugModalOpenButtons = Array.from(document.querySelectorAll(".debug-modal-open-button"));
const debugParseTab = document.getElementById("debug-parse-tab");
const debugPromptTab = document.getElementById("debug-prompt-tab");
const debugParsePanel = document.getElementById("debug-parse-panel");
const debugPromptPanel = document.getElementById("debug-prompt-panel");
const debugParseOutput = document.getElementById("debug-parse-output");
const debugPromptOutput = document.getElementById("debug-prompt-output");
const debugStatusOutput = document.getElementById("debug-status-output");
const configurationToggle = document.getElementById("configuration-toggle");
const configurationPanel = document.getElementById("configuration-panel");
const directionsToggle = document.getElementById("directions-toggle");
const directionsPanel = document.getElementById("directions-panel");
const instructionsInput = document.getElementById("instructions-input");
const contextInput = document.getElementById("context-input");
const llmProviderSelect = document.getElementById("llm-provider-select");
const llmBaseUrlInput = document.getElementById("llm-base-url-input");
const llmPathInput = document.getElementById("llm-path-input");
const llmModelSelect = document.getElementById("llm-model-select");
const llmSaveButton = document.getElementById("llm-save-button");
const llmStatusOutput = document.getElementById("llm-status-output");
const resumeFileInput = document.getElementById("resume-file-input");
const resumeUploadButton = document.getElementById("resume-upload-button");
const resumeClearButton = document.getElementById("resume-clear-button");
const resumeStatusOutput = document.getElementById("resume-status-output");
const languageGroup = document.getElementById("language-group");
const toneGroup = document.getElementById("tone-group");
const toneReset = document.getElementById("tone-reset");
const lengthUnitGroup = document.getElementById("length-unit-group");
const lengthValueGroup = document.getElementById("length-value-group");
const generationLoader = document.getElementById("generation-loader");
const generationErrorBanner = document.getElementById("generation-error-banner");
const generationErrorTitle = document.getElementById("generation-error-title");
const generationErrorDetail = document.getElementById("generation-error-detail");
const suggestionsPanel = document.getElementById("suggestions-panel");
const regenerateConfigurationToggle = document.getElementById("regenerate-configuration-toggle");
const regenerateConfigurationPanel = document.getElementById("regenerate-configuration-panel");
const regenerateSuggestionGroup = document.getElementById("regenerate-suggestion-group");
const regenerateInstructionsInput = document.getElementById("regenerate-instructions-input");
const copyButtons = Array.from(document.querySelectorAll(".copy-button"));
const pickButtons = Array.from(document.querySelectorAll(".pick-button"));
const suggestionOutputs = [
  document.getElementById("suggestion-1-output"),
  document.getElementById("suggestion-2-output"),
  document.getElementById("suggestion-3-output")
];
const suggestionOutputIds = new Set(
  suggestionOutputs
    .map((output) => output?.id)
    .filter(Boolean)
);
const regenerateSuggestionButtons = Array.from(
  regenerateSuggestionGroup?.querySelectorAll("[data-regenerate-suggestion-index]") ?? []
);
const promptFileCache = new Map();

const formState = {
  modeId: "auto",
  language: "auto",
  tones: [...DEFAULT_TONES],
  lengthUnit: "characters",
  lengthValue: "auto"
};
const regenerateFormState = {
  selectedSuggestionIndices: []
};

const urlParams = new URLSearchParams(window.location.search);
const sourceUrl = urlParams.get("sourceUrl") ?? "";
const sourceTabIdValue = urlParams.get("sourceTabId");
const sourceTabId = sourceTabIdValue === null ? Number.NaN : Number(sourceTabIdValue);
let lastLlmModalTrigger = null;
let lastUploadsModalTrigger = null;
let lastDebugModalTrigger = null;
let debugLoadSequence = 0;
let pendingResizeFrame = 0;
let savedResume = null;

async function parseSourceTab(modeId = formState.modeId) {
  if (!Number.isInteger(sourceTabId)) {
    return {
      status: "failed_to_parse_with_appropriate_methodology",
      error: "Source tab id is unavailable."
    };
  }

  await chrome.scripting.executeScript({
    target: { tabId: sourceTabId },
    files: PARSER_FILES
  });

  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: sourceTabId },
    func: async (parserIdOverride, retryDelayMs, retryTimeoutMs) => {
      const wait = (durationMs) => new Promise((resolve) => {
        globalThis.setTimeout(resolve, durationMs);
      });

      const isRecoverableLinkedInMessagingFailure = (parseResult) => {
        if (parseResult?.status !== "failed_to_parse_with_appropriate_methodology") {
          return false;
        }

        if (parseResult?.parserId !== "linkedin-messaging") {
          return false;
        }

        return /message list was not found|no linkedin messages were extracted/i.test(parseResult?.error ?? "");
      };

      const nudgePageLifecycle = () => {
        const events = [
          () => globalThis.dispatchEvent(new Event("focus")),
          () => globalThis.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: false })),
          () => globalThis.dispatchEvent(new Event("online")),
          () => document.dispatchEvent(new Event("visibilitychange"))
        ];

        for (const dispatchEvent of events) {
          try {
            dispatchEvent();
          } catch (_error) {
            // Best-effort only; parsing can continue without lifecycle nudges.
          }
        }
      };

      const parse = () => {
        if (parserIdOverride && globalThis.ConverseParsing.parseDocumentWithParserId) {
          return globalThis.ConverseParsing.parseDocumentWithParserId(
            parserIdOverride,
            globalThis.location?.href ?? "",
            document
          );
        }

        return globalThis.ConverseParsing.parseCurrentPage();
      };

      if (!globalThis.ConverseParsing?.parseCurrentPage) {
        return {
          status: "failed_to_parse_with_appropriate_methodology",
          error: "Parser runtime is unavailable on the current page."
        };
      }

      let result = parse();
      if (!isRecoverableLinkedInMessagingFailure(result)) {
        return result;
      }

      nudgePageLifecycle();

      const deadline = Date.now() + retryTimeoutMs;
      while (Date.now() < deadline) {
        await wait(retryDelayMs);
        result = parse();

        if (!isRecoverableLinkedInMessagingFailure(result)) {
          return result;
        }

        nudgePageLifecycle();
      }

      return result;
    },
    args: [getModeConfig(modeId)?.parserId ?? null, PARSE_RETRY_DELAY_MS, PARSE_RETRY_TIMEOUT_MS]
  });

  return result;
}

function getPromptingConfig() {
  const config = globalThis.ConversePrompting;
  if (!config?.globalPromptPath) {
    throw new Error("Prompt configuration is unavailable.");
  }

  return config;
}

function getModeConfig(modeId = formState.modeId) {
  const config = getPromptingConfig();
  const fallbackMode = config.modes?.auto;
  return config.modes?.[modeId] ?? fallbackMode ?? null;
}

function getResumeTools() {
  const tools = globalThis.ConverseResume;
  if (!tools?.extractResumeTextFromDocx) {
    throw new Error("Resume upload tooling is unavailable.");
  }

  return tools;
}

function syncModeSelects() {
  modeSelects.forEach((select) => {
    select.value = formState.modeId;
  });
}

function populateModeOptions() {
  const config = getPromptingConfig();
  const modes = Object.values(config.modes ?? {});

  modeSelects.forEach((select) => {
    select.replaceChildren();

    modes.forEach((mode) => {
      const option = document.createElement("option");
      option.value = mode.id;
      option.textContent = mode.label;
      select.append(option);
    });
  });

  syncModeSelects();
}

async function loadPromptSnippet(path) {
  if (!path) {
    return "";
  }

  const cached = promptFileCache.get(path);
  if (cached) {
    return cached;
  }

  const response = await fetch(chrome.runtime.getURL(path));
  if (!response.ok) {
    throw new Error(`Unable to load prompt snippet at ${path}.`);
  }

  const text = (await response.text()).trim();
  promptFileCache.set(path, text);
  return text;
}

function normalizeResumeRecord(value) {
  if (!value || typeof value !== "object") {
    return null;
  }

  const text = typeof value.text === "string" ? value.text.trim() : "";
  if (!text) {
    return null;
  }

  return {
    fileName: typeof value.fileName === "string" && value.fileName.trim()
      ? value.fileName.trim()
      : "resume.docx",
    uploadedAt: typeof value.uploadedAt === "string" && value.uploadedAt.trim()
      ? value.uploadedAt.trim()
      : new Date(0).toISOString(),
    text
  };
}

function formatResumeTimestamp(isoTimestamp) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short"
    }).format(new Date(isoTimestamp));
  } catch (_error) {
    return isoTimestamp;
  }
}

function setResumeStatus(message, tone = "muted") {
  if (!resumeStatusOutput) {
    return;
  }

  resumeStatusOutput.textContent = message;
  resumeStatusOutput.classList.toggle("is-success", tone === "success");
  resumeStatusOutput.classList.toggle("is-error", tone === "error");
}

function renderResumeState() {
  if (!savedResume) {
    if (resumeUploadButton) {
      resumeUploadButton.textContent = "upload .docx";
    }

    if (resumeClearButton) {
      resumeClearButton.disabled = true;
    }

    setResumeStatus(
      "no resume uploaded yet. cover-letter mode will rely only on page context and your manual instructions."
    );
    return;
  }

  if (resumeUploadButton) {
    resumeUploadButton.textContent = "replace .docx";
  }

  if (resumeClearButton) {
    resumeClearButton.disabled = false;
  }

  setResumeStatus(
    `${savedResume.fileName} saved on ${formatResumeTimestamp(savedResume.uploadedAt)}. `
      + `${savedResume.text.length.toLocaleString()} characters will be added automatically in cover-letter mode.`,
    "success"
  );
}

async function loadSavedResume() {
  const result = await chrome.storage.local.get(RESUME_STORAGE_KEY);
  savedResume = normalizeResumeRecord(result?.[RESUME_STORAGE_KEY]);
  renderResumeState();
}

async function persistSavedResume(nextResume) {
  savedResume = normalizeResumeRecord(nextResume);

  if (!savedResume) {
    await chrome.storage.local.remove(RESUME_STORAGE_KEY);
  } else {
    await chrome.storage.local.set({
      [RESUME_STORAGE_KEY]: savedResume
    });
  }

  renderResumeState();
}

async function saveResumeFile(file) {
  if (!(file instanceof File)) {
    throw new Error("Choose a .docx resume file first.");
  }

  setResumeStatus(`Reading ${file.name}…`);

  const text = await getResumeTools().extractResumeTextFromDocx(file);
  await persistSavedResume({
    fileName: file.name,
    uploadedAt: new Date().toISOString(),
    text
  });
}

function getResumePromptPayload(snapshot) {
  if (snapshot.modeId !== "cover-letter" || !savedResume?.text) {
    return null;
  }

  return {
    file_name: savedResume.fileName,
    uploaded_at: savedResume.uploadedAt,
    text: savedResume.text
  };
}

function buildLengthConstraint(snapshot) {
  const { length } = snapshot;
  if (length.value === "auto") {
    return null;
  }

  const numericValue = Number(length.value);
  if (!Number.isFinite(numericValue) || numericValue <= 0) {
    return null;
  }

  const lowerBound = Math.max(1, Math.ceil(numericValue * 0.9));
  const unit = length.unit;

  return [
    "This block is super important.",
    `Requested length: ${numericValue} ${unit}.`,
    `Required target range for each suggestion: ${lowerBound}-${numericValue} ${unit}.`,
    `Hard maximum for each suggestion: ${numericValue} ${unit}.`,
    "The requested length applies to each suggestion independently.",
    "Do not divide the requested length across the batch of suggestions.",
    "Do not return a short blurb, opener, summary, or compressed note when the requested length clearly calls for a full draft.",
    "If regenerate_config gives a different length instruction, follow regenerate_config instead."
  ].join("\n");
}

function getPromptUserInput(snapshot) {
  const instructions = snapshot.instructions.trim();
  const context = snapshot.contextEnabled ? snapshot.context.trim() : "";
  const length = snapshot.length.value === "auto"
    ? null
    : `${snapshot.length.value} ${snapshot.length.unit}`;

  return {
    mode: snapshot.modeId,
    language: snapshot.language,
    tone: snapshot.tones,
    length,
    additional_instructions: instructions || null,
    additional_context: context || null
  };
}

function buildRegenerateConfig() {
  const isEnabled = regenerateConfigurationToggle?.getAttribute("aria-expanded") === "true";
  if (!isEnabled) {
    return null;
  }

  const likedSuggestions = regenerateFormState.selectedSuggestionIndices
    .map((index) => suggestionOutputs[index]?.value.trim() ?? "")
    .filter((text) => Boolean(text));
  const additionalInstructions = regenerateInstructionsInput?.value.trim() ?? "";

  if (likedSuggestions.length === 0 && !additionalInstructions) {
    return null;
  }

  return {
    liked_suggestions: likedSuggestions,
    additional_instructions: additionalInstructions
  };
}

function getPromptParsingResult(parseResult) {
  if (parseResult?.status !== "success") {
    throw new Error(parseResult?.error || "Unable to generate a prompt without a successful parser result.");
  }

  if (typeof parseResult.output === "string") {
    return parseResult.output.trim();
  }

  return JSON.stringify(parseResult.output ?? {}, null, 2);
}

async function buildPrompt(snapshot, parseResult, regenerateConfig = null) {
  const config = getPromptingConfig();
  const modeConfig = getModeConfig(snapshot.modeId);
  const parserId = parseResult?.parserId;
  const parserPromptPath = modeConfig?.promptPath || config.parserPromptPaths?.[parserId];
  const resumePayload = getResumePromptPayload(snapshot);
  const lengthConstraint = buildLengthConstraint(snapshot);

  if (!parserPromptPath) {
    throw new Error(`No prompt snippet is configured for parser "${parserId ?? "unknown"}".`);
  }

  const [globalPrompt, parserPrompt] = await Promise.all([
    loadPromptSnippet(config.globalPromptPath),
    loadPromptSnippet(parserPromptPath)
  ]);

  const promptSections = [
    globalPrompt,
    "",
    parserPrompt,
    "",
    "<user_input>",
    JSON.stringify(getPromptUserInput(snapshot), null, 2),
    "</user_input>",
    "",
    "<parsing_result>",
    getPromptParsingResult(parseResult),
    "</parsing_result>"
  ];

  if (resumePayload) {
    promptSections.push(
      "",
      "<resume>",
      JSON.stringify(resumePayload, null, 2),
      "</resume>"
    );
  }

  if (lengthConstraint) {
    promptSections.push(
      "",
      "<length_constraint>",
      lengthConstraint,
      "</length_constraint>"
    );
  }

  if (regenerateConfig) {
    promptSections.push(
      "",
      "<regenerate_config>",
      JSON.stringify(regenerateConfig, null, 2),
      "</regenerate_config>"
    );
  }

  return promptSections.join("\n");
}

function normalizeDebugParseResult(parseResult) {
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

function formatDebugParseResult(parseResult) {
  return JSON.stringify(normalizeDebugParseResult(parseResult), null, 2);
}

function getLlmConfig() {
  const config = globalThis.ConverseLlmConfig;
  if (!config) {
    throw new Error("LLM configuration is unavailable.");
  }

  return config;
}

function setLlmStatus(message, tone = "muted") {
  if (!llmStatusOutput) {
    return;
  }

  llmStatusOutput.textContent = message;
  llmStatusOutput.classList.toggle("is-success", tone === "success");
  llmStatusOutput.classList.toggle("is-error", tone === "error");
}

function setDebugStatus(message, tone = "muted") {
  if (!debugStatusOutput) {
    return;
  }

  debugStatusOutput.textContent = message;
  debugStatusOutput.classList.toggle("is-success", tone === "success");
  debugStatusOutput.classList.toggle("is-error", tone === "error");
}

function getLlmSettingsFromInputs() {
  return getLlmConfig().normalizeSettings({
    provider: llmProviderSelect?.value,
    baseUrl: llmBaseUrlInput?.value,
    path: llmPathInput?.value,
    model: llmModelSelect?.value
  });
}

function populateModelOptions() {
  if (!llmModelSelect) {
    return;
  }

  llmModelSelect.replaceChildren();

  getLlmConfig().MODEL_OPTIONS.forEach((option) => {
    const element = document.createElement("option");
    element.value = option.value;
    element.textContent = option.label;
    llmModelSelect.append(element);
  });
}

function ensureModelOption(value) {
  if (!llmModelSelect || !value) {
    return;
  }

  const existingOption = Array.from(llmModelSelect.options).find((option) => option.value === value);
  if (existingOption) {
    return;
  }

  const element = document.createElement("option");
  element.value = value;
  element.textContent = `${value} (custom)`;
  llmModelSelect.append(element);
}

function applyLlmSettings(settings) {
  if (llmProviderSelect) {
    llmProviderSelect.value = settings.provider;
  }

  if (llmBaseUrlInput) {
    llmBaseUrlInput.value = settings.baseUrl;
  }

  if (llmPathInput) {
    llmPathInput.value = settings.path;
  }

  if (llmModelSelect) {
    ensureModelOption(settings.model);
    llmModelSelect.value = settings.model;
  }
}

function getMessageError(response, fallbackMessage) {
  if (response?.ok) {
    return null;
  }

  return response?.error || fallbackMessage;
}

async function sendRuntimeMessage(message) {
  const response = await chrome.runtime.sendMessage(message);
  const errorMessage = getMessageError(response, "The background service returned an unexpected error.");
  if (errorMessage) {
    throw new Error(errorMessage);
  }

  return response;
}

async function requestRelayPermission(baseUrl) {
  const originPattern = getLlmConfig().getOriginPattern(baseUrl);
  const alreadyGranted = await chrome.permissions.contains({
    origins: [originPattern]
  });

  if (alreadyGranted) {
    return true;
  }

  return chrome.permissions.request({
    origins: [originPattern]
  });
}

async function loadLlmSettings() {
  const response = await sendRuntimeMessage({ type: "converse:get-llm-settings" });
  const settings = getLlmConfig().normalizeSettings(response.settings);
  applyLlmSettings(settings);
  setLlmStatus("LLM connection settings loaded.");
}

async function saveLlmSettings() {
  const settings = getLlmSettingsFromInputs();
  setLlmStatus("Requesting permission for the relay URL...");

  const granted = await requestRelayPermission(settings.baseUrl);
  if (!granted) {
    throw new Error(`Permission was not granted for ${settings.baseUrl}.`);
  }

  const response = await sendRuntimeMessage({
    type: "converse:save-llm-settings",
    settings
  });

  applyLlmSettings(response.settings);
  setLlmStatus(`Saved. Requests will be sent to ${response.settings.baseUrl}.`, "success");
}

async function requestSuggestions(promptText) {
  const response = await sendRuntimeMessage({
    type: "converse:generate-suggestions",
    request: {
      promptText,
      suggestionCount: suggestionOutputs.length
    }
  });

  return response.result;
}

function updateSingleSelect(groupElement, selectedValue) {
  groupElement?.querySelectorAll("[data-value]").forEach((button) => {
    button.classList.toggle("is-selected", button.dataset.value === selectedValue);
  });
}

function updateToneSelection() {
  toneGroup?.querySelectorAll("[data-value]").forEach((button) => {
    button.classList.toggle("is-selected", formState.tones.includes(button.dataset.value));
  });
}

function setPanelExpanded(toggleElement, panelElement, isExpanded) {
  toggleElement?.setAttribute("aria-expanded", String(isExpanded));
  if (panelElement) {
    panelElement.hidden = !isExpanded;
  }
  scheduleWindowResize();
}

function getFormState() {
  return {
    modeId: formState.modeId,
    language: formState.language,
    tones: [...formState.tones],
    length: {
      unit: formState.lengthUnit,
      value: formState.lengthValue === "auto" ? "auto" : Number(formState.lengthValue)
    },
    instructions: instructionsInput?.value ?? "",
    contextEnabled: directionsToggle?.getAttribute("aria-expanded") === "true",
    context: contextInput?.value ?? ""
  };
}

function updateRegenerateSuggestionSelection() {
  regenerateSuggestionButtons.forEach((button) => {
    const index = Number(button.dataset.regenerateSuggestionIndex);
    button.classList.toggle("is-selected", regenerateFormState.selectedSuggestionIndices.includes(index));
  });
}

function resetRegenerateConfiguration() {
  regenerateFormState.selectedSuggestionIndices = [];
  updateRegenerateSuggestionSelection();

  if (regenerateInstructionsInput) {
    regenerateInstructionsInput.value = "";
  }

  setPanelExpanded(regenerateConfigurationToggle, regenerateConfigurationPanel, false);
}

function getActiveRegenerateConfig() {
  const showingResults = Boolean(resultsView && !resultsView.hidden);
  return showingResults ? buildRegenerateConfig() : null;
}

function resizeWindowToContent() {
  const doc = document.documentElement;
  const targetHeight = Math.min(
    Math.max(
      Math.max(document.body.scrollHeight, doc.scrollHeight) + (window.outerHeight - window.innerHeight),
      WINDOW_MIN_HEIGHT
    ),
    window.screen.availHeight - WINDOW_MARGIN
  );
  window.resizeTo(WINDOW_WIDTH, targetHeight);
}

function scheduleWindowResize() {
  if (pendingResizeFrame) {
    window.cancelAnimationFrame(pendingResizeFrame);
  }

  pendingResizeFrame = window.requestAnimationFrame(() => {
    pendingResizeFrame = window.requestAnimationFrame(() => {
      pendingResizeFrame = 0;
      resizeWindowToContent();
    });
  });
}

function isLlmModalOpen() {
  return Boolean(llmModalBackdrop && !llmModalBackdrop.hidden);
}

function isUploadsModalOpen() {
  return Boolean(uploadsModalBackdrop && !uploadsModalBackdrop.hidden);
}

function isDebugModalOpen() {
  return Boolean(debugModalBackdrop && !debugModalBackdrop.hidden);
}

function openLlmModal(triggerButton = null) {
  if (!llmModalBackdrop) {
    return;
  }

  lastLlmModalTrigger = triggerButton instanceof HTMLElement ? triggerButton : document.activeElement;
  llmModalBackdrop.hidden = false;
  requestAnimationFrame(() => {
    llmProviderSelect?.focus();
  });
}

function openUploadsModal(triggerButton = null) {
  if (!uploadsModalBackdrop) {
    return;
  }

  lastUploadsModalTrigger = triggerButton instanceof HTMLElement ? triggerButton : document.activeElement;
  uploadsModalBackdrop.hidden = false;
  requestAnimationFrame(() => {
    resumeUploadButton?.focus();
  });
}

function setDebugTab(tabName) {
  const showingParse = tabName !== "prompt";

  debugParseTab?.classList.toggle("is-selected", showingParse);
  debugPromptTab?.classList.toggle("is-selected", !showingParse);
  debugParseTab?.setAttribute("aria-selected", String(showingParse));
  debugPromptTab?.setAttribute("aria-selected", String(!showingParse));

  if (debugParsePanel) {
    debugParsePanel.hidden = !showingParse;
  }

  if (debugPromptPanel) {
    debugPromptPanel.hidden = showingParse;
  }
}

function setDebugLoadingState() {
  if (debugParseOutput) {
    debugParseOutput.value = "Parsing the active page...";
  }

  if (debugPromptOutput) {
    debugPromptOutput.value = "Building prompt preview...";
  }

  setDebugStatus("Inspecting the active tab...");
  updateSuggestionActionStates();
}

async function refreshDebugModalContent() {
  const currentSequence = ++debugLoadSequence;
  const snapshot = getFormState();

  setDebugLoadingState();

  let parseResult;
  try {
    parseResult = await parseSourceTab(snapshot.modeId);
  } catch (error) {
    if (currentSequence !== debugLoadSequence) {
      return;
    }

    const message = normalizeErrorMessage(error instanceof Error ? error.message : String(error));

    if (debugParseOutput) {
      debugParseOutput.value = JSON.stringify({
        status: "failed_to_parse_with_appropriate_methodology",
        error: message
      }, null, 2);
    }

    if (debugPromptOutput) {
      debugPromptOutput.value = `Prompt unavailable.\n\n${message}`;
    }

    setDebugStatus("Unable to inspect the active tab.", "error");
    updateSuggestionActionStates();
    return;
  }

  if (currentSequence !== debugLoadSequence) {
    return;
  }

  if (debugParseOutput) {
    debugParseOutput.value = formatDebugParseResult(parseResult);
  }

  if (parseResult?.status !== "success") {
    if (debugPromptOutput) {
      debugPromptOutput.value = `Prompt unavailable because parsing did not succeed.\n\n${normalizeErrorMessage(parseResult?.error || summarizeParserUrl(parseResult?.url || sourceUrl))}`;
    }

    setDebugStatus("Parse result loaded, but prompt generation is unavailable.", "error");
    updateSuggestionActionStates();
    return;
  }

  try {
    const promptText = await buildPrompt(snapshot, parseResult, getActiveRegenerateConfig());
    if (currentSequence !== debugLoadSequence) {
      return;
    }

    if (debugPromptOutput) {
      debugPromptOutput.value = promptText;
    }

    setDebugStatus("Live parse result and prompt preview loaded.", "success");
    updateSuggestionActionStates();
  } catch (error) {
    if (currentSequence !== debugLoadSequence) {
      return;
    }

    if (debugPromptOutput) {
      debugPromptOutput.value = `Unable to build prompt.\n\n${normalizeErrorMessage(error instanceof Error ? error.message : String(error))}`;
    }

    setDebugStatus("Parse result loaded, but prompt preview failed to build.", "error");
    updateSuggestionActionStates();
  }
}

function openDebugModal(triggerButton = null) {
  if (!debugModalBackdrop) {
    return;
  }

  lastDebugModalTrigger = triggerButton instanceof HTMLElement ? triggerButton : document.activeElement;
  setDebugTab("parse");
  debugModalBackdrop.hidden = false;
  setDebugLoadingState();
  refreshDebugModalContent();

  requestAnimationFrame(() => {
    debugParseTab?.focus();
  });
}

function closeLlmModal() {
  if (!llmModalBackdrop || llmModalBackdrop.hidden) {
    return;
  }

  llmModalBackdrop.hidden = true;

  if (lastLlmModalTrigger instanceof HTMLElement) {
    lastLlmModalTrigger.focus();
  }
}

function closeUploadsModal() {
  if (!uploadsModalBackdrop || uploadsModalBackdrop.hidden) {
    return;
  }

  uploadsModalBackdrop.hidden = true;

  if (lastUploadsModalTrigger instanceof HTMLElement) {
    lastUploadsModalTrigger.focus();
  }
}

function closeDebugModal() {
  if (!debugModalBackdrop || debugModalBackdrop.hidden) {
    return;
  }

  debugModalBackdrop.hidden = true;
  debugLoadSequence += 1;

  if (lastDebugModalTrigger instanceof HTMLElement) {
    lastDebugModalTrigger.focus();
  }
}

function setActiveView(activeView) {
  const showingComposer = activeView === "composer";
  const showingResults = activeView === "results";

  composerView.hidden = !showingComposer;
  resultsView.hidden = !showingResults;
  composerView.classList.toggle("view-active", showingComposer);
  resultsView.classList.toggle("view-active", showingResults);
  scheduleWindowResize();
}

function setResultsState(state) {
  if (generationLoader) {
    generationLoader.hidden = state !== "loading";
  }

  if (generationErrorBanner) {
    generationErrorBanner.hidden = state !== "error";
  }

  if (suggestionsPanel) {
    suggestionsPanel.hidden = state !== "suggestions";
  }

  scheduleWindowResize();
}

function resetSuggestionOutputs() {
  suggestionOutputs.forEach((output) => {
    output.value = "";
  });
}

function resetSuggestionActionFeedback() {
  copyButtons.forEach((button) => {
    button.classList.remove("is-copied");
  });

  pickButtons.forEach((button) => {
    resetPickButtonState(button);
  });
}

function getSuggestionHeightBounds(output) {
  const computedStyle = window.getComputedStyle(output);
  const lineHeight = Number.parseFloat(computedStyle.lineHeight) || 24;
  const paddingTop = Number.parseFloat(computedStyle.paddingTop) || 0;
  const paddingBottom = Number.parseFloat(computedStyle.paddingBottom) || 0;
  const borderTop = Number.parseFloat(computedStyle.borderTopWidth) || 0;
  const borderBottom = Number.parseFloat(computedStyle.borderBottomWidth) || 0;
  const verticalChrome = paddingTop + paddingBottom + borderTop + borderBottom;

  return {
    minHeight: lineHeight * 2 + verticalChrome,
    maxHeight: lineHeight * 5 + verticalChrome
  };
}

function resizeSuggestionOutput(output) {
  if (!(output instanceof HTMLTextAreaElement)) {
    return;
  }

  const { minHeight, maxHeight } = getSuggestionHeightBounds(output);
  output.style.height = `${minHeight}px`;
  output.style.overflowY = "hidden";

  const targetHeight = Math.min(Math.max(output.scrollHeight, minHeight), maxHeight);
  output.style.height = `${targetHeight}px`;
  output.style.overflowY = output.scrollHeight > maxHeight ? "auto" : "hidden";
}

function resizeSuggestionOutputs() {
  suggestionOutputs.forEach((output) => {
    resizeSuggestionOutput(output);
  });
}

function renderLoadingState() {
  resetSuggestionActionFeedback();
  resetSuggestionOutputs();
  setResultsState("loading");
  updateSuggestionActionStates();
}

function renderSuggestions(suggestions, { preserveRegenerateConfiguration = false } = {}) {
  resetSuggestionActionFeedback();
  suggestionOutputs.forEach((output, index) => {
    output.value = suggestions[index] ?? "";
  });
  if (!preserveRegenerateConfiguration) {
    resetRegenerateConfiguration();
  }
  setResultsState("suggestions");
  window.requestAnimationFrame(() => {
    resizeSuggestionOutputs();
    scheduleWindowResize();
    updateSuggestionActionStates();
  });
}

function normalizeErrorMessage(value, fallback = "Something went wrong.") {
  if (typeof value !== "string") {
    return fallback;
  }

  const normalized = value.replace(/\s+/g, " ").trim();
  return normalized || fallback;
}

function stripKnownErrorPrefix(message, prefixes) {
  for (const prefix of prefixes) {
    if (message.startsWith(prefix)) {
      return message.slice(prefix.length).trim();
    }
  }

  return message;
}

function summarizeParserUrl(url) {
  if (formState.modeId !== "auto") {
    return "The selected mode could not parse enough useful content from this page.";
  }

  if (!url) {
    return "No parser is configured for this page.";
  }

  try {
    const parsed = new URL(url);
    return `No parser is configured for ${parsed.hostname}${parsed.pathname}.`;
  } catch (error) {
    return `No parser is configured for ${url}.`;
  }
}

function createGenerationIssue(title, detail) {
  return {
    title,
    detail: normalizeErrorMessage(detail)
  };
}

function summarizeDomParseReason(message) {
  if (/job description text/i.test(message) || /job posting/i.test(message)) {
    return "The job page did not expose enough readable description content.";
  }

  if (/message list was not found/i.test(message)) {
    return "The conversation thread was not visible on the page.";
  }

  if (/participant name/i.test(message) || /conversation participant/i.test(message)) {
    return "The conversation header was missing from the page.";
  }

  if (/no .*messages were extracted/i.test(message)) {
    return "No messages could be read from the current thread.";
  }

  if (/parser runtime is unavailable/i.test(message)) {
    return "The page parser could not start on this tab.";
  }

  return stripKnownErrorPrefix(message, ["LinkedIn messaging "]);
}

function classifyParseFailure(parseResult) {
  if (parseResult?.status === "failed_to_find_appropriate_parsing_methodology") {
    return createGenerationIssue(
      "failed to find parser for URL",
      summarizeParserUrl(parseResult?.url || sourceUrl)
    );
  }

  return createGenerationIssue(
    "failed to parse the DOM",
    summarizeDomParseReason(
      normalizeErrorMessage(parseResult?.error, "The page structure did not match what the parser expected.")
    )
  );
}

function classifyBuildPromptFailure(error) {
  const message = normalizeErrorMessage(error instanceof Error ? error.message : String(error));

  if (/unable to load prompt snippet/i.test(message)) {
    return createGenerationIssue(
      "failed to build prompt",
      "A prompt template file could not be loaded."
    );
  }

  if (/prompt configuration is unavailable/i.test(message)) {
    return createGenerationIssue(
      "failed to build prompt",
      "Prompt configuration is missing from the extension."
    );
  }

  return createGenerationIssue(
    "failed to build prompt",
    stripKnownErrorPrefix(message, [
      "No prompt snippet is configured for parser ",
      "Prompt configuration is unavailable.",
      "Unable to generate a prompt without a successful parser result."
    ])
  );
}

function classifySuggestionFailure(error) {
  const message = normalizeErrorMessage(error instanceof Error ? error.message : String(error));

  if (/permission to contact/i.test(message)) {
    return createGenerationIssue(
      "failed to reach relay",
      "The configured relay URL has not been approved yet in the extension."
    );
  }

  if (/relay request failed:/i.test(message) || /failed to fetch/i.test(message)) {
    return createGenerationIssue(
      "failed to reach relay",
      stripKnownErrorPrefix(message, ["Relay request failed:"])
    );
  }

  if (/llm api timeout:/i.test(message) || /\b504\b/.test(message) || /\btimed out\b/i.test(message) || /\btimeout\b/i.test(message)) {
    return createGenerationIssue(
      "failed to hear back from LLM API",
      stripKnownErrorPrefix(message, ["LLM API timeout:", "LLM request failed:"])
    );
  }

  if (/llm api request failed:/i.test(message) || /\b502\b/.test(message) || /\b503\b/.test(message) || /bad gateway/i.test(message) || /service unavailable/i.test(message)) {
    return createGenerationIssue(
      "failed to reach LLM API",
      stripKnownErrorPrefix(message, ["LLM API request failed:", "LLM request failed:"])
    );
  }

  if (/provider returned an empty response|not valid json|did not include assistant text|did not include the expected suggestions array/i.test(message)) {
    return createGenerationIssue(
      "failed to hear back from LLM API",
      "The model replied in an unexpected format."
    );
  }

  return createGenerationIssue(
    "failed to hear back from LLM API",
    stripKnownErrorPrefix(message, ["LLM request failed:"])
  );
}

function renderGenerationError(issue) {
  resetSuggestionActionFeedback();
  resetSuggestionOutputs();

  if (generationErrorTitle) {
    generationErrorTitle.textContent = issue.title;
  }

  if (generationErrorDetail) {
    generationErrorDetail.textContent = issue.detail;
  }

  setResultsState("error");
  updateSuggestionActionStates();
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

function resetCopyButtonState(button) {
  button.classList.remove("is-copied");
}

function isUsableSuggestionText(text) {
  return Boolean(text && text.trim());
}

function modeSupportsPicking(modeId = formState.modeId) {
  return modeId === "auto";
}

function updateSuggestionActionStates() {
  const suggestionsVisible = Boolean(suggestionsPanel && !suggestionsPanel.hidden);
  const picksEnabled = modeSupportsPicking();

  pickButtons.forEach((button) => {
    const targetId = button.dataset.pickTarget;
    const target = targetId ? document.getElementById(targetId) : null;
    button.disabled = !picksEnabled || !suggestionsVisible || !isUsableSuggestionText(target?.value ?? "");
  });

  copyButtons.forEach((button) => {
    const targetId = button.dataset.copyTarget;
    const target = targetId ? document.getElementById(targetId) : null;
    const isSuggestionCopy = suggestionOutputIds.has(targetId);
    button.disabled = isSuggestionCopy
      ? !suggestionsVisible || !isUsableSuggestionText(target?.value ?? "")
      : !isUsableSuggestionText(target?.value ?? "");
  });

  regenerateSuggestionButtons.forEach((button) => {
    const index = Number(button.dataset.regenerateSuggestionIndex);
    const target = suggestionOutputs[index];
    button.disabled = !suggestionsVisible || !isUsableSuggestionText(target?.value ?? "");
  });
}

function resetPickButtonState(button) {
  button.classList.remove("is-picked");
  button.textContent = "pick";
}

async function injectSuggestionIntoSourceTab(text) {
  if (!Number.isInteger(sourceTabId)) {
    throw new Error("Source tab id is unavailable.");
  }

  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: sourceTabId },
    func: (suggestionText) => {
      function isVisible(element) {
        if (!(element instanceof HTMLElement)) {
          return false;
        }

        const style = window.getComputedStyle(element);
        if (style.display === "none" || style.visibility === "hidden") {
          return false;
        }

        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
      }

      function isEligibleInput(element) {
        if (!(element instanceof HTMLElement) || !isVisible(element)) {
          return false;
        }

        if (element instanceof HTMLTextAreaElement) {
          return !element.disabled && !element.readOnly;
        }

        if (element instanceof HTMLInputElement) {
          return !element.disabled && !element.readOnly && (!element.type || element.type === "text");
        }

        return element.isContentEditable;
      }

      function setInputValue(element, value) {
        const prototype = element instanceof HTMLTextAreaElement
          ? HTMLTextAreaElement.prototype
          : HTMLInputElement.prototype;
        const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");

        if (descriptor?.set) {
          descriptor.set.call(element, value);
          return;
        }

        element.value = value;
      }

      function setContentEditableValue(element, value) {
        element.focus();

        const selection = window.getSelection();
        if (selection) {
          const range = document.createRange();
          range.selectNodeContents(element);
          selection.removeAllRanges();
          selection.addRange(range);
        }

        let inserted = false;

        if (typeof document.execCommand === "function") {
          try {
            document.execCommand("selectAll", false, null);
            inserted = document.execCommand("insertText", false, value);
          } catch (error) {
            inserted = false;
          }
        }

        if (!inserted) {
          const lines = value.split("\n");
          element.replaceChildren();

          lines.forEach((line, index) => {
            if (index > 0) {
              element.append(document.createElement("br"));
            }

            element.append(document.createTextNode(line));
          });
        }
      }

      function dispatchEditableEvents(element, value) {
        element.dispatchEvent(new InputEvent("input", {
          bubbles: true,
          inputType: "insertText",
          data: value
        }));
        element.dispatchEvent(new Event("change", { bubbles: true }));
      }

      function getTargetElement() {
        const activeElement = document.activeElement;
        if (isEligibleInput(activeElement)) {
          return activeElement;
        }

        const selectors = [
          ".msg-form__contenteditable[contenteditable='true']",
          ".msg-form__contenteditable",
          "[role='textbox'][contenteditable='true']",
          "textarea:not([readonly]):not([disabled])",
          "input[type='text']:not([readonly]):not([disabled])",
          "[contenteditable='true']"
        ];

        for (const selector of selectors) {
          const match = Array.from(document.querySelectorAll(selector)).find(isEligibleInput);
          if (match) {
            return match;
          }
        }

        return null;
      }

      if (typeof suggestionText !== "string" || !suggestionText.trim()) {
        return {
          ok: false,
          error: "Suggestion is empty."
        };
      }

      const target = getTargetElement();
      if (!target) {
        return {
          ok: false,
          error: "No editable message field was found on the page."
        };
      }

      target.focus();

      if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) {
        setInputValue(target, suggestionText);
        target.setSelectionRange?.(suggestionText.length, suggestionText.length);
      } else {
        setContentEditableValue(target, suggestionText);
      }

      dispatchEditableEvents(target, suggestionText);
      target.scrollIntoView({ block: "nearest" });

      return {
        ok: true
      };
    },
    args: [text]
  });

  if (!result?.ok) {
    throw new Error(result?.error || "Unable to inject the suggestion into the source page.");
  }

  const sourceTab = await chrome.tabs.update(sourceTabId, { active: true });
  if (typeof sourceTab?.windowId === "number") {
    await chrome.windows.update(sourceTab.windowId, { focused: true });
  }
}

async function runGeneration(regenerateConfig = null, { preserveRegenerateConfiguration = false } = {}) {
  const snapshot = getFormState();
  setActiveView("results");
  renderLoadingState();

  let parseResult;
  try {
    parseResult = await parseSourceTab(snapshot.modeId);
  } catch (error) {
    renderGenerationError(createGenerationIssue(
      "failed to parse the DOM",
      normalizeErrorMessage(error instanceof Error ? error.message : String(error))
    ));
    return;
  }

  if (parseResult?.status !== "success") {
    renderGenerationError(classifyParseFailure(parseResult));
    return;
  }

  let promptText;
  try {
    promptText = await buildPrompt(snapshot, parseResult, regenerateConfig);
  } catch (error) {
    renderGenerationError(classifyBuildPromptFailure(error));
    return;
  }

  try {
    const generationResult = await requestSuggestions(promptText);
    renderSuggestions(generationResult.suggestions, { preserveRegenerateConfiguration });
  } catch (error) {
    renderGenerationError(classifySuggestionFailure(error));
  }
}

languageGroup?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-group='language']");
  if (!button) {
    return;
  }

  formState.language = button.dataset.value;
  updateSingleSelect(languageGroup, formState.language);
});

modeSelects.forEach((select) => {
  select.addEventListener("change", (event) => {
    const nextValue = event.target.value;
    const mode = getModeConfig(nextValue);
    formState.modeId = mode?.id ?? "auto";
    syncModeSelects();
    updateSuggestionActionStates();
  });
});

lengthUnitGroup?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-group='length-unit']");
  if (!button) {
    return;
  }

  formState.lengthUnit = button.dataset.value;
  updateSingleSelect(lengthUnitGroup, formState.lengthUnit);
});

lengthValueGroup?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-group='length-value']");
  if (!button) {
    return;
  }

  formState.lengthValue = button.dataset.value;
  updateSingleSelect(lengthValueGroup, formState.lengthValue);
});

toneGroup?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-group='tone']");
  if (!button) {
    return;
  }

  const value = button.dataset.value;
  const includesValue = formState.tones.includes(value);

  if (value === "auto") {
    formState.tones = includesValue ? [] : ["auto"];
    updateToneSelection();
    return;
  }

  const tonesWithoutAuto = formState.tones.filter((tone) => tone !== "auto");
  formState.tones = includesValue
    ? tonesWithoutAuto.filter((tone) => tone !== value)
    : [...tonesWithoutAuto, value];

  updateToneSelection();
});

toneReset?.addEventListener("click", () => {
  formState.tones = [];
  updateToneSelection();
});

configurationToggle?.addEventListener("click", () => {
  const isExpanded = configurationToggle.getAttribute("aria-expanded") === "true";
  setPanelExpanded(configurationToggle, configurationPanel, !isExpanded);
});

directionsToggle?.addEventListener("click", () => {
  const isExpanded = directionsToggle.getAttribute("aria-expanded") === "true";
  setPanelExpanded(directionsToggle, directionsPanel, !isExpanded);
});

regenerateConfigurationToggle?.addEventListener("click", () => {
  const isExpanded = regenerateConfigurationToggle.getAttribute("aria-expanded") === "true";
  setPanelExpanded(regenerateConfigurationToggle, regenerateConfigurationPanel, !isExpanded);
});

regenerateSuggestionGroup?.addEventListener("click", (event) => {
  const button = event.target.closest("[data-regenerate-suggestion-index]");
  if (!button || button.disabled) {
    return;
  }

  const index = Number(button.dataset.regenerateSuggestionIndex);
  regenerateFormState.selectedSuggestionIndices = regenerateFormState.selectedSuggestionIndices.includes(index)
    ? regenerateFormState.selectedSuggestionIndices.filter((value) => value !== index)
    : [...regenerateFormState.selectedSuggestionIndices, index].sort((left, right) => left - right);
  updateRegenerateSuggestionSelection();
});

generateButton?.addEventListener("click", () => {
  runGeneration(null);
});

retryButton?.addEventListener("click", () => {
  resetRegenerateConfiguration();
  setActiveView("composer");
  instructionsInput?.focus();
});

regenerateButton?.addEventListener("click", () => {
  runGeneration(buildRegenerateConfig(), { preserveRegenerateConfiguration: true });
});

llmSaveButton?.addEventListener("click", async () => {
  setLlmStatus("Saving connection settings...");

  try {
    await saveLlmSettings();
  } catch (error) {
    setLlmStatus(error instanceof Error ? error.message : String(error), "error");
  }
});

resumeUploadButton?.addEventListener("click", () => {
  resumeFileInput?.click();
});

resumeFileInput?.addEventListener("change", async () => {
  const [file] = Array.from(resumeFileInput.files ?? []);
  if (!file) {
    return;
  }

  try {
    await saveResumeFile(file);
  } catch (error) {
    setResumeStatus(error instanceof Error ? error.message : String(error), "error");
  } finally {
    resumeFileInput.value = "";
  }
});

resumeClearButton?.addEventListener("click", async () => {
  try {
    await persistSavedResume(null);
    setResumeStatus("Saved resume cleared. Cover-letter mode will no longer use resume context.", "success");
  } catch (error) {
    setResumeStatus(error instanceof Error ? error.message : String(error), "error");
  }
});

llmModalOpenButtons.forEach((button) => {
  button.addEventListener("click", () => {
    openLlmModal(button);
  });
});

uploadsModalOpenButtons.forEach((button) => {
  button.addEventListener("click", () => {
    openUploadsModal(button);
  });
});

debugModalOpenButtons.forEach((button) => {
  button.addEventListener("click", () => {
    openDebugModal(button);
  });
});

llmModalCloseButton?.addEventListener("click", () => {
  closeLlmModal();
});

uploadsModalCloseButton?.addEventListener("click", () => {
  closeUploadsModal();
});

debugModalCloseButton?.addEventListener("click", () => {
  closeDebugModal();
});

llmModalBackdrop?.addEventListener("click", (event) => {
  if (event.target === llmModalBackdrop) {
    closeLlmModal();
  }
});

uploadsModalBackdrop?.addEventListener("click", (event) => {
  if (event.target === uploadsModalBackdrop) {
    closeUploadsModal();
  }
});

debugModalBackdrop?.addEventListener("click", (event) => {
  if (event.target === debugModalBackdrop) {
    closeDebugModal();
  }
});

llmModal?.addEventListener("click", (event) => {
  event.stopPropagation();
});

uploadsModal?.addEventListener("click", (event) => {
  event.stopPropagation();
});

debugModal?.addEventListener("click", (event) => {
  event.stopPropagation();
});

debugParseTab?.addEventListener("click", () => {
  setDebugTab("parse");
});

debugPromptTab?.addEventListener("click", () => {
  setDebugTab("prompt");
});

copyButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const targetId = button.dataset.copyTarget;
    const target = document.getElementById(targetId);
    if (!target) {
      return;
    }

    await copyText(target.value);
    button.classList.add("is-copied");
    window.setTimeout(() => resetCopyButtonState(button), 1200);
  });
});

pickButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    if (button.disabled) {
      return;
    }

    const targetId = button.dataset.pickTarget;
    const target = targetId ? document.getElementById(targetId) : null;
    if (!(target instanceof HTMLTextAreaElement) || !isUsableSuggestionText(target.value)) {
      return;
    }

    try {
      await injectSuggestionIntoSourceTab(target.value);
      button.classList.add("is-picked");
      button.textContent = "picked";
      window.setTimeout(() => resetPickButtonState(button), 1200);
      window.close();
    } catch (error) {
      button.classList.remove("is-picked");
      button.textContent = error instanceof Error ? "failed" : "error";
      window.setTimeout(() => resetPickButtonState(button), 1600);
    }
  });
});

[closeButton, resultsCloseButton].forEach((button) => {
  button?.addEventListener("click", () => {
    resetRegenerateConfiguration();
    window.close();
  });
});

window.addEventListener("load", () => {
  populateModeOptions();
  populateModelOptions();
  updateSingleSelect(languageGroup, formState.language);
  updateSingleSelect(lengthUnitGroup, formState.lengthUnit);
  updateSingleSelect(lengthValueGroup, formState.lengthValue);
  updateToneSelection();
  setPanelExpanded(configurationToggle, configurationPanel, true);
  setPanelExpanded(directionsToggle, directionsPanel, false);
  resetRegenerateConfiguration();
  resizeSuggestionOutputs();
  scheduleWindowResize();
  updateSuggestionActionStates();

  loadLlmSettings().catch((error) => {
    const config = getLlmConfig();
    applyLlmSettings(config.DEFAULT_SETTINGS);
    setLlmStatus(error instanceof Error ? error.message : String(error), "error");
  });

  loadSavedResume().catch((error) => {
    savedResume = null;
    renderResumeState();
    setResumeStatus(error instanceof Error ? error.message : String(error), "error");
  });
});

window.addEventListener("resize", () => {
  if (window.outerHeight > window.screen.availHeight - WINDOW_MARGIN) {
    window.resizeTo(WINDOW_WIDTH, window.screen.availHeight - WINDOW_MARGIN);
  }
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && isDebugModalOpen()) {
    event.preventDefault();
    closeDebugModal();
    return;
  }

  if (event.key === "Escape" && isUploadsModalOpen()) {
    event.preventDefault();
    closeUploadsModal();
    return;
  }

  if (event.key === "Escape" && isLlmModalOpen()) {
    event.preventDefault();
    closeLlmModal();
  }
});
