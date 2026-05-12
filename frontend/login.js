const DEFAULT_CURRENT_USER = "Quentin Glangetas";
const BACKEND_BASE_URL = "http://localhost:3000";
const LOGIN_ENDPOINT = `${BACKEND_BASE_URL}/api/auth/login`;
const CURRENT_USER_STORAGE_KEY = "current_user";
const CURRENT_USER_ID_STORAGE_KEY = "current_user_id";

const loginForm = document.getElementById("login-form");
const usernameInput = document.getElementById("login-username-input");
const submitButton = document.getElementById("login-submit-button");
const statusOutput = document.getElementById("login-status-output");

function setStatus(message, tone = "muted") {
  if (!statusOutput) {
    return;
  }

  statusOutput.textContent = message;
  statusOutput.classList.toggle("is-success", tone === "success");
  statusOutput.classList.toggle("is-error", tone === "error");
}

function normalizeUsername(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
}

async function requestBackendPermission() {
  if (!chrome.permissions?.contains || !chrome.permissions?.request) {
    return true;
  }

  const backendUrl = new URL(BACKEND_BASE_URL);
  const originPattern = `${backendUrl.protocol}//${backendUrl.hostname}/*`;
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

async function readResponseBody(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text);
  } catch (_error) {
    return text;
  }
}

function getResponseError(responseBody, statusCode) {
  if (responseBody && typeof responseBody === "object" && "detail" in responseBody) {
    return String(responseBody.detail);
  }

  return `Login failed with HTTP ${statusCode}.`;
}

function getAuthenticatedUser(responseBody, fallbackUsername) {
  if (!responseBody || typeof responseBody !== "object") {
    return null;
  }

  const currentUser = normalizeUsername(
    responseBody.current_user
      ?? responseBody.currentUser
      ?? responseBody.user?.displayName
      ?? fallbackUsername
  );
  const currentUserId = String(
    responseBody.current_user_id
      ?? responseBody.currentUserId
      ?? responseBody.user_id
      ?? responseBody.userId
      ?? responseBody.user?.id
      ?? ""
  ).trim();

  if (!currentUser || !currentUserId) {
    return null;
  }

  return {
    currentUser,
    currentUserId
  };
}

async function authenticate(username) {
  const response = await fetch(LOGIN_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ username })
  });
  const responseBody = await readResponseBody(response);

  if (!response.ok) {
    throw new Error(getResponseError(responseBody, response.status));
  }

  const authenticatedUser = getAuthenticatedUser(responseBody, username);
  if (!authenticatedUser) {
    throw new Error("Backend response did not include a user id.");
  }

  return authenticatedUser;
}

async function saveAuthenticatedUser(authenticatedUser) {
  await chrome.storage.local.set({
    [CURRENT_USER_STORAGE_KEY]: authenticatedUser.currentUser,
    [CURRENT_USER_ID_STORAGE_KEY]: authenticatedUser.currentUserId
  });
}

async function loadStoredUser() {
  const stored = await chrome.storage.local.get([
    CURRENT_USER_STORAGE_KEY,
    CURRENT_USER_ID_STORAGE_KEY
  ]);
  const currentUser = normalizeUsername(stored[CURRENT_USER_STORAGE_KEY]);
  const currentUserId = String(stored[CURRENT_USER_ID_STORAGE_KEY] ?? "").trim();

  if (usernameInput) {
    usernameInput.value = currentUser || DEFAULT_CURRENT_USER;
  }

  if (currentUser && currentUserId) {
    setStatus(`signed in as ${currentUser}`, "success");
  }
}

loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();

  const username = normalizeUsername(usernameInput?.value);
  if (!username) {
    setStatus("username is required", "error");
    usernameInput?.focus();
    return;
  }

  if (submitButton) {
    submitButton.disabled = true;
  }
  setStatus("connecting to backend...");

  try {
    const permissionGranted = await requestBackendPermission();
    if (!permissionGranted) {
      throw new Error(`Permission was not granted for ${BACKEND_BASE_URL}.`);
    }

    const authenticatedUser = await authenticate(username);
    await saveAuthenticatedUser(authenticatedUser);
    setStatus(`signed in as ${authenticatedUser.currentUser}`, "success");
  } catch (error) {
    setStatus(error instanceof Error ? error.message : String(error), "error");
  } finally {
    if (submitButton) {
      submitButton.disabled = false;
    }
  }
});

window.addEventListener("load", () => {
  loadStoredUser().catch((error) => {
    if (usernameInput) {
      usernameInput.value = DEFAULT_CURRENT_USER;
    }
    setStatus(error instanceof Error ? error.message : String(error), "error");
  });
});
