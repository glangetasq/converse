importScripts(
  "llm/config.js",
  "llm/providers/openai-chat-completions.js"
);

const POPUP_WIDTH = 760;
const POPUP_HEIGHT = 340;
const LLM_SETTINGS_STORAGE_KEY = "llmSettings";

function getLlmConfig() {
  const config = globalThis.ConverseLlmConfig;
  if (!config) {
    throw new Error("LLM configuration is unavailable.");
  }

  return config;
}

function getLlmProvider(providerId) {
  const provider = globalThis.ConverseLlmProviders?.[providerId];
  if (!provider) {
    throw new Error(`Unknown LLM provider "${providerId}".`);
  }

  return provider;
}

async function getStoredLlmSettings() {
  const { [LLM_SETTINGS_STORAGE_KEY]: storedSettings } = await chrome.storage.local.get(LLM_SETTINGS_STORAGE_KEY);
  return getLlmConfig().normalizeSettings(storedSettings);
}

async function saveLlmSettings(settings) {
  const normalizedSettings = getLlmConfig().normalizeSettings(settings);
  await chrome.storage.local.set({
    [LLM_SETTINGS_STORAGE_KEY]: normalizedSettings
  });

  return normalizedSettings;
}

async function hasOriginPermission(baseUrl) {
  const originPattern = getLlmConfig().getOriginPattern(baseUrl);
  return chrome.permissions.contains({
    origins: [originPattern]
  });
}

async function generateSuggestions(request) {
  const settings = await getStoredLlmSettings();
  if (!await hasOriginPermission(settings.baseUrl)) {
    throw new Error(`Permission to contact ${settings.baseUrl} has not been granted yet.`);
  }

  const provider = getLlmProvider(settings.provider);
  return provider.generate(request, settings);
}

async function getSourceUrl(tab) {
  if (!tab?.id) {
    return tab?.url ?? tab?.pendingUrl ?? "";
  }

  const resolvedTab = await chrome.tabs.get(tab.id);
  return resolvedTab?.url ?? resolvedTab?.pendingUrl ?? tab?.url ?? tab?.pendingUrl ?? "";
}

async function openCenteredPeek(tab) {
  const resolvedSourceUrl = await getSourceUrl(tab);
  const sourceUrl = resolvedSourceUrl ? `?sourceUrl=${encodeURIComponent(resolvedSourceUrl)}` : "";
  const sourceTabId = Number.isInteger(tab?.id) ? `&sourceTabId=${encodeURIComponent(tab.id)}` : "";
  const currentWindow = tab?.windowId
    ? await chrome.windows.get(tab.windowId)
    : await chrome.windows.getLastFocused();

  const left = typeof currentWindow.left === "number" && typeof currentWindow.width === "number"
    ? Math.max(currentWindow.left + Math.round((currentWindow.width - POPUP_WIDTH) / 2), 0)
    : undefined;

  const top = typeof currentWindow.top === "number" && typeof currentWindow.height === "number"
    ? Math.max(currentWindow.top + Math.round((currentWindow.height - POPUP_HEIGHT) / 2), 0)
    : undefined;

  await chrome.windows.create({
    url: `popup.html${sourceUrl}${sourceTabId}`,
    type: "popup",
    width: POPUP_WIDTH,
    height: POPUP_HEIGHT,
    left,
    top,
    focused: true
  });
}

chrome.action.onClicked.addListener((tab) => {
  openCenteredPeek(tab).catch((error) => {
    console.error("Unable to open centered peek window.", error);
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const handleMessage = async () => {
    switch (message?.type) {
      case "converse:get-llm-settings":
        return {
          ok: true,
          settings: await getStoredLlmSettings()
        };
      case "converse:save-llm-settings":
        return {
          ok: true,
          settings: await saveLlmSettings(message.settings)
        };
      case "converse:generate-suggestions":
        return {
          ok: true,
          result: await generateSuggestions(message.request)
        };
      default:
        return null;
    }
  };

  handleMessage()
    .then((response) => {
      if (response) {
        sendResponse(response);
      }
    })
    .catch((error) => {
      sendResponse({
        ok: false,
        error: error instanceof Error ? error.message : String(error)
      });
    });

  return true;
});
