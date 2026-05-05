importScripts(
  "llm/config.js",
  "llm/providers/openai-chat-completions.js"
);

const LLM_SETTINGS_STORAGE_KEY = "llmSettings";
const SIDE_PANEL_STATE_STORAGE_KEY = "openSidePanelTabIds";
const SIDE_PANEL_SOURCE_STORAGE_KEY = "sidePanelSource";
const openSidePanelTabIds = new Set();

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

async function getTrackedOpenSidePanelTabIds() {
  if (!chrome.storage?.session) {
    return new Set(openSidePanelTabIds);
  }

  const { [SIDE_PANEL_STATE_STORAGE_KEY]: storedTabIds } = await chrome.storage.session.get(SIDE_PANEL_STATE_STORAGE_KEY);
  return new Set((storedTabIds ?? []).filter(Number.isInteger));
}

async function setTrackedOpenSidePanelTabIds(tabIds) {
  openSidePanelTabIds.clear();
  tabIds.forEach((tabId) => {
    openSidePanelTabIds.add(tabId);
  });

  if (chrome.storage?.session) {
    await chrome.storage.session.set({
      [SIDE_PANEL_STATE_STORAGE_KEY]: [...tabIds]
    });
  }
}

async function markSidePanelOpen(tabId) {
  if (!Number.isInteger(tabId)) {
    return;
  }

  const tabIds = await getTrackedOpenSidePanelTabIds();
  tabIds.add(tabId);
  await setTrackedOpenSidePanelTabIds(tabIds);
}

async function markSidePanelClosed(tabId) {
  if (!Number.isInteger(tabId)) {
    return;
  }

  const tabIds = await getTrackedOpenSidePanelTabIds();
  tabIds.delete(tabId);
  await setTrackedOpenSidePanelTabIds(tabIds);
}

async function saveSidePanelSource(tab, sourceUrl) {
  if (!chrome.storage?.session || !Number.isInteger(tab?.id)) {
    return;
  }

  await chrome.storage.session.set({
    [SIDE_PANEL_SOURCE_STORAGE_KEY]: {
      sourceTabId: tab.id,
      sourceUrl,
      windowId: tab.windowId
    }
  });
}

async function getSavedSidePanelSource() {
  if (!chrome.storage?.session) {
    return null;
  }

  const { [SIDE_PANEL_SOURCE_STORAGE_KEY]: source } = await chrome.storage.session.get(SIDE_PANEL_SOURCE_STORAGE_KEY);
  return source ?? null;
}

function buildSidePanelPath(tab, sourceUrl) {
  const params = new URLSearchParams();

  if (sourceUrl) {
    params.set("sourceUrl", sourceUrl);
  }

  if (Number.isInteger(tab?.id)) {
    params.set("sourceTabId", String(tab.id));
  }

  const query = params.toString();
  return query ? `popup.html?${query}` : "popup.html";
}

async function closeSidePanelForTabId(tabId) {
  if (!Number.isInteger(tabId)) {
    return false;
  }

  if (!chrome.sidePanel?.close) {
    markSidePanelClosed(tabId).catch((error) => {
      console.warn("Unable to update Converse side panel state.", error);
    });
    return false;
  }

  try {
    chrome.sidePanel.close({ tabId }).catch((error) => {
      console.warn("Unable to close Converse side panel.", error);
    });
  } catch (error) {
    console.warn("Unable to close Converse side panel.", error);
  }

  markSidePanelClosed(tabId).catch((error) => {
    console.warn("Unable to update Converse side panel state.", error);
  });

  return true;
}

function openSidePanelForTab(tab) {
  const resolvedSourceUrl = tab?.url ?? tab?.pendingUrl ?? "";
  const path = buildSidePanelPath(tab, resolvedSourceUrl);

  const setOptionsPromise = chrome.sidePanel.setOptions({
    tabId: tab.id,
    path,
    enabled: true
  });

  const openPromise = chrome.sidePanel.open({ tabId: tab.id });

  return Promise.all([setOptionsPromise, openPromise])
    .then(() => Promise.all([
      markSidePanelOpen(tab.id),
      saveSidePanelSource(tab, resolvedSourceUrl)
    ]));
}

async function toggleSidePanel(tab) {
  if (!Number.isInteger(tab?.id)) {
    throw new Error("Unable to open Converse without an active source tab.");
  }

  if (openSidePanelTabIds.has(tab.id)) {
    await closeSidePanelForTabId(tab.id);
    return;
  }

  return openSidePanelForTab(tab);
}

chrome.action.onClicked.addListener((tab) => {
  toggleSidePanel(tab).catch((error) => {
    markSidePanelClosed(tab?.id).catch((trackingError) => {
      console.warn("Unable to update Converse side panel state.", trackingError);
    });
    console.error("Unable to toggle Converse side panel.", error);
  });
});

chrome.tabs.onRemoved.addListener((tabId) => {
  markSidePanelClosed(tabId).catch((error) => {
    console.warn("Unable to clear Converse side panel state for removed tab.", error);
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
      case "converse:get-side-panel-source":
        return {
          ok: true,
          source: await getSavedSidePanelSource()
        };
      case "converse:close-side-panel":
        closeSidePanelForTabId(message.sourceTabId).catch((error) => {
          console.warn("Unable to close Converse side panel.", error);
        });
        return {
          ok: true
        };
      case "converse:side-panel-unloaded":
        if (Number.isInteger(message.sourceTabId)) {
          await markSidePanelClosed(message.sourceTabId);
        }
        return {
          ok: true
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
