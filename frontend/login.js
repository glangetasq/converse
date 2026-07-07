const DEFAULT_CURRENT_USER = "Quentin Glangetas";
const CURRENT_USER_STORAGE_KEY = "current_user";
const CURRENT_USER_ID_STORAGE_KEY = "current_user_id";

const loginForm = document.getElementById("login-form");
const usernameInput = document.getElementById("login-username-input");
const submitButton = document.getElementById("login-submit-button");
const statusOutput = document.getElementById("login-status-output");

function setStatus(message, tone = "muted") {
  statusOutput.textContent = message;
  statusOutput.classList.toggle("is-success", tone === "success");
  statusOutput.classList.toggle("is-error", tone === "error");
}

function normalizeUsername(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

function getAuthenticatedUser(responseBody, fallbackUsername) {
  if (!responseBody || typeof responseBody !== "object") {
    return null;
  }

  const currentUser = normalizeUsername(responseBody.current_user ?? responseBody.currentUser ?? fallbackUsername);
  const currentUserId = String(responseBody.current_user_id ?? responseBody.currentUserId ?? "").trim();

  if (!currentUser || !currentUserId) {
    return null;
  }

  return { currentUser, currentUserId };
}

async function loadStoredUser() {
  const stored = await chrome.storage.local.get([CURRENT_USER_STORAGE_KEY, CURRENT_USER_ID_STORAGE_KEY]);
  const currentUser = normalizeUsername(stored[CURRENT_USER_STORAGE_KEY]);
  const currentUserId = String(stored[CURRENT_USER_ID_STORAGE_KEY] ?? "").trim();

  usernameInput.value = currentUser || DEFAULT_CURRENT_USER;

  if (currentUser && currentUserId) {
    setStatus(`signed in as ${currentUser}`, "success");
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const username = normalizeUsername(usernameInput.value);
  if (!username) {
    setStatus("username is required", "error");
    usernameInput.focus();
    return;
  }

  submitButton.disabled = true;
  setStatus("connecting to backend…");

  try {
    const responseBody = await ConverseApi.login(username);
    const authenticatedUser = getAuthenticatedUser(responseBody, username);
    if (!authenticatedUser) {
      throw new Error("Backend response did not include a user id.");
    }

    await chrome.storage.local.set({
      [CURRENT_USER_STORAGE_KEY]: authenticatedUser.currentUser,
      [CURRENT_USER_ID_STORAGE_KEY]: authenticatedUser.currentUserId
    });
    setStatus(`signed in as ${authenticatedUser.currentUser}`, "success");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : String(error), "error");
  } finally {
    submitButton.disabled = false;
  }
});

window.addEventListener("load", () => {
  loadStoredUser().catch((error) => {
    usernameInput.value = DEFAULT_CURRENT_USER;
    setStatus(error instanceof Error ? error.message : String(error), "error");
  });
});
