(() => {
  const PROVIDERS = Object.freeze({
    "openai-chat-completions": Object.freeze({
      id: "openai-chat-completions",
      label: "OpenAI",
      description: "Route prompt generation through your own OpenAI-compatible relay."
    })
  });

  const MODEL_OPTIONS = Object.freeze([
    Object.freeze({ value: "gpt-5.2", label: "gpt-5.2 ($14.00/M output)" }),
    Object.freeze({ value: "gpt-5-mini", label: "gpt-5 mini ($2.00/M output)" }),
    Object.freeze({ value: "gpt-5-nano", label: "gpt-5 nano ($0.40/M output)" }),
    Object.freeze({ value: "gpt-4.1", label: "gpt-4.1 ($8.00/M output)" }),
    Object.freeze({ value: "gpt-4.1-mini", label: "gpt-4.1 mini ($1.60/M output)" }),
    Object.freeze({ value: "gpt-4.1-nano", label: "gpt-4.1 nano ($0.40/M output)" }),
    Object.freeze({ value: "gpt-4o", label: "gpt-4o ($10.00/M output)" }),
    Object.freeze({ value: "gpt-4o-mini", label: "gpt-4o mini ($0.60/M output)" }),
    Object.freeze({ value: "o3", label: "o3 ($8.00/M output)" }),
    Object.freeze({ value: "o4-mini", label: "o4-mini ($4.40/M output)" })
  ]);

  const DEFAULT_SETTINGS = Object.freeze({
    provider: "openai-chat-completions",
    baseUrl: "http://127.0.0.1:8787",
    path: "/v1/chat/completions",
    model: "gpt-4.1-mini",
    temperature: 0.9
  });

  function clampNumber(value, minimum, maximum, fallback) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) {
      return fallback;
    }

    return Math.min(Math.max(parsed, minimum), maximum);
  }

  function normalizeBaseUrl(value) {
    if (typeof value !== "string") {
      return "";
    }

    return value.trim().replace(/\/+$/g, "");
  }

  function normalizePath(value) {
    if (typeof value !== "string") {
      return DEFAULT_SETTINGS.path;
    }

    const trimmed = value.trim();
    if (!trimmed) {
      return DEFAULT_SETTINGS.path;
    }

    return trimmed.startsWith("/") ? trimmed : `/${trimmed}`;
  }

  function normalizeProvider(providerId) {
    return PROVIDERS[providerId] ? providerId : DEFAULT_SETTINGS.provider;
  }

  function getModelOption(modelId) {
    return MODEL_OPTIONS.find((option) => option.value === modelId) ?? null;
  }

  function normalizeSettings(settings = {}) {
    return {
      provider: normalizeProvider(settings.provider),
      baseUrl: normalizeBaseUrl(settings.baseUrl) || DEFAULT_SETTINGS.baseUrl,
      path: normalizePath(settings.path),
      model: typeof settings.model === "string" && settings.model.trim()
        ? settings.model.trim()
        : DEFAULT_SETTINGS.model,
      temperature: clampNumber(settings.temperature, 0, 2, DEFAULT_SETTINGS.temperature)
    };
  }

  function getProvider(providerId) {
    return PROVIDERS[normalizeProvider(providerId)];
  }

  function getOriginPattern(baseUrl) {
    const normalizedBaseUrl = normalizeBaseUrl(baseUrl);
    if (!normalizedBaseUrl) {
      throw new Error("An LLM relay URL is required.");
    }

    const url = new URL(normalizedBaseUrl);
    return `${url.origin}/*`;
  }

  globalThis.ConverseLlmConfig = Object.freeze({
    DEFAULT_SETTINGS,
    MODEL_OPTIONS,
    PROVIDERS,
    getModelOption,
    getOriginPattern,
    getProvider,
    normalizeSettings
  });
})();
