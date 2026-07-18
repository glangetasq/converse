(() => {
  const DEFAULT_BASE_URL = "http://localhost:3000";
  const BACKEND_URL_STORAGE_KEY = "backend_url";
  const API_KEY_STORAGE_KEY = "api_key";
  const MODELS_CACHE_STORAGE_KEY = "models_cache";
  const LAST_OK_STORAGE_KEY = "backend_last_ok_at";

  // /api/llm/models reads a static KNOWN_MODELS, so it only changes on redeploy.
  const MODELS_TTL_MS = 3600000;
  // No probe can tell us the backend is warm without waking it, so infer: a request
  // succeeded recently => the instance is probably still up.
  const WARM_WINDOW_MS = 300000;

  // Scale-to-zero: a cold hit pays container start + Neon resume, so the first call
  // can be slow or 5xx where a warm one would not.
  const REQUEST_TIMEOUT_MS = 20000;
  // A hosted/* model runs on its own scale-to-zero GPU service; a cold one adds a
  // multi-minute container + weight-load start on top of the backend, so a generate
  // call routed to it needs a far longer ceiling than a frontier API call.
  const HOSTED_REQUEST_TIMEOUT_MS = 300000;
  const RETRY_DELAYS_MS = [400, 1200];

  let settingsPromise = null;

  function getSettings() {
    if (!settingsPromise) {
      settingsPromise = chrome.storage.local
        .get([BACKEND_URL_STORAGE_KEY, API_KEY_STORAGE_KEY])
        .then((stored) => ({
          baseUrl: String(stored[BACKEND_URL_STORAGE_KEY] || DEFAULT_BASE_URL).replace(/\/+$/, ""),
          apiKey: String(stored[API_KEY_STORAGE_KEY] || "")
        }))
        .catch(() => ({ baseUrl: DEFAULT_BASE_URL, apiKey: "" }));
    }

    return settingsPromise;
  }

  // Settings are memoized for the page lifetime; saving must invalidate or the side
  // panel keeps using the previous backend until it is reopened.
  function resetSettings() {
    settingsPromise = null;
  }

  function getBaseUrl() {
    return getSettings().then((settings) => settings.baseUrl);
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  // Mirrors the backend's VLLMClient.MODEL_PREFIX — self-hosted models are `hosted/<name>`.
  const isHostedModel = (model) => typeof model === "string" && model.startsWith("hosted/");

  function markBackendOk() {
    return chrome.storage.local.set({ [LAST_OK_STORAGE_KEY]: Date.now() }).catch(() => {});
  }

  async function isProbablyWarm() {
    const stored = await chrome.storage.local.get(LAST_OK_STORAGE_KEY).catch(() => ({}));
    const lastOkAt = stored[LAST_OK_STORAGE_KEY];
    return typeof lastOkAt === "number" && Date.now() - lastOkAt < WARM_WINDOW_MS;
  }

  async function readBody(response) {
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

  function extractErrorDetail(body, statusCode) {
    if (body && typeof body === "object" && body.detail) {
      return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    }

    return `Backend returned HTTP ${statusCode}.`;
  }

  function buildHeaders(apiKey, hasBody) {
    const headers = {};
    if (hasBody) {
      headers["Content-Type"] = "application/json";
    }
    // Unset locally (the backend leaves the gate open when CONVERSE_API_KEY is unset),
    // required against Cloud Run.
    if (apiKey) {
      headers.Authorization = `Bearer ${apiKey}`;
    }

    return headers;
  }

  async function attempt(baseUrl, apiKey, path, method, body, timeoutMs) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      return await fetch(`${baseUrl}${path}`, {
        method,
        headers: buildHeaders(apiKey, body !== undefined),
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal
      });
    } finally {
      clearTimeout(timeout);
    }
  }

  async function request(path, { method = "GET", body, timeoutMs = REQUEST_TIMEOUT_MS } = {}) {
    const { baseUrl, apiKey } = await getSettings();
    const isLocal = baseUrl.startsWith("http://localhost") || baseUrl.startsWith("http://127.0.0.1");
    let response = null;
    let networkError = null;

    for (let i = 0; i <= RETRY_DELAYS_MS.length; i += 1) {
      networkError = null;
      try {
        response = await attempt(baseUrl, apiKey, path, method, body, timeoutMs);
      } catch (error) {
        networkError = error;
      }

      // Retry only what a cold start can cause: a dropped/timed-out connection or a 5xx.
      // 4xx is a real answer — retrying it just wastes the user's time.
      const retriable = networkError !== null || response.status >= 500;
      if (!retriable || i === RETRY_DELAYS_MS.length) {
        break;
      }

      await sleep(RETRY_DELAYS_MS[i]);
    }

    if (networkError !== null) {
      if (networkError.name === "AbortError") {
        throw new Error(`Backend timed out after ${timeoutMs / 1000}s at ${baseUrl}.`);
      }
      if (isLocal) {
        throw new Error(`Backend unreachable at ${baseUrl} — is it running?`);
      }
      throw new Error(`Backend unreachable at ${baseUrl} — check the backend url in settings.`);
    }

    const responseBody = await readBody(response);
    if (response.status === 401) {
      throw new Error("Rejected by the backend (401) — set or refresh the api key in settings.");
    }
    if (!response.ok) {
      throw new Error(extractErrorDetail(responseBody, response.status));
    }

    markBackendOk();
    return responseBody;
  }

  // Never wakes a sleeping backend just for the model menu: a cold start is only paid
  // when there is no cache at all. Otherwise the refresh waits for some other request
  // to prove the backend is up.
  async function getModelsCached() {
    const stored = await chrome.storage.local.get(MODELS_CACHE_STORAGE_KEY).catch(() => ({}));
    const cached = stored[MODELS_CACHE_STORAGE_KEY];
    const hasCache = Boolean(cached && cached.payload);

    if (hasCache && Date.now() - cached.fetchedAt < MODELS_TTL_MS) {
      return cached.payload;
    }
    if (hasCache && !(await isProbablyWarm())) {
      return cached.payload;
    }

    try {
      const payload = await request("/api/llm/models");
      await chrome.storage.local.set({
        [MODELS_CACHE_STORAGE_KEY]: { payload, fetchedAt: Date.now() }
      });
      return payload;
    } catch (error) {
      if (hasCache) {
        return cached.payload;
      }
      throw error;
    }
  }

  // Force a fresh fetch (bypasses the TTL + warm gating) and overwrite the cache, so the
  // menu picks up models a redeploy added without waiting out the TTL or reopening the panel.
  async function refreshModels() {
    const payload = await request("/api/llm/models");
    await chrome.storage.local.set({
      [MODELS_CACHE_STORAGE_KEY]: { payload, fetchedAt: Date.now() }
    });
    return payload;
  }

  globalThis.ConverseApi = Object.freeze({
    getBaseUrl,
    getSettings,
    resetSettings,
    saveSettings: async ({ backendUrl, apiKey }) => {
      await chrome.storage.local.set({
        [BACKEND_URL_STORAGE_KEY]: backendUrl.trim().replace(/\/+$/, ""),
        [API_KEY_STORAGE_KEY]: apiKey.trim()
      });
      // the cached menu and warm flag describe the previous backend
      await chrome.storage.local.remove([MODELS_CACHE_STORAGE_KEY, LAST_OK_STORAGE_KEY]);
      resetSettings();
    },
    checkHealth: () => request("/health"),
    getModels: () => request("/api/llm/models"),
    getModelsCached,
    refreshModels,
    generateFollowup: (payload) =>
      request("/api/followups/generate", {
        method: "POST",
        body: payload,
        timeoutMs: isHostedModel(payload?.model) ? HOSTED_REQUEST_TIMEOUT_MS : REQUEST_TIMEOUT_MS
      }),
    ingestFollowup: (generationId, payload) =>
      request(`/api/followups/${generationId}/ingest`, { method: "POST", body: payload }),
    previewPrompt: (payload) => request("/api/followups/preview", { method: "POST", body: payload }),
    saveEvalExample: (payload) => request("/api/eval_examples", { method: "POST", body: payload }),
    saveParsedProfile: (payload) => request("/api/debug/parse_dump", { method: "POST", body: payload }),
    login: (username) => request("/api/auth/login", { method: "POST", body: { username } })
  });
})();
