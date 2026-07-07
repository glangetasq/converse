const TAB_STATE_PREFIX = "tabState:";

// The side panel is global (follows the active tab from popup.js); Chrome natively
// toggles it from the action icon.
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error("Unable to configure Converse side panel behavior.", error));

chrome.tabs.onRemoved.addListener((tabId) => {
  chrome.storage.session?.remove(`${TAB_STATE_PREFIX}${tabId}`).catch((error) => {
    console.warn("Unable to clear Converse state for removed tab.", error);
  });
});
