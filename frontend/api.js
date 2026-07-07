(() => {
  const DEFAULT_BASE_URL = "http://localhost:3000";
  const BACKEND_URL_STORAGE_KEY = "backend_url";

  let baseUrlPromise = null;

  function getBaseUrl() {
    if (!baseUrlPromise) {
      baseUrlPromise = chrome.storage.local
        .get(BACKEND_URL_STORAGE_KEY)
        .then((stored) => String(stored[BACKEND_URL_STORAGE_KEY] || DEFAULT_BASE_URL).replace(/\/+$/, ""))
        .catch(() => DEFAULT_BASE_URL);
    }

    return baseUrlPromise;
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

  async function request(path, { method = "GET", body } = {}) {
    const baseUrl = await getBaseUrl();
    let response;
    try {
      response = await fetch(`${baseUrl}${path}`, {
        method,
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body)
      });
    } catch (_error) {
      throw new Error(`Backend unreachable at ${baseUrl} — is it running?`);
    }

    const responseBody = await readBody(response);
    if (!response.ok) {
      throw new Error(extractErrorDetail(responseBody, response.status));
    }

    return responseBody;
  }

  globalThis.ConverseApi = Object.freeze({
    getBaseUrl,
    getModels: () => request("/api/llm/models"),
    generateFollowup: (payload) => request("/api/followups/generate", { method: "POST", body: payload }),
    previewPrompt: (payload) => request("/api/followups/preview", { method: "POST", body: payload }),
    saveEvalExample: (payload) => request("/api/eval_examples", { method: "POST", body: payload }),
    saveParsedProfile: (payload) => request("/api/debug/parse_dump", { method: "POST", body: payload }),
    login: (username) => request("/api/auth/login", { method: "POST", body: { username } })
  });
})();
